from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, date


@dataclass
class MailItem:
    item_id: str
    change_key: str
    subject: str
    sender_name: str
    sender_email: str
    date_received: datetime
    body: str = ""
    is_html_body: bool = False
    is_unread: bool = True
    has_attachments: bool = False
    recipients: list[str] = field(default_factory=list)
    cc_recipients: list[str] = field(default_factory=list)
    # Each dict: {"name": str, "size": int, "id": str}
    attachments: list[dict] = field(default_factory=list)

    @property
    def sender_display(self) -> str:
        return self.sender_name or self.sender_email or "Expéditeur inconnu"

    @property
    def date_display(self) -> str:
        today = date.today()
        d = self.date_received.date()
        if d == today:
            return self.date_received.strftime("%H:%M")
        delta = (today - d).days
        if delta < 7:
            days = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
            return days[d.weekday()]
        return d.strftime("%d.%m")

    @property
    def subject_display(self) -> str:
        return self.subject.strip() if self.subject else "(Sans sujet)"

    @property
    def meta_display(self) -> str:
        date_str = self.date_received.strftime("%d.%m.%Y %H:%M")
        parts = [f"De : {self.sender_display}"]
        if self.recipients:
            parts.append(f"À : {', '.join(self.recipients)}")
        parts.append(f"Date : {date_str}")
        return "    •    ".join(parts)
