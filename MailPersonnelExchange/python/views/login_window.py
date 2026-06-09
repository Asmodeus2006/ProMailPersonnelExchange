from __future__ import annotations

import json
import sys
from pathlib import Path

from PyQt6.QtCore import (
    QObject,
    QRunnable,
    QSize,
    Qt,
    QThreadPool,
    QTimer,
    pyqtSignal,
    pyqtSlot,
)
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from models.ad_user import ADUser
from services.ad_service import ADService
from services.ews_service import EwsService

# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------

class _Signals(QObject):
    result = pyqtSignal(object)
    error = pyqtSignal(str)
    finished = pyqtSignal()


class _Worker(QRunnable):
    def __init__(self, fn, *args):
        super().__init__()
        self.fn = fn
        self.args = args
        self.signals = _Signals()
        self.setAutoDelete(True)

    @pyqtSlot()
    def run(self) -> None:
        try:
            self.signals.result.emit(self.fn(*self.args))
        except Exception as exc:
            self.signals.error.emit(str(exc))
        finally:
            self.signals.finished.emit()


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_CONFIG_PATH = Path.home() / ".promed_messagerie.json"

_DEFAULTS: dict = {
    "ldap_url":     "ldap://PRO-DC02.gamba-smcf.local",
    "base_dn":      "DC=gamba-smcf,DC=local",
    "ews_url":      "https://email.promed-lab.ch/EWS/Exchange.asmx",
    "domain":       "GAMBA-SMCF",
    "signature":    "",
    "recent_users": [],
}


def _load_cfg() -> dict:
    if _CONFIG_PATH.exists():
        try:
            return {**_DEFAULTS, **json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))}
        except Exception:
            pass
    return dict(_DEFAULTS)


def _save_cfg(cfg: dict) -> None:
    _CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Avatar helpers
# ---------------------------------------------------------------------------

_COLORS = [
    "#1565c0", "#6a1b9a", "#00695c", "#2e7d32",
    "#bf360c", "#4e342e", "#37474f", "#ad1457",
    "#0277bd", "#558b2f",
]


def _color(name: str) -> str:
    return _COLORS[hash(name) % len(_COLORS)]


# ---------------------------------------------------------------------------
# Stylesheets
# ---------------------------------------------------------------------------

_RIGHT_PANEL_SS = """
    QWidget { color: #1a1a2e; background: transparent; }
    QLabel  { color: #1a1a2e; background: transparent; }
    QLabel#sectionLabel { color: #475569; font-size: 11px; text-transform: uppercase; }
    QLabel#statusLabel  { color: #64748b; }
    QLineEdit {
        background-color: #ffffff;
        color: #1a1a2e;
        border: 1.5px solid #dde5f0;
        border-radius: 8px;
        padding: 4px 10px;
        selection-background-color: #1976d2;
    }
    QLineEdit:focus { border-color: #1976d2; }
    QScrollArea { background: transparent; border: none; }
    QScrollBar:vertical {
        background: transparent; width: 6px; margin: 0;
    }
    QScrollBar::handle:vertical {
        background: #cbd5e1; border-radius: 3px; min-height: 30px;
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""

_CARD_SS = """
    QPushButton#userCard {
        background-color: #ffffff;
        border-radius: 12px;
        border: 1.5px solid #e2e8f0;
        color: #1a1a2e;
    }
    QPushButton#userCard:hover {
        border-color: #1976d2;
        background-color: #eff6ff;
    }
    QPushButton#userCard:pressed {
        background-color: #dbeafe;
    }
