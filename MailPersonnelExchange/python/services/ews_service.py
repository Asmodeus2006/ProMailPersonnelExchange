from __future__ import annotations

from datetime import datetime
from pathlib import Path

from exchangelib import (
    Account,
    Configuration,
    Credentials,
    DELEGATE,
    FileAttachment,
    HTMLBody,
    Mailbox,
    Message as EwsMessage,
)
from exchangelib.protocol import BaseProtocol, NoVerifyHTTPAdapter

from models.mail_item import MailItem


def _mailboxes(addresses: str) -> list[Mailbox]:
    return [Mailbox(email_address=a.strip()) for a in addresses.split(",") if a.strip()]


class EwsService:
    def __init__(self) -> None:
        self._account: Account | None = None
        self._extra_roots: dict[str, object] = {}  # display_name → root folder

    @property
    def is_connected(self) -> bool:
        return self._account is not None

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def connect(self, email: str, nip: str, password: str, domain: str, ews_url: str) -> None:
        BaseProtocol.HTTP_ADAPTER_CLS = NoVerifyHTTPAdapter
        creds = Credentials(username=f"{domain}\\{nip}", password=password)
        config = Configuration(service_endpoint=ews_url, credentials=creds)
        account = Account(
            primary_smtp_address=email,
            config=config,
            autodiscover=False,
            access_type=DELEGATE,
        )
        list(account.inbox.all().only("id")[:1])
        self._account = account

    def disconnect(self) -> None:
        self._account = None

    # ------------------------------------------------------------------
    # Inbox
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Extra mailbox discovery
    # ------------------------------------------------------------------

    def discover_extra_mailboxes(self) -> list[str]:
        """Walk the EWS root to find additional accessible mailboxes."""
        INBOX_NAMES = {"Inbox", "Boîte de réception", "Éléments reçus", "INBOX"}
        SKIP = {"Top of Information Store", "Non-IPM Subtree"}
        self._extra_roots.clear()
        found: list[str] = []
        try:
            for folder in self._account.root.children:
                name = getattr(folder, "name", "") or ""
                if not name or name in SKIP:
                    continue
                try:
                    child_names = {c.name for c in folder.children}
                    if child_names & INBOX_NAMES:
                        self._extra_roots[name] = folder
                        found.append(name)
                except Exception:
                    pass
        except Exception:
            pass
        return found

    def _find_subfolder(self, root_folder, folder_name: str):
        """Return the well-known sub-folder inside a mailbox root folder."""
        NAMES_MAP = {
            "inbox":  ["Inbox", "Boîte de réception", "Éléments reçus"],
            "sent":   ["Sent Items", "Éléments envoyés", "Sent"],
            "drafts": ["Drafts", "Brouillons"],
            "trash":  ["Deleted Items", "Éléments supprimés", "Corbeille"],
            "junk":   ["Junk Email", "Courrier indésirable", "Indésirables", "Spam"],
        }
        try:
            children = {c.name: c for c in root_folder.children}
            for name in NAMES_MAP.get(folder_name, []):
                if name in children:
                    return children[name]
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------
    # Folder loading
    # ------------------------------------------------------------------

    def load_folder(self, folder_name: str = "inbox",
                    mailbox: str | None = None,
                    max_items: int = 75) -> list[MailItem]:
        assert self._account is not None

        if mailbox and mailbox != "primary":
            root = self._extra_roots.get(mailbox)
            if root is None:
                return []
            folder = self._find_subfolder(root, folder_name)
            if folder is None:
                return []
        else:
            try:
                folder = {
                    "inbox":  self._account.inbox,
                    "sent":   self._account.sent,
                    "drafts": self._account.drafts,
                    "trash":  self._account.trash,
                    "junk":   self._account.junk,
                }.get(folder_name, self._account.inbox)
            except Exception:
                folder = self._account.inbox

        return self._load_items(folder, max_items)

    def _load_items(self, folder, max_items: int) -> list[MailItem]:
        raw = list(
            folder.all()
            .only("id", "changekey", "subject", "sender", "datetime_received",
                  "is_read", "has_attachments", "to_recipients")
            .order_by("-datetime_received")[:max_items]
        )
        items: list[MailItem] = []
        for msg in raw:
            sender_name = sender_email = ""
            if msg.sender:
                sender_name = msg.sender.name or ""
                sender_email = msg.sender.email_address or ""
            dt = msg.datetime_received
            local_dt = dt.astimezone() if dt else datetime.now()
            recipients = [
                r.email_address
                for r in (getattr(msg, "to_recipients", None) or [])
                if getattr(r, "email_address", None)
            ]
            items.append(MailItem(
                item_id=msg.id,
                change_key=msg.changekey,
                subject=msg.subject or "",
                sender_name=sender_name,
                sender_email=sender_email,
                date_received=local_dt,
                is_unread=not getattr(msg, "is_read", True),
                has_attachments=bool(getattr(msg, "has_attachments", False)),
                recipients=recipients,
            ))
        return items

    def load_inbox(self, max_items: int = 75) -> list[MailItem]:
        return self.load_folder("inbox", "primary", max_items)

    # ------------------------------------------------------------------
    # Full message body + attachment metadata
    # ------------------------------------------------------------------

    def load_body(self, item_id: str, change_key: str) -> MailItem:
        assert self._account is not None

        dummy = EwsMessage(id=item_id, changekey=change_key)
        full_items = list(self._account.fetch(ids=[dummy]))
        if not full_items:
            raise ValueError("Message introuvable")

        full = full_items[0]

        body_text = ""
        is_html = False
        body_obj = getattr(full, "body", None)
        if body_obj is not None:
            body_text = str(body_obj)
            is_html = isinstance(body_obj, HTMLBody)

        sender_name = sender_email = ""
        if getattr(full, "sender", None):
            sender_name = full.sender.name or ""
            sender_email = full.sender.email_address or ""

        recipients = [r.email_address for r in (getattr(full, "to_recipients", None) or [])
                      if getattr(r, "email_address", None)]
        cc = [r.email_address for r in (getattr(full, "cc_recipients", None) or [])
              if getattr(r, "email_address", None)]

        dt = getattr(full, "datetime_received", None)
        local_dt = dt.astimezone() if dt else datetime.now()

        # Collect attachment metadata (no content yet — fetched on demand)
        attachments_meta: list[dict] = []
        for att in (getattr(full, "attachments", None) or []):
            if isinstance(att, FileAttachment):
                att_id = att.attachment_id.id if att.attachment_id else None
                if att_id:
                    attachments_meta.append({
                        "name": att.name or "Pièce jointe",
                        "size": att.size or 0,
                        "id":   att_id,
                    })

        return MailItem(
            item_id=full.id,
            change_key=full.changekey,
            subject=getattr(full, "subject", "") or "",
            sender_name=sender_name,
            sender_email=sender_email,
            date_received=local_dt,
            body=body_text,
            is_html_body=is_html,
            is_unread=not getattr(full, "is_read", True),
            has_attachments=bool(getattr(full, "has_attachments", False)),
            recipients=recipients,
            cc_recipients=cc,
            attachments=attachments_meta,
        )

    # ------------------------------------------------------------------
    # Download an attachment
    # Returns (filename, content_bytes)
    # ------------------------------------------------------------------

    def download_attachment(self, item_id: str, change_key: str,
                            attachment_id: str) -> tuple[str, bytes]:
        assert self._account is not None

        dummy = EwsMessage(id=item_id, changekey=change_key)
        full_items = list(self._account.fetch(ids=[dummy]))
        if not full_items:
            raise ValueError("Message introuvable")

        full = full_items[0]
        for att in (getattr(full, "attachments", None) or []):
            if not isinstance(att, FileAttachment):
                continue
            att_id = att.attachment_id.id if att.attachment_id else None
            if att_id != attachment_id:
                continue
            content = att.content
            if content is None:
                raise ValueError("Le contenu de la pièce jointe est indisponible.")
            return att.name or "pièce_jointe", content

        raise ValueError("Pièce jointe introuvable.")

    # ------------------------------------------------------------------
    # Send / Reply / Forward  (all accept optional attachment_paths)
    # ------------------------------------------------------------------

    def send_new(self, to: str, subject: str, body: str,
                 cc: str = "", bcc: str = "",
                 attachment_paths: list[str] | None = None) -> None:
        assert self._account is not None
        msg = EwsMessage(
            account=self._account,
            subject=subject,
            body=body,
            to_recipients=_mailboxes(to),
        )
        if cc:
            msg.cc_recipients = _mailboxes(cc)
        if bcc:
            msg.bcc_recipients = _mailboxes(bcc)
        self._send_with_attachments(msg, attachment_paths)

    def send_reply(self, original_subject: str, sender_email: str,
                   body_prefix: str, cc: str = "",
                   attachment_paths: list[str] | None = None) -> None:
        assert self._account is not None
        msg = EwsMessage(
            account=self._account,
            subject=f"RE: {original_subject}",
            body=body_prefix,
            to_recipients=[Mailbox(email_address=sender_email)],
        )
        if cc:
            msg.cc_recipients = _mailboxes(cc)
        self._send_with_attachments(msg, attachment_paths)

    def send_reply_all(self, original_subject: str, sender_email: str,
                       recipients: list[str], body_prefix: str,
                       attachment_paths: list[str] | None = None) -> None:
        assert self._account is not None
        all_to = list(dict.fromkeys([sender_email] + recipients))
        msg = EwsMessage(
            account=self._account,
            subject=f"RE: {original_subject}",
            body=body_prefix,
            to_recipients=[Mailbox(email_address=e) for e in all_to if e],
        )
        self._send_with_attachments(msg, attachment_paths)

    def send_forward(self, original_subject: str, to: str, body: str,
                     cc: str = "",
                     attachment_paths: list[str] | None = None) -> None:
        assert self._account is not None
        msg = EwsMessage(
            account=self._account,
            subject=f"Fwd : {original_subject}",
            body=body,
            to_recipients=_mailboxes(to),
        )
        if cc:
            msg.cc_recipients = _mailboxes(cc)
        self._send_with_attachments(msg, attachment_paths)

    def _send_with_attachments(self, msg: EwsMessage,
                                attachment_paths: list[str] | None) -> None:
        paths = [p for p in (attachment_paths or []) if Path(p).exists()]
        if paths:
            msg.save(folder=self._account.drafts)  # Save as draft first so we can attach
            for p in paths:
                fp = Path(p)
                msg.attach(FileAttachment(name=fp.name, content=fp.read_bytes()))
            msg.send()
        else:
            msg.send_and_save()

    # ------------------------------------------------------------------
    # Email management
    # ------------------------------------------------------------------

    def delete_email(self, item_id: str, change_key: str) -> None:
        assert self._account is not None
        msg = EwsMessage(account=self._account, id=item_id, changekey=change_key)
        msg.move_to_trash()

    def mark_read(self, item_id: str, change_key: str, is_read: bool) -> None:
        assert self._account is not None
        items = list(self._account.fetch(
            ids=[EwsMessage(id=item_id, changekey=change_key)]
        ))
        if items:
            items[0].is_read = is_read
            items[0].save(update_fields=["is_read"])
