from __future__ import annotations

import json
import re
from pathlib import Path

from PyQt6.QtCore import Qt, QObject, QRunnable, QThreadPool, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from models.mail_item import MailItem
from services.ews_service import EwsService


# ---------------------------------------------------------------------------
# Config helper (loads signature from shared config file)
# ---------------------------------------------------------------------------

def _get_signature() -> str:
    cfg_path = Path.home() / ".promed_messagerie.json"
    if cfg_path.exists():
        try:
            return json.loads(cfg_path.read_text(encoding="utf-8")).get("signature", "")
        except Exception:
            pass
    return ""


def _strip_html(html: str) -> str:
    """Very basic HTML → plain text for quoted messages."""
    html = re.sub(r"<(script|style)[^>]*>.*?</(script|style)>", "",
                  html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    html = re.sub(r"<p[^>]*>", "\n", html, flags=re.IGNORECASE)
    html = re.sub(r"</p>", "\n", html, flags=re.IGNORECASE)
    html = re.sub(r"<[^>]+>", "", html)
    html = html.replace("&nbsp;", " ").replace("&amp;", "&") \
               .replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
    html = re.sub(r"\n{3,}", "\n\n", html)
    return html.strip()


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------

class _Signals(QObject):
    finished = pyqtSignal()
    error    = pyqtSignal(str)


class _SendWorker(QRunnable):
    def __init__(self, fn, *args):
        super().__init__()
        self.fn   = fn
        self.args = args
        self.signals = _Signals()
        self.setAutoDelete(True)

    @pyqtSlot()
    def run(self) -> None:
        try:
            self.fn(*self.args)
        except Exception as exc:
            self.signals.error.emit(str(exc))
        finally:
            self.signals.finished.emit()


# ---------------------------------------------------------------------------
# ComposeWindow
# ---------------------------------------------------------------------------

_ICONS = {"new": "✉", "reply": "↩", "reply_all": "↩↩", "forward": "→"}
_TITLES = {
    "new":       "Nouveau message",
    "reply":     "Répondre",
    "reply_all": "Répondre à tous",
    "forward":   "Transférer",
}


class ComposeWindow(QDialog):
    def __init__(
        self,
        ews: EwsService,
        mode: str = "new",
        mail: MailItem | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._ews   = ews
        self._mode  = mode
        self._mail  = mail
        self._workers: list[_SendWorker] = []
        self._send_had_error = False
        self._attach_paths: list[str] = []

        self.setWindowTitle(_TITLES.get(mode, "Mail"))
        self.setMinimumSize(700, 600)
        self.resize(860, 720)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)

        self._build_ui()
        self._prefill()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header band ─────────────────────────────────────────────
        header = QFrame()
        header.setObjectName("composeHeader")
        header.setStyleSheet("#composeHeader{background:#1565c0;border:none;}")
        header.setFixedHeight(62)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(22, 0, 22, 0)
        hl.setSpacing(12)

        icon_lbl = QLabel(_ICONS.get(self._mode, "✉"))
        icon_lbl.setStyleSheet("color:#fff;font-size:22px;")
        hl.addWidget(icon_lbl)

        title_lbl = QLabel(_TITLES.get(self._mode, "Mail"))
        f = title_lbl.font()
        f.setPointSizeF(13.5)
        f.setBold(True)
        title_lbl.setFont(f)
        title_lbl.setStyleSheet("color:#fff;")
        hl.addWidget(title_lbl)
        hl.addStretch()
        root.addWidget(header)

        # ── Fields card ─────────────────────────────────────────────
        fields_card = QFrame()
        fields_card.setObjectName("composeFields")
        fl = QVBoxLayout(fields_card)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.setSpacing(0)

        # À row + inline CC/BCC toggles
        to_row = self._make_field_row("À", "_txt_to")
        self._btn_cc = QPushButton("CC")
        self._btn_cc.setFlat(True)
        self._btn_cc.setFixedHeight(28)
        self._btn_cc.setFixedWidth(38)
        self._btn_cc.setStyleSheet(
            "QPushButton{color:#90caf9;font-size:11px;border-radius:4px;}"
            "QPushButton:hover{background:rgba(144,202,249,0.15);}"
        )
        self._btn_cc.clicked.connect(self._toggle_cc)

        self._btn_bcc = QPushButton("CCI")
        self._btn_bcc.setFlat(True)
        self._btn_bcc.setFixedHeight(28)
        self._btn_bcc.setFixedWidth(38)
        self._btn_bcc.setStyleSheet(
            "QPushButton{color:#90caf9;font-size:11px;border-radius:4px;}"
            "QPushButton:hover{background:rgba(144,202,249,0.15);}"
        )
        self._btn_bcc.clicked.connect(self._toggle_bcc)
        to_row["inner_layout"].addWidget(self._btn_cc)
        to_row["inner_layout"].addWidget(self._btn_bcc)

        fl.addWidget(to_row["widget"])
        fl.addWidget(self._make_divider())

        # CC row (hidden)
        cc_data = self._make_field_row("CC", "_txt_cc")
        self._cc_frame = cc_data["widget"]
        self._cc_frame.hide()
        fl.addWidget(self._cc_frame)
        self._cc_sep = self._make_divider()
        self._cc_sep.hide()
        fl.addWidget(self._cc_sep)

        # BCC row (hidden)
        bcc_data = self._make_field_row("CCI", "_txt_bcc")
        self._bcc_frame = bcc_data["widget"]
        self._bcc_frame.hide()
        fl.addWidget(self._bcc_frame)
        self._bcc_sep = self._make_divider()
        self._bcc_sep.hide()
        fl.addWidget(self._bcc_sep)

        # Subject row
        fl.addWidget(self._make_field_row("Sujet", "_txt_subject")["widget"])
        root.addWidget(fields_card)

        # ── Attachment chips bar (hidden until files added) ─────────
        self._attach_bar = QWidget()
        self._attach_bar.setFixedHeight(46)
        self._attach_bar.setStyleSheet(
            "background:#f0f6ff;border-top:1px solid #dde8f5;"
            "border-bottom:1px solid #dde8f5;"
        )
        self._attach_chips_layout = QHBoxLayout(self._attach_bar)
        self._attach_chips_layout.setContentsMargins(14, 6, 14, 6)
        self._attach_chips_layout.setSpacing(8)
        self._attach_bar.hide()
        root.addWidget(self._attach_bar)

        # ── Body ────────────────────────────────────────────────────
        body_wrapper = QFrame()
        body_layout = QVBoxLayout(body_wrapper)
        body_layout.setContentsMargins(18, 14, 18, 10)
        body_layout.setSpacing(0)

        self._txt_body = QTextEdit()
        self._txt_body.setPlaceholderText("Écrivez votre message ici…")
        self._txt_body.setFrameShape(QFrame.Shape.NoFrame)
        self._txt_body.setStyleSheet(
            "QTextEdit{background:transparent;border:none;font-size:13px;}"
        )
        body_layout.addWidget(self._txt_body, stretch=1)
        root.addWidget(body_wrapper, stretch=1)

        # ── Bottom bar ───────────────────────────────────────────────
        bottom = QFrame()
        bottom.setFrameShape(QFrame.Shape.StyledPanel)
        bottom.setFixedHeight(60)
        bbl = QHBoxLayout(bottom)
        bbl.setContentsMargins(18, 0, 18, 0)
        bbl.setSpacing(10)

        # Attach button
        self._btn_attach = QPushButton("📎  Joindre un fichier")
        self._btn_attach.setFixedHeight(36)
        self._btn_attach.setFlat(True)
        self._btn_attach.setStyleSheet(
            "QPushButton{color:#1565c0;padding:0 10px;border-radius:5px;"
            "border:1px solid #c7d9f5;background:#f0f6ff;font-size:12px;}"
            "QPushButton:hover{background:#e0eaff;border-color:#1976d2;}"
        )
        self._btn_attach.clicked.connect(self._pick_files)
        bbl.addWidget(self._btn_attach)

        self._progress = QProgressBar()
        self._progress.setMaximum(0)
        self._progress.setFixedHeight(4)
        self._progress.setFixedWidth(120)
        self._progress.setTextVisible(False)
        self._progress.hide()
        bbl.addWidget(self._progress)

        bbl.addStretch()

        self._btn_cancel = QPushButton("Annuler")
        self._btn_cancel.setFixedSize(110, 36)
        self._btn_cancel.setFlat(True)
        self._btn_cancel.clicked.connect(self.reject)
        bbl.addWidget(self._btn_cancel)

        self._btn_send = QPushButton("  ✉  Envoyer")
        self._btn_send.setFixedSize(140, 36)
        self._btn_send.setStyleSheet(
            "QPushButton{background:#1565c0;color:#fff;border:none;"
            "border-radius:6px;font-weight:bold;font-size:13px;}"
            "QPushButton:hover{background:#1976d2;}"
            "QPushButton:disabled{background:#555;color:#999;}"
        )
        self._btn_send.clicked.connect(self._send)
        bbl.addWidget(self._btn_send)

        root.addWidget(bottom)

    def _make_field_row(self, label_text: str, attr: str) -> dict:
        widget = QFrame()
        widget.setFixedHeight(46)
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(18, 0, 12, 0)
        layout.setSpacing(10)

        lbl = QLabel(label_text)
        lbl.setFixedWidth(36)
        lbl.setStyleSheet("color:#90a4ae;font-size:12px;")
        layout.addWidget(lbl)

        txt = QLineEdit()
        txt.setFixedHeight(34)
        txt.setFrame(False)
        txt.setStyleSheet("QLineEdit{background:transparent;border:none;font-size:13px;}")
        setattr(self, attr, txt)
        layout.addWidget(txt, stretch=1)

        return {"widget": widget, "inner_layout": layout}

    @staticmethod
    def _make_divider() -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFixedHeight(1)
        sep.setContentsMargins(18, 0, 18, 0)
        return sep

    def _toggle_cc(self) -> None:
        visible = not self._cc_frame.isVisible()
        self._cc_frame.setVisible(visible)
        self._cc_sep.setVisible(visible)
        self._btn_cc.setStyleSheet(
            f"QPushButton{{color:{'#fff' if visible else '#90caf9'};"
            f"font-size:11px;border-radius:4px;"
            f"{'background:rgba(144,202,249,0.25);' if visible else ''}}}"
            "QPushButton:hover{background:rgba(144,202,249,0.15);}"
        )
        if visible:
            self._txt_cc.setFocus()

    def _toggle_bcc(self) -> None:
        visible = not self._bcc_frame.isVisible()
        self._bcc_frame.setVisible(visible)
        self._bcc_sep.setVisible(visible)
        self._btn_bcc.setStyleSheet(
            f"QPushButton{{color:{'#fff' if visible else '#90caf9'};"
            f"font-size:11px;border-radius:4px;"
            f"{'background:rgba(144,202,249,0.25);' if visible else ''}}}"
            "QPushButton:hover{background:rgba(144,202,249,0.15);}"
        )
        if visible:
            self._txt_bcc.setFocus()

    # ------------------------------------------------------------------
    # Attachments
    # ------------------------------------------------------------------

    def _pick_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self, "Joindre des fichiers",
            str(Path.home()),
            "Tous les fichiers (*)",
        )
        for path in files:
            if path not in self._attach_paths:
                self._attach_paths.append(path)
        self._refresh_attach_chips()

    def _refresh_attach_chips(self) -> None:
        while self._attach_chips_layout.count():
            item = self._attach_chips_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for path in self._attach_paths:
            name = Path(path).name
            chip = QWidget()
            chip.setStyleSheet(
                "background:#e0eaff;border-radius:10px;"
            )
            cl = QHBoxLayout(chip)
            cl.setContentsMargins(8, 2, 4, 2)
            cl.setSpacing(4)

            lbl = QLabel(f"📎  {name}")
            lbl.setStyleSheet("color:#1565c0;font-size:11px;background:transparent;")
            cl.addWidget(lbl)

            btn_rm = QPushButton("×")
            btn_rm.setFixedSize(18, 18)
            btn_rm.setFlat(True)
            btn_rm.setStyleSheet(
                "QPushButton{color:#ef5350;font-size:13px;"
                "font-weight:bold;background:transparent;border:none;}"
                "QPushButton:hover{color:#c62828;}"
            )
            _p = path
            btn_rm.clicked.connect(lambda _c, p=_p: self._remove_attachment(p))
            cl.addWidget(btn_rm)

            self._attach_chips_layout.addWidget(chip)

        self._attach_chips_layout.addStretch()
        self._attach_bar.setVisible(bool(self._attach_paths))

    def _remove_attachment(self, path: str) -> None:
        if path in self._attach_paths:
            self._attach_paths.remove(path)
        self._refresh_attach_chips()

    # ------------------------------------------------------------------
    # Pre-fill (recipients, subject, quoted text, signature)
    # ------------------------------------------------------------------

    def _prefill(self) -> None:
        sig = _get_signature()
        sig_block = f"\n\n-- \n{sig}" if sig else ""

        if not self._mail:
            # New mail: signature in body, cursor at top
            if sig:
                self._txt_body.setPlainText(sig_block.lstrip())
                self._move_cursor_top()
            return

        m = self._mail
        body_text = _strip_html(m.body) if m.is_html_body else m.body
        date_str  = m.date_received.strftime("%d.%m.%Y à %H:%M")

        if self._mode in ("reply", "reply_all"):
            if self._mode == "reply":
                self._txt_to.setText(m.sender_email)
                self._txt_to.setEnabled(False)
                self._txt_subject.setText(f"RE: {m.subject_display}")
            else:
                all_to = ", ".join(dict.fromkeys([m.sender_email] + m.recipients))
                self._txt_to.setText(all_to)
                self._txt_to.setEnabled(False)
                self._txt_subject.setText(f"RE: {m.subject_display}")
                if m.cc_recipients:
                    self._txt_cc.setText(", ".join(m.cc_recipients))
                    self._toggle_cc()

            quoted = (
                f"\n\n─────────────────────────────────\n"
                f"De : {m.sender_display}\n"
                f"Date : {date_str}\n"
                f"À : {', '.join(m.recipients)}\n"
                f"Sujet : {m.subject_display}\n\n"
                f"{body_text}"
            )
            self._txt_body.setPlainText(sig_block.lstrip() + quoted)
            self._move_cursor_top()

        elif self._mode == "forward":
            self._txt_subject.setText(f"Fwd : {m.subject_display}")
            quoted = (
                f"─────────────────────────────────\n"
                f"De : {m.sender_display}\n"
                f"Date : {date_str}\n"
                f"Sujet : {m.subject_display}\n"
                f"À : {', '.join(m.recipients)}\n\n"
                f"{body_text}"
            )
            full = (sig_block.lstrip() + "\n\n" + quoted) if sig else quoted
            self._txt_body.setPlainText(full)
            self._move_cursor_top()

    def _move_cursor_top(self) -> None:
        cursor = self._txt_body.textCursor()
        cursor.setPosition(0)
        self._txt_body.setTextCursor(cursor)

    # ------------------------------------------------------------------
    # Send
    # ------------------------------------------------------------------

    def _send(self) -> None:
        to      = self._txt_to.text().strip()
        cc      = self._txt_cc.text().strip() if hasattr(self, "_txt_cc") else ""
        bcc     = self._txt_bcc.text().strip() if hasattr(self, "_txt_bcc") else ""
        subject = self._txt_subject.text().strip()
        body    = self._txt_body.toPlainText()
        paths   = self._attach_paths or None

        if self._mode in ("new", "forward") and not to:
            QMessageBox.warning(self, "Envoi", "Le destinataire est obligatoire.")
            return

        self._set_sending(True)

        if self._mode == "new":
            worker = _SendWorker(self._ews.send_new, to, subject, body, cc, bcc, paths)
        elif self._mode == "reply":
            worker = _SendWorker(
                self._ews.send_reply,
                self._mail.subject_display, self._mail.sender_email,
                body, cc, paths,
            )
        elif self._mode == "reply_all":
            worker = _SendWorker(
                self._ews.send_reply_all,
                self._mail.subject_display, self._mail.sender_email,
                self._mail.recipients, body, paths,
            )
        else:  # forward
            worker = _SendWorker(
                self._ews.send_forward,
                self._mail.subject_display, to, body, cc, paths,
            )

        self._workers.append(worker)
        worker.signals.finished.connect(lambda: self._on_sent_finished(worker))
        worker.signals.error.connect(self._on_sent_error)
        QThreadPool.globalInstance().start(worker)

    def _on_sent_finished(self, worker: _SendWorker) -> None:
        if worker in self._workers:
            self._workers.remove(worker)
        if self._send_had_error:
            self._send_had_error = False
            return
        self._set_sending(False)
        QMessageBox.information(self, "Exchange", "Message envoyé.")
        self.accept()

    def _on_sent_error(self, msg: str) -> None:
        self._send_had_error = True
        self._set_sending(False)
        QMessageBox.critical(self, "Erreur d'envoi", f"Impossible d'envoyer :\n{msg}")

    def _set_sending(self, sending: bool) -> None:
        self._btn_send.setEnabled(not sending)
        self._btn_cancel.setEnabled(not sending)
        self._btn_attach.setEnabled(not sending)
        self._progress.setVisible(sending)
        self._btn_send.setText("Envoi en cours…" if sending else "  ✉  Envoyer")