"""


# ---------------------------------------------------------------------------
# Config dialog
# ---------------------------------------------------------------------------

class ConfigDialog(QDialog):
    saved = pyqtSignal()

    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self._cfg = cfg
        self.setWindowTitle("Configuration du serveur")
        self.setMinimumSize(580, 360)
        self.resize(620, 380)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 20)
        root.setSpacing(14)

        title = QLabel("⚙  Configuration")
        f = title.font()
        f.setBold(True)
        f.setPointSizeF(12.0)
        title.setFont(f)
        root.addWidget(title)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        root.addWidget(sep)

        # Server fields row
        row = QHBoxLayout()
        row.setSpacing(12)

        self._txt_ldap   = QLineEdit(self._cfg.get("ldap_url", ""))
        self._txt_dn     = QLineEdit(self._cfg.get("base_dn", ""))
        self._txt_domain = QLineEdit(self._cfg.get("domain", ""))
        self._txt_ews    = QLineEdit(self._cfg.get("ews_url", ""))

        for label, widget, stretch in [
            ("Serveur LDAP", self._txt_ldap,   2),
            ("Base DN",      self._txt_dn,     2),
            ("Domaine",      self._txt_domain, 1),
            ("URL EWS",      self._txt_ews,    3),
        ]:
            col = QWidget()
            cl = QVBoxLayout(col)
            cl.setContentsMargins(0, 0, 0, 0)
            cl.setSpacing(3)
            lbl = QLabel(label)
            lbl.setObjectName("fieldLabel")
            cl.addWidget(lbl)
            widget.setFixedHeight(32)
            cl.addWidget(widget)
            row.addWidget(col, stretch=stretch)

        root.addLayout(row)

        # Signature field
        sig_lbl = QLabel("Signature email")
        sig_lbl.setObjectName("fieldLabel")
        root.addWidget(sig_lbl)

        self._txt_sig = QTextEdit()
        self._txt_sig.setPlaceholderText(
            "Cordialement,\nPrénom Nom\nFonction  |  Promed"
        )
        self._txt_sig.setPlainText(self._cfg.get("signature", ""))
        self._txt_sig.setFixedHeight(80)
        self._txt_sig.setStyleSheet(
            "QTextEdit{border:1px solid #d0d8e8;border-radius:6px;padding:4px 8px;}"
        )
        root.addWidget(self._txt_sig)

        root.addStretch()

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_cancel = QPushButton("Annuler")
        btn_cancel.setFlat(True)
        btn_cancel.setFixedHeight(34)
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        btn_save = QPushButton("  Enregistrer")
        btn_save.setFixedHeight(34)
        btn_save.setObjectName("btnPrimary")
        btn_save.clicked.connect(self._save)
        btn_row.addWidget(btn_save)
        root.addLayout(btn_row)

    def _save(self) -> None:
        self._cfg.update({
            "ldap_url":  self._txt_ldap.text().strip(),
            "base_dn":   self._txt_dn.text().strip(),
            "domain":    self._txt_domain.text().strip(),
            "ews_url":   self._txt_ews.text().strip(),
            "signature": self._txt_sig.toPlainText(),
        })
        _save_cfg(self._cfg)
        self.saved.emit()
        self.accept()


# ---------------------------------------------------------------------------
# User card
# ---------------------------------------------------------------------------

class _UserCard(QPushButton):
    def __init__(self, user: ADUser, size: int = 150, parent=None):
        super().__init__(parent)
        self.user = user
        self.setFixedSize(size, int(size * 0.93))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("userCard")
        self.setStyleSheet(_CARD_SS)

        av_size = max(38, int(size * 0.34))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, int(size * 0.10), 8, int(size * 0.08))
        layout.setSpacing(7)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        av = QLabel(user.initials)
        av.setFixedSize(av_size, av_size)
        av.setAlignment(Qt.AlignmentFlag.AlignCenter)
        av.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        av.setStyleSheet(
            f"QLabel {{ background-color: {_color(user.display_name)};"
            f" color: #ffffff; border-radius: {av_size // 2}px;"
            " font-size: 15px; font-weight: bold; border: none; }}"
        )
        layout.addWidget(av, alignment=Qt.AlignmentFlag.AlignCenter)

        name = QLabel(user.display_name)
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name.setWordWrap(True)
        name.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        name.setStyleSheet("color: #1e293b; font-size: 9pt; font-weight: 600;")
        layout.addWidget(name)


# ---------------------------------------------------------------------------
# Password dialog
# ---------------------------------------------------------------------------

class PasswordDialog(QDialog):
    def __init__(self, user: ADUser, ews: EwsService, cfg: dict, parent=None):
        super().__init__(parent)
        self._user = user
        self._ews = ews
        self._cfg = cfg
        self._had_error = False

        self.setWindowTitle("Connexion")
        self.setFixedSize(400, 320)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 24)
        root.setSpacing(12)

        top = QHBoxLayout()
        top.setSpacing(16)

        av = QLabel(self._user.initials)
        av.setFixedSize(58, 58)
        av.setAlignment(Qt.AlignmentFlag.AlignCenter)
        av.setStyleSheet(
            f"QLabel {{ background-color: {_color(self._user.display_name)};"
            " color: #fff; border-radius: 29px; font-size: 20px; font-weight: bold; }}"
        )
        top.addWidget(av)

        col = QVBoxLayout()
        col.setSpacing(3)
        n = QLabel(self._user.display_name)
        f = n.font()
        f.setBold(True)
        f.setPointSizeF(12.5)
        n.setFont(f)
        col.addWidget(n)
        e = QLabel(self._user.email)
        e.setObjectName("metaLabel")
        col.addWidget(e)
        col.addStretch()
        top.addLayout(col)
        top.addStretch()
        root.addLayout(top)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        root.addWidget(sep)

        pwd_lbl = QLabel("Mot de passe")
        pwd_lbl.setObjectName("fieldLabel")
        root.addWidget(pwd_lbl)

        self._txt_pwd = QLineEdit()
        self._txt_pwd.setEchoMode(QLineEdit.EchoMode.Password)
        self._txt_pwd.setFixedHeight(38)
        self._txt_pwd.setPlaceholderText("••••••••")
        self._txt_pwd.returnPressed.connect(self._do_connect)
        root.addWidget(self._txt_pwd)

        self._lbl_err = QLabel("")
        self._lbl_err.setStyleSheet("color: #ef5350; font-size: 11px;")
        self._lbl_err.hide()
        root.addWidget(self._lbl_err)

        self._bar = QProgressBar()
        self._bar.setMaximum(0)
        self._bar.setFixedHeight(3)
        self._bar.setTextVisible(False)
        self._bar.hide()
        root.addWidget(self._bar)

        root.addStretch()

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._btn_cancel = QPushButton("Annuler")
        self._btn_cancel.setFixedHeight(34)
        self._btn_cancel.setFlat(True)
        self._btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(self._btn_cancel)

        self._btn_ok = QPushButton("  Se connecter")
        self._btn_ok.setFixedSize(140, 36)
        self._btn_ok.setObjectName("btnPrimary")
        self._btn_ok.clicked.connect(self._do_connect)
        btn_row.addWidget(self._btn_ok)
        root.addLayout(btn_row)

    def _do_connect(self) -> None:
        pwd = self._txt_pwd.text()
        if not pwd:
            self._show_err("Mot de passe requis.")
            return
        self._lbl_err.hide()
        self._had_error = False
        self._set_busy(True)

        worker = _Worker(
            self._ews.connect,
            self._user.email,
            self._user.sam_account_name,
            pwd,
            self._cfg["domain"],
            self._cfg["ews_url"],
        )
        worker.signals.result.connect(lambda _: self.accept())
        worker.signals.error.connect(self._on_err)
        worker.signals.finished.connect(lambda: self._set_busy(False))
        QThreadPool.globalInstance().start(worker)

    def _on_err(self, msg: str) -> None:
        self._had_error = True
        self._show_err(f"Connexion refusée : {msg[:70]}")

    def _show_err(self, msg: str) -> None:
        self._lbl_err.setText(msg)
        self._lbl_err.show()

    def _set_busy(self, busy: bool) -> None:
        self._btn_ok.setEnabled(not busy)
        self._btn_cancel.setEnabled(not busy)
        self._txt_pwd.setEnabled(not busy)
        self._bar.setVisible(busy)
        self._btn_ok.setText("Connexion…" if busy else "  Se connecter")


# ---------------------------------------------------------------------------
# LoginWindow
# ---------------------------------------------------------------------------

class LoginWindow(QMainWindow):
    authenticated = pyqtSignal(object, str)

    def __init__(self) -> None:
        super().__init__()
        self._ad = ADService()
        self._ews = EwsService()
        self._users: list[ADUser] = []
        self._cfg = _load_cfg()

        self.setWindowTitle("Promed Messagerie")
        self.setMinimumSize(960, 640)
        self.resize(1140, 780)

        self._build_ui()
        QTimer.singleShot(200, self._load_users)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        main = QHBoxLayout(central)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        main.addWidget(self._build_left_panel())
        main.addWidget(self._build_right_panel(), stretch=1)

    # -- Left brand panel -----------------------------------------------

    def _build_left_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("leftPanel")
        panel.setFixedWidth(300)
        panel.setStyleSheet(
            "#leftPanel {"
            "  background: qlineargradient(x1:0,y1:0,x2:0.4,y2:1,"
            "      stop:0 #1a3a8f, stop:0.55 #0d1f4e, stop:1 #090f1e);"
            "  border: none;"
            "}"
        )

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(36, 48, 36, 36)
        layout.setSpacing(0)

        # Logo
        _res_base = Path(sys._MEIPASS) if hasattr(sys, "_MEIPASS") else Path(__file__).parent.parent
        _logo_path = _res_base / "ressources" / "logo_promed.png"
        lbl_logo = QLabel()
        pix = QPixmap(str(_logo_path))
        if not pix.isNull():
            lbl_logo.setPixmap(
                pix.scaledToHeight(48, Qt.TransformationMode.SmoothTransformation)
            )
        layout.addWidget(lbl_logo)

        layout.addSpacing(24)

        # App name
        app_name = QLabel("Promed\nMessagerie")
        f = app_name.font()
        f.setPointSizeF(22.0)
        f.setBold(True)
        app_name.setFont(f)
        app_name.setStyleSheet("color: #ffffff; line-height: 1.2;")
        layout.addWidget(app_name)

        layout.addSpacing(12)

        tagline = QLabel("Messagerie Exchange\nprofessionnelle")
        tagline.setStyleSheet("color: rgba(255,255,255,0.55); font-size: 12px;")
        layout.addWidget(tagline)

        layout.addStretch()

        # Bottom hint
        hint = QLabel("Cliquez sur votre nom\npour vous connecter.")
        hint.setStyleSheet(
            "color: rgba(255,255,255,0.35); font-size: 11px; line-height: 1.5;"
        )
        layout.addWidget(hint)

        return panel

    # -- Right content panel --------------------------------------------

    def _build_right_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("rightPanel")
        panel.setStyleSheet(
            "QWidget#rightPanel { background-color: #f1f5fb; border: none; }"
        )

        outer = QVBoxLayout(panel)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Top bar with ⚙ button ────────────────────────────────────
        top_bar = QWidget()
        top_bar.setFixedHeight(52)
        top_bar.setStyleSheet("background: transparent;")
        tb_layout = QHBoxLayout(top_bar)
        tb_layout.setContentsMargins(40, 0, 20, 0)
        tb_layout.addStretch()

        btn_cfg = QPushButton("⚙")
        btn_cfg.setFixedSize(34, 34)
        btn_cfg.setFlat(True)
        btn_cfg.setToolTip("Configuration du serveur")
        btn_cfg.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cfg.setStyleSheet(
            "QPushButton { color: #94a3b8; font-size: 17px; border-radius: 6px;"
            "               background: transparent; }"
            "QPushButton:hover { color: #1976d2; background: #e0eaff; }"
        )
        btn_cfg.clicked.connect(self._open_config)
        tb_layout.addWidget(btn_cfg)
        outer.addWidget(top_bar)

        # ── Scrollable content ───────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { background: transparent; width: 6px; margin: 0; }"
            "QScrollBar::handle:vertical { background: #cbd5e1; border-radius: 3px; min-height: 30px; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
        )

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        cl = QVBoxLayout(content)
        cl.setContentsMargins(40, 8, 40, 40)
        cl.setSpacing(24)

        # Greeting
        greeting = QLabel("Bonjour,\nqui êtes-vous ?")
        f = greeting.font()
        f.setPointSizeF(24.0)
        f.setBold(True)
        greeting.setFont(f)
        greeting.setStyleSheet("color: #0f172a; line-height: 1.2;")
        cl.addWidget(greeting)

        # Status
        self._lbl_status = QLabel("Chargement de l'annuaire…")
        self._lbl_status.setObjectName("statusLabel")
        self._lbl_status.setStyleSheet("color: #64748b; font-size: 12px;")
        cl.addWidget(self._lbl_status)

        self._bar = QProgressBar()
        self._bar.setMaximum(0)
        self._bar.setFixedHeight(3)
        self._bar.setTextVisible(False)
        cl.addWidget(self._bar)

        # Recent users
        self._recent_section = QWidget()
        self._recent_section.setStyleSheet("background: transparent;")
        self._recent_section.hide()
        rl = QVBoxLayout(self._recent_section)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(12)

        lbl_r = QLabel("CONNEXIONS RÉCENTES")
        lbl_r.setStyleSheet(
            "color: #64748b; font-size: 10px; font-weight: 700; letter-spacing: 1px;"
        )
        rl.addWidget(lbl_r)

        self._recent_row = QHBoxLayout()
        self._recent_row.setSpacing(12)
        self._recent_row.addStretch()
        rl.addLayout(self._recent_row)
        cl.addWidget(self._recent_section)

        # All users
        self._all_section = QWidget()
        self._all_section.setStyleSheet("background: transparent;")
        self._all_section.hide()
        al = QVBoxLayout(self._all_section)
        al.setContentsMargins(0, 0, 0, 0)
        al.setSpacing(12)

        lbl_a = QLabel("TOUS LES UTILISATEURS")
        lbl_a.setStyleSheet(
            "color: #64748b; font-size: 10px; font-weight: 700; letter-spacing: 1px;"
        )
        al.addWidget(lbl_a)

        self._txt_search = QLineEdit()
        self._txt_search.setPlaceholderText("\U0001f50d  Rechercher un collaborateur…")
        self._txt_search.setClearButtonEnabled(True)
        self._txt_search.setFixedHeight(38)
        self._txt_search.setStyleSheet(
            "QLineEdit { background: #ffffff; color: #1e293b;"
            "            border: 1.5px solid #dde5f0; border-radius: 8px;"
            "            padding: 4px 10px; }"
            "QLineEdit:focus { border-color: #1976d2; }"
        )
        self._txt_search.textChanged.connect(self._filter_users)
        al.addWidget(self._txt_search)

        self._cards_container = QWidget()
        self._cards_container.setStyleSheet("background: transparent;")
        self._grid = QGridLayout(self._cards_container)
        self._grid.setSpacing(12)
        self._grid.setContentsMargins(0, 0, 0, 0)
        al.addWidget(self._cards_container)
        cl.addWidget(self._all_section)

        cl.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll, stretch=1)

        return panel

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------

    def _open_config(self) -> None:
        dlg = ConfigDialog(self._cfg, parent=self)
        dlg.saved.connect(self._on_config_saved)
        dlg.exec()

    def _on_config_saved(self) -> None:
        self._cfg = _load_cfg()
        self._load_users()

    # ------------------------------------------------------------------
    # Load users
    # ------------------------------------------------------------------

    def _load_users(self) -> None:
        ldap_url = self._cfg.get("ldap_url", "")
        base_dn  = self._cfg.get("base_dn", "")
        if not ldap_url or not base_dn:
            self._lbl_status.setText("Configurez le serveur via le bouton ⚙.")
            return

        self._bar.show()
        self._lbl_status.setText("Chargement de l'annuaire Active Directory…")
        self._recent_section.hide()
        self._all_section.hide()

        worker = _Worker(self._ad.query_users, ldap_url, base_dn)
        worker.signals.result.connect(self._on_users_loaded)
        worker.signals.error.connect(self._on_load_error)
        worker.signals.finished.connect(lambda: self._bar.hide())
        QThreadPool.globalInstance().start(worker)

    def _on_users_loaded(self, users: list[ADUser]) -> None:
        self._users = users
        self._lbl_status.setText(
            f"{len(users)} collaborateur(s) — cliquez sur votre nom."
        )
        self._populate_recent()
        self._populate_grid(users)
        self._all_section.show()

    def _on_load_error(self, msg: str) -> None:
        self._lbl_status.setText(f"Erreur AD : {msg[:120]}")

    # ------------------------------------------------------------------
    # Recent users
    # ------------------------------------------------------------------

    def _populate_recent(self) -> None:
        recent_data: list[dict] = self._cfg.get("recent_users", [])
        if not recent_data:
            self._recent_section.hide()
            return

        while self._recent_row.count() > 1:
            item = self._recent_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        email_map = {u.email.lower(): u for u in self._users}
        added = 0
        for rd in recent_data[:5]:
            email = rd.get("email", "").lower()
            user = email_map.get(email) or ADUser(
                display_name=rd.get("display_name", email),
                email=rd.get("email", email),
                sam_account_name=rd.get("sam_account_name", ""),
            )
            card = _UserCard(user, size=130)
            card.clicked.connect(lambda _c, u=user: self._on_card_clicked(u))
            self._recent_row.insertWidget(added, card)
            added += 1

        if added:
            self._recent_section.show()

    def _save_recent_user(self, user: ADUser) -> None:
        recent: list[dict] = self._cfg.get("recent_users", [])
        entry = {
            "display_name":     user.display_name,
            "email":            user.email,
            "sam_account_name": user.sam_account_name,
        }
        recent = [r for r in recent if r.get("email") != user.email]
        recent.insert(0, entry)
        self._cfg["recent_users"] = recent[:5]
        _save_cfg(self._cfg)

    # ------------------------------------------------------------------
    # Grid
    # ------------------------------------------------------------------

    def _filter_users(self, query: str) -> None:
        q = query.strip().lower()
        filtered = (
            [u for u in self._users if q in u.display_name.lower() or q in u.email.lower()]
            if q else self._users
        )
        self._populate_grid(filtered)

    def _populate_grid(self, users: list[ADUser]) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        cols = 6
        for i, user in enumerate(users):
            card = _UserCard(user, size=148)
            card.clicked.connect(lambda _c, u=user: self._on_card_clicked(u))
            self._grid.addWidget(card, i // cols, i % cols)

        if users:
            last = len(users) % cols
            if last:
                spacer = QWidget()
                spacer.setSizePolicy(
                    QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
                )
                self._grid.addWidget(spacer, len(users) // cols, last, 1, cols - last)

    # ------------------------------------------------------------------
    # Card click
    # ------------------------------------------------------------------

    def _on_card_clicked(self, user: ADUser) -> None:
        dlg = PasswordDialog(user, self._ews, self._cfg, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._save_recent_user(user)
            self.authenticated.emit(self._ews, user.email)

    def closeEvent(self, event) -> None:
        QApplication.quit()
