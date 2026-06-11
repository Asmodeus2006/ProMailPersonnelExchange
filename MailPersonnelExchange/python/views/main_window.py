from __future__ import annotations

import os
import sys
from pathlib import Path

from PyQt6.QtCore import (
    QObject,
    QPoint,
    QRunnable,
    QSize,
    Qt,
    QThreadPool,
    pyqtSignal,
    pyqtSlot,
)
from PyQt6.QtGui import QKeySequence, QPixmap, QShortcut, QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStatusBar,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)
from qt_material import apply_stylesheet

from models.mail_item import MailItem
from services.ews_service import EwsService
from updater import UpdateChecker, UpdateDownloader, run_installer_and_quit
from version import APP_VERSION
from views.compose_window import ComposeWindow
from views.mail_delegate import MailDelegate


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------

class _Signals(QObject):
    result   = pyqtSignal(object)
    error    = pyqtSignal(str)
    finished = pyqtSignal()


class _Worker(QRunnable):
    def __init__(self, fn, *args):
        super().__init__()
        self.fn   = fn
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
# Stylesheets
# ---------------------------------------------------------------------------

_HEADER_SS = (
    "QWidget#mainHeader{"
    "background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
    "stop:0 #090f1e,stop:0.55 #0d1f4e,stop:1 #1a3a8f);"
    "border:none;}"
)

_LIST_SS = """
    QFrame#mailListPanel {
        background: #f0f4f9;
        border-right: 1px solid #dde5f0;
    }
    QWidget#listHeader {
        background: #e8eef8;
        border-bottom: 1px solid #d4ddef;
    }
    QWidget#listHeader QLabel { color: #1e293b; background: transparent; }
    QFrame#mailListPanel QLineEdit {
        background: #ffffff;
        color: #1e293b;
        border: 1.5px solid #d4ddef;
        border-radius: 8px;
        padding: 4px 10px;
    }
    QFrame#mailListPanel QLineEdit:focus { border-color: #1976d2; }
    QListView { background: #ffffff; border: none; outline: none; }
    QListView::item { border: none; padding: 0; }
    QListView::item:selected { background: #dbeafe; }
    QScrollBar:vertical {
        background: transparent; width: 5px; margin: 0;
    }
    QScrollBar::handle:vertical {
        background: #c4cfe0; border-radius: 2px; min-height: 24px;
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""

_ACTION_SS = """
    QPushButton {
        background: #ffffff;
        color: #374151;
        border: 1px solid #d1dae8;
        border-radius: 6px;
        padding: 0 13px;
        font-size: 12px;
        text-transform: none;
    }
    QPushButton:hover    { background: #eef3ff; border-color: #1976d2; color: #1565c0; }
    QPushButton:pressed  { background: #dbeafe; }
    QPushButton:disabled { background: #f4f6fb; color: #c8d3e4; border-color: #edf0f6; }
"""

_DELETE_SS = """
    QPushButton {
        background: #fff1f2;
        color: #dc2626;
        border: 1px solid #fecaca;
        border-radius: 6px;
        padding: 0 13px;
        font-size: 12px;
        text-transform: none;
    }
    QPushButton:hover    { background: #fee2e2; border-color: #ef4444; }
    QPushButton:pressed  { background: #fecaca; }
    QPushButton:disabled { background: #f4f6fb; color: #c8d3e4; border-color: #edf0f6; }
"""

_SENDER_CARD_SS = """
    QFrame#senderCard {
        background: #f6f9ff;
        border: 1px solid #dde8f5;
        border-radius: 8px;
    }
    QLabel           { background: transparent; color: #1e293b; }
    QLabel#metaLabel { color: #64748b; font-size: 11px; }
"""

# (key, sidebar_label, panel_label)
_FOLDERS: list[tuple[str, str, str]] = [
    ("inbox",  "📥  Boîte de réception", "Boîte de réception"),
    ("sent",   "📤  Éléments envoyés",   "Éléments envoyés"),
    ("drafts", "📝  Brouillons",          "Brouillons"),
    ("trash",  "🗑  Éléments supprimés", "Éléments supprimés"),
    ("junk",   "🚫  Indésirables",        "Indésirables"),
]

_SIDEBAR_SS = """
    QWidget#folderSidebar {
        background: #2a3f60;
        border-right: 1px solid #3a5278;
    }
    QLabel#sidebarTitle {
        color: #90a8c8;
        font-size: 10px;
        padding: 0 16px;
    }
    QListWidget {
        background: transparent;
        border: none;
        color: #ffffff;
        font-size: 13px;
        outline: none;
        padding: 4px 0;
    }
    QListWidget::item {
        padding: 9px 16px;
        border-radius: 6px;
        margin: 1px 8px;
        color: #ffffff;
    }
    QListWidget::item:hover {
        background: rgba(255,255,255,0.07);
        color: #ffffff;
    }
    QListWidget::item:selected {
        background: rgba(25, 118, 210, 0.22);
        color: #93c5fd;
        border-left: 3px solid #1976d2;
        padding-left: 13px;
    }
    QScrollBar:vertical { width: 0; }
"""


# ---------------------------------------------------------------------------
# MainWindow
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    logout_requested = pyqtSignal()

    def __init__(self, ews: EwsService, user_email: str = "", ad_users: list | None = None) -> None:
        super().__init__()
        self._ews              = ews
        self._user_email       = user_email
        self._ad_users: list   = ad_users or []
        self._current_folder   = "inbox"
        self._all_items:     list[MailItem] = []
        self._visible_items: list[MailItem] = []
        self._current_full_mail: MailItem | None = None
        self._workers:    list[_Worker] = []

        self.setWindowTitle("Promed Messagerie")
        self.setMinimumSize(1024, 700)
        self.resize(1360, 880)

        self._build_central()
        self._build_statusbar()
        self._wire_events()
        self._set_action_buttons(False)

        self._start_load_folder()
        self._start_update_check()

    # ------------------------------------------------------------------
    # Mise à jour automatique
    # ------------------------------------------------------------------

    def _build_update_banner(self) -> QWidget:
        self._update_banner = QFrame()
        self._update_banner.setObjectName("updateBanner")
        self._update_banner.setFixedHeight(40)
        self._update_banner.setStyleSheet(
            "QFrame#updateBanner{background:#fef3c7;border-bottom:1px solid #f59e0b;}"
        )
        hl = QHBoxLayout(self._update_banner)
        hl.setContentsMargins(16, 0, 16, 0)
        hl.setSpacing(12)

        self._lbl_update = QLabel()
        self._lbl_update.setStyleSheet("color:#92400e; font-weight:bold; background:transparent;")
        hl.addWidget(self._lbl_update)

        self._update_dl_bar = QProgressBar()
        self._update_dl_bar.setFixedWidth(160)
        self._update_dl_bar.setFixedHeight(14)
        self._update_dl_bar.setTextVisible(False)
        self._update_dl_bar.setStyleSheet(
            "QProgressBar{background:#fde68a;border-radius:7px;border:none;}"
            "QProgressBar::chunk{background:#f59e0b;border-radius:7px;}"
        )
        self._update_dl_bar.hide()
        hl.addWidget(self._update_dl_bar)

        hl.addStretch()

        self._btn_do_update = QPushButton("⬇  Mettre à jour")
        self._btn_do_update.setFixedHeight(28)
        self._btn_do_update.setStyleSheet(
            "QPushButton{background:#f59e0b;color:#fff;border:none;"
            "border-radius:5px;padding:0 14px;font-weight:bold;text-transform:none;}"
            "QPushButton:hover{background:#d97706;}"
            "QPushButton:disabled{background:#fcd34d;color:#fff;}"
        )
        hl.addWidget(self._btn_do_update)

        self._update_banner.hide()
        return self._update_banner

    def _start_update_check(self) -> None:
        checker = UpdateChecker(APP_VERSION)
        checker.signals.found.connect(self._on_update_found)
        checker.signals.debug.connect(self._set_status)
        QThreadPool.globalInstance().start(checker)

    @pyqtSlot(str, str)
    def _on_update_found(self, version: str, url: str) -> None:
        self._lbl_update.setText(f"✨  Mise à jour disponible — v{version}")
        try:
            self._btn_do_update.clicked.disconnect()
        except RuntimeError:
            pass
        self._btn_do_update.clicked.connect(lambda: self._download_update(url))
        self._update_banner.show()

    def _download_update(self, url: str) -> None:
        self._btn_do_update.setEnabled(False)
        self._btn_do_update.setText("Téléchargement...")
        self._update_dl_bar.setMaximum(100)
        self._update_dl_bar.setValue(0)
        self._update_dl_bar.show()

        dl = UpdateDownloader(url)
        dl.signals.progress.connect(self._update_dl_bar.setValue)
        dl.signals.done.connect(self._on_update_ready)
        dl.signals.error.connect(self._on_update_error)
        QThreadPool.globalInstance().start(dl)

    @pyqtSlot(str)
    def _on_update_ready(self, path: str) -> None:
        self._btn_do_update.setText("Installation en cours…")
        run_installer_and_quit(path, QApplication.instance().quit)

    @pyqtSlot(str)
    def _on_update_error(self, msg: str) -> None:
        self._btn_do_update.setEnabled(True)
        self._btn_do_update.setText("⬇  Réessayer")
        self._lbl_update.setText("Erreur de téléchargement — vérifiez votre connexion")

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------

    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setObjectName("mainHeader")
        header.setFixedHeight(58)

        hl = QHBoxLayout(header)
        hl.setContentsMargins(16, 0, 16, 0)
        hl.setSpacing(8)

        # Header pleine largeur — logo tout à gauche
        header.setStyleSheet(
            "QWidget#mainHeader{"
            "background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #1e3a8a,stop:0.55 #2563b0,stop:1 #3b82f6);"
            "border:none;}"
        )

        _res_base = Path(sys._MEIPASS) if hasattr(sys, "_MEIPASS") else Path(__file__).parent.parent
        _logo_path = _res_base / "ressources" / "logo_promed.png"
        lbl_logo = QLabel()
        lbl_logo.setStyleSheet("background:transparent;")
        pix = QPixmap(str(_logo_path))
        if not pix.isNull():
            lbl_logo.setPixmap(
                pix.scaledToHeight(34, Qt.TransformationMode.SmoothTransformation)
            )
        hl.addWidget(lbl_logo)

        lbl_title = QLabel("Promed Messagerie")
        f = lbl_title.font()
        f.setBold(True)
        f.setPointSizeF(f.pointSizeF() + 2)
        lbl_title.setFont(f)
        lbl_title.setStyleSheet("color:#ffffff; background:transparent; padding-left:4px;")
        hl.addWidget(lbl_title)

        lbl_version = QLabel(f"v{APP_VERSION}")
        lbl_version.setStyleSheet(
            "color:rgba(255,255,255,0.55); font-size:11px; background:transparent; padding-left:4px;"
        )
        hl.addWidget(lbl_version)

        hl.addStretch()

        self._lbl_conn = QLabel(
            f"●  {self._user_email}" if self._user_email else "● Connecté"
        )
        self._lbl_conn.setStyleSheet(
            "color:#6ee7b7; font-size:12px; padding:0 14px; background:transparent;"
        )
        hl.addWidget(self._lbl_conn)

        vsep = QFrame()
        vsep.setFrameShape(QFrame.Shape.VLine)
        vsep.setFixedHeight(24)
        vsep.setStyleSheet("color:rgba(255,255,255,0.22); background:transparent;")
        hl.addWidget(vsep)

        self._tb_btn_refresh = QPushButton("↻  Actualiser")
        self._tb_btn_refresh.setFixedHeight(30)
        self._tb_btn_refresh.setStyleSheet(
            "QPushButton{color:rgba(255,255,255,0.75);padding:0 10px;"
            "border-radius:5px;background:transparent;border:none;text-transform:none;}"
            "QPushButton:hover{background:rgba(255,255,255,0.12);color:#fff;}"
        )
        hl.addWidget(self._tb_btn_refresh)

        self._tb_btn_new = QPushButton("✉  Nouveau mail")
        self._tb_btn_new.setFixedHeight(32)
        self._tb_btn_new.setStyleSheet(
            "QPushButton{background:rgba(255,255,255,0.15);color:#fff;"
            "border:1px solid rgba(255,255,255,0.28);border-radius:6px;"
            "padding:0 16px;font-weight:bold;text-transform:none;}"
            "QPushButton:hover{background:rgba(255,255,255,0.24);}"
            "QPushButton:pressed{background:rgba(255,255,255,0.08);}"
        )
        hl.addWidget(self._tb_btn_new)

        self._btn_logout = QPushButton("Déconnexion")
        self._btn_logout.setFixedHeight(32)
        self._btn_logout.setStyleSheet(
            "QPushButton{color:rgba(252,165,165,0.90);padding:0 12px;"
            "border-radius:5px;background:transparent;"
            "border:1px solid rgba(252,165,165,0.30);font-size:12px;text-transform:none;}"
            "QPushButton:hover{color:#fca5a5;background:rgba(239,68,68,0.14);"
            "border-color:rgba(239,68,68,0.50);}"
        )
        hl.addWidget(self._btn_logout)

        return header

    # ------------------------------------------------------------------
    # Central widget
    # ------------------------------------------------------------------

    def _build_central(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_header())

        # Loading bar (thin, below header)
        self._progress = QProgressBar()
        self._progress.setMaximum(0)
        self._progress.setFixedHeight(3)
        self._progress.setTextVisible(False)
        self._progress.setStyleSheet(
            "QProgressBar{background:transparent;border:none;}"
            "QProgressBar::chunk{background:#1976d2;}"
        )
        self._progress.hide()
        root.addWidget(self._progress)

        # Bannière de mise à jour (cachée par défaut)
        root.addWidget(self._build_update_banner())

        # Content = folder sidebar + splitter
        content = QWidget()
        content_hl = QHBoxLayout(content)
        content_hl.setContentsMargins(0, 0, 0, 0)
        content_hl.setSpacing(0)

        content_hl.addWidget(self._build_folder_sidebar())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(6)
        splitter.setStyleSheet(
            "QSplitter::handle{background:#dde5f0;}"
            "QSplitter::handle:hover{background:#1976d2;}"
            "QSplitter::handle:pressed{background:#1565c0;}"
        )

        list_panel = self._build_mail_list_panel()
        list_panel.setMinimumWidth(220)

        preview_panel = self._build_preview_panel()
        preview_panel.setMinimumWidth(380)

        splitter.addWidget(list_panel)
        splitter.addWidget(preview_panel)
        splitter.setSizes([380, 980])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        content_hl.addWidget(splitter, stretch=1)
        root.addWidget(content, stretch=1)

    # ------------------------------------------------------------------
    # Folder sidebar (far left)
    # ------------------------------------------------------------------

    def _build_folder_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("folderSidebar")
        sidebar.setFixedWidth(195)
        sidebar.setStyleSheet(_SIDEBAR_SS)

        vl = QVBoxLayout(sidebar)
        vl.setContentsMargins(0, 14, 0, 8)
        vl.setSpacing(0)

        lbl = QLabel("DOSSIERS")
        lbl.setObjectName("sidebarTitle")
        f = lbl.font()
        f.setBold(True)
        lbl.setFont(f)
        vl.addWidget(lbl)

        vl.addSpacing(8)

        self._folder_list = QListWidget()
        self._folder_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        for key, sidebar_label, _ in _FOLDERS:
            item = QListWidgetItem(sidebar_label)
            item.setData(Qt.ItemDataRole.UserRole, key)
            self._folder_list.addItem(item)
        self._folder_list.setCurrentRow(0)
        vl.addWidget(self._folder_list, stretch=1)

        return sidebar

    def _on_folder_selected(self, row: int) -> None:
        if row < 0 or row >= len(_FOLDERS):
            return
        folder_key = _FOLDERS[row][0]
        if folder_key == self._current_folder:
            return
        self._current_folder = folder_key
        self._show_empty_preview()
        self._start_load_folder()

    # ------------------------------------------------------------------
    # Mail list panel (left)
    # ------------------------------------------------------------------

    def _build_mail_list_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("mailListPanel")
        panel.setFrameShape(QFrame.Shape.NoFrame)
        panel.setStyleSheet(_LIST_SS)

        vl = QVBoxLayout(panel)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(0)

        # Header section (folder name + search)
        lh = QWidget()
        lh.setObjectName("listHeader")
        lhl = QVBoxLayout(lh)
        lhl.setContentsMargins(14, 12, 14, 10)
        lhl.setSpacing(8)

        self._lbl_mailbox = QLabel("Boite de réception")
        f = self._lbl_mailbox.font()
        f.setBold(True)
        f.setPointSizeF(f.pointSizeF() + 1)
        self._lbl_mailbox.setFont(f)
        lhl.addWidget(self._lbl_mailbox)

        self._txt_search = QLineEdit()
        self._txt_search.setPlaceholderText("🔍  Rechercher…")
        self._txt_search.setClearButtonEnabled(True)
        self._txt_search.setFixedHeight(34)
        lhl.addWidget(self._txt_search)
        vl.addWidget(lh)

        # List view
        self._mail_model = QStandardItemModel()
        self._mail_list  = QListView()
        self._mail_list.setModel(self._mail_model)
        self._mail_list.setItemDelegate(MailDelegate(self._mail_list))
        self._mail_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._mail_list.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._mail_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._mail_list.setSpacing(0)
        self._mail_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        vl.addWidget(self._mail_list, stretch=1)

        return panel

    # ------------------------------------------------------------------
    # Preview panel (right)
    # Structure:
    #   [Action bar]        ← fixed, never scrolls
    #   [Mail header area]  ← fixed (subject + sender card), no scroll
    #   [QTextBrowser]      ← scrolls its own content, no layout jump
    # ------------------------------------------------------------------

    def _build_preview_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("previewPanel")
        panel.setFrameShape(QFrame.Shape.NoFrame)
        panel.setStyleSheet("QFrame#previewPanel{background:#ffffff;border:none;}")

        vl = QVBoxLayout(panel)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(0)

        # ── Action bar ────────────────────────────────────────────────
        ab = QWidget()
        ab.setStyleSheet("background:#f6f9ff;border-bottom:1px solid #e0e8f4;")
        abl = QHBoxLayout(ab)
        abl.setContentsMargins(20, 8, 20, 8)
        abl.setSpacing(6)

        self._btn_reply      = QPushButton("↩  Répondre")
        self._btn_reply_all  = QPushButton("↩↩  À tous")
        self._btn_forward    = QPushButton("→  Transférer")
        self._btn_toggle_read = QPushButton("☑  Lu/Non-lu")
        self._btn_delete     = QPushButton("🗑  Supprimer")

        for btn, tip in [
            (self._btn_reply,       "Ctrl+R"),
            (self._btn_reply_all,   "Ctrl+Shift+R"),
            (self._btn_forward,     "Ctrl+F"),
            (self._btn_toggle_read, "U"),
        ]:
            btn.setFixedHeight(32)
            btn.setToolTip(tip)
            btn.setStyleSheet(_ACTION_SS)

        self._btn_delete.setFixedHeight(32)
        self._btn_delete.setToolTip("Suppr")
        self._btn_delete.setStyleSheet(_DELETE_SS)

        abl.addWidget(self._btn_reply)
        abl.addWidget(self._btn_reply_all)
        abl.addWidget(self._btn_forward)
        abl.addStretch()
        abl.addWidget(self._btn_toggle_read)
        abl.addWidget(self._btn_delete)
        vl.addWidget(ab)

        # ── Empty state (shown when no mail is selected) ───────────────
        self._empty_state = self._build_empty_state()
        vl.addWidget(self._empty_state, stretch=1)

        # ── Mail header area (non-scrollable) ─────────────────────────
        self._mail_head = QWidget()
        self._mail_head.setStyleSheet("background:#ffffff;border-bottom:1px solid #e8eef7;")
        self._mail_head.hide()
        mhl = QVBoxLayout(self._mail_head)
        mhl.setContentsMargins(28, 18, 28, 14)
        mhl.setSpacing(10)

        self._lbl_subject = QLabel("")
        f = self._lbl_subject.font()
        f.setBold(True)
        f.setPointSizeF(f.pointSizeF() + 5)
        self._lbl_subject.setFont(f)
        self._lbl_subject.setWordWrap(True)
        self._lbl_subject.setStyleSheet("color:#0f172a;background:transparent;")
        mhl.addWidget(self._lbl_subject)

        self._header_card = self._build_sender_card()
        self._header_card.hide()
        mhl.addWidget(self._header_card)

        # Attachment chips (shown when mail has attachments)
        self._attach_bar = QWidget()
        self._attach_bar.setStyleSheet("background:transparent;")
        self._attach_layout = QHBoxLayout(self._attach_bar)
        self._attach_layout.setContentsMargins(0, 4, 0, 0)
        self._attach_layout.setSpacing(8)
        self._attach_bar.hide()
        mhl.addWidget(self._attach_bar)

        vl.addWidget(self._mail_head)

        # ── Body (QTextBrowser manages its own scroll) ─────────────────
        self._txt_body = QTextBrowser()
        self._txt_body.setOpenExternalLinks(True)
        self._txt_body.setFrameShape(QFrame.Shape.NoFrame)
        self._txt_body.setStyleSheet(
            "QTextBrowser{background:#ffffff;color:#1a1a1a;border:none;"
            "padding:20px 28px;"
            "font-family:'Segoe UI',Arial,sans-serif;font-size:13px;}"
        )
        self._txt_body.document().setDocumentMargin(0)
        self._txt_body.hide()
        vl.addWidget(self._txt_body, stretch=1)

        return panel

    def _build_empty_state(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background:#ffffff;")
        vl = QVBoxLayout(w)
        vl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vl.setSpacing(10)

        ico = QLabel("✉")
        ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ico.setStyleSheet("font-size:52px; color:#d1dae8; background:transparent;")
        vl.addWidget(ico)

        lbl = QLabel("Aucun message sélectionné")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(
            "color:#94a3b8; font-size:15px; font-weight:600; background:transparent;"
        )
        vl.addWidget(lbl)

        hint = QLabel("Cliquez sur un message pour afficher son contenu")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet("color:#b8c4d4; font-size:12px; background:transparent;")
        vl.addWidget(hint)

        return w

    def _build_sender_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("senderCard")
        card.setFrameShape(QFrame.Shape.NoFrame)
        card.setStyleSheet(_SENDER_CARD_SS)

        grid = QGridLayout(card)
        grid.setContentsMargins(14, 10, 14, 10)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(3)

        self._lbl_avatar = QLabel("?")
        self._lbl_avatar.setFixedSize(42, 42)
        self._lbl_avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_avatar.setStyleSheet(
            "QLabel{background:#1565c0;color:#fff;"
            "border-radius:21px;font-size:15px;font-weight:bold;border:none;}"
        )
        grid.addWidget(self._lbl_avatar, 0, 0, 2, 1, Qt.AlignmentFlag.AlignTop)

        self._lbl_sender_name = QLabel("")
        f = self._lbl_sender_name.font()
        f.setBold(True)
        f.setPointSizeF(f.pointSizeF() + 0.5)
        self._lbl_sender_name.setFont(f)
        grid.addWidget(self._lbl_sender_name, 0, 1)

        self._lbl_date_detail = QLabel("")
        self._lbl_date_detail.setObjectName("metaLabel")
        self._lbl_date_detail.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        grid.addWidget(self._lbl_date_detail, 0, 2)

        self._lbl_sender_email_lbl = QLabel("")
        self._lbl_sender_email_lbl.setObjectName("metaLabel")
        grid.addWidget(self._lbl_sender_email_lbl, 1, 1, 1, 2)

        hsep = QFrame()
        hsep.setFrameShape(QFrame.Shape.HLine)
        hsep.setStyleSheet("color:#dde8f5;")
        grid.addWidget(hsep, 2, 0, 1, 3)

        lbl_to = QLabel("À :")
        lbl_to.setObjectName("metaLabel")
        lbl_to.setFixedWidth(26)
        grid.addWidget(lbl_to, 3, 0, Qt.AlignmentFlag.AlignTop)

        self._lbl_recipients = QLabel("")
        self._lbl_recipients.setWordWrap(True)
        self._lbl_recipients.setObjectName("metaLabel")
        grid.addWidget(self._lbl_recipients, 3, 1, 1, 2)

        grid.setColumnStretch(1, 1)
        return card

    # ------------------------------------------------------------------
    # Status bar
    # ------------------------------------------------------------------

    def _build_statusbar(self) -> None:
        sb = QStatusBar()
        sb.setStyleSheet(
            "QStatusBar{background:#eef2f8;border-top:1px solid #d4ddef;}"
            "QStatusBar QLabel{color:#64748b;font-size:11px;"
            "padding:0 4px;background:transparent;}"
        )
        self.setStatusBar(sb)
        self._lbl_status = QLabel("Chargement de la boite de réception…")
        sb.addWidget(self._lbl_status)
        lbl_author = QLabel("App créée par Asmodeus")
        lbl_author.setStyleSheet("color:#94a3b8; font-size:10px; padding:0 8px; background:transparent;")
        sb.addPermanentWidget(lbl_author)

    # ------------------------------------------------------------------
    # Wire events + shortcuts
    # ------------------------------------------------------------------

    def _wire_events(self) -> None:
        self._btn_logout.clicked.connect(self._logout)
        self._tb_btn_refresh.clicked.connect(self._start_load_folder)
        self._folder_list.currentRowChanged.connect(self._on_folder_selected)
        self._txt_search.textChanged.connect(self._apply_filter)
        self._tb_btn_new.clicked.connect(lambda: self._open_compose("new"))

        self._btn_reply.clicked.connect(lambda: self._open_compose("reply"))
        self._btn_reply_all.clicked.connect(lambda: self._open_compose("reply_all"))
        self._btn_forward.clicked.connect(lambda: self._open_compose("forward"))
        self._btn_delete.clicked.connect(self._delete_selected)
        self._btn_toggle_read.clicked.connect(self._toggle_read_selected)

        sel = self._mail_list.selectionModel()
        sel.selectionChanged.connect(self._on_selection_changed)
        self._mail_list.customContextMenuRequested.connect(self._show_context_menu)

        QShortcut(QKeySequence("Ctrl+N"), self).activated.connect(
            lambda: self._open_compose("new")
        )
        QShortcut(QKeySequence("Ctrl+R"), self).activated.connect(
            lambda: self._open_compose("reply")
        )
        QShortcut(QKeySequence("Ctrl+Shift+R"), self).activated.connect(
            lambda: self._open_compose("reply_all")
        )
        QShortcut(QKeySequence("Ctrl+F"), self).activated.connect(
            lambda: self._open_compose("forward")
        )
        QShortcut(QKeySequence("Delete"), self).activated.connect(self._delete_selected)
        QShortcut(QKeySequence("U"), self).activated.connect(self._toggle_read_selected)

    # ------------------------------------------------------------------
    # Context menu
    # ------------------------------------------------------------------

    def _show_context_menu(self, pos: QPoint) -> None:
        idx = self._mail_list.indexAt(pos)
        if not idx.isValid():
            return
        row  = idx.row()
        mail = self._visible_items[row] if row < len(self._visible_items) else None

        menu = QMenu(self)
        menu.addAction("↩  Répondre",          lambda: self._open_compose("reply"))
        menu.addAction("↩↩  Répondre à tous",  lambda: self._open_compose("reply_all"))
        menu.addAction("→  Transférer",         lambda: self._open_compose("forward"))
        menu.addSeparator()
        if mail is not None:
            if mail.is_unread:
                menu.addAction("✓  Marquer comme lu",     lambda: self._mark_read(mail, True))
            else:
                menu.addAction("○  Marquer comme non-lu", lambda: self._mark_read(mail, False))
        menu.addSeparator()
        menu.addAction("🗑  Supprimer", self._delete_selected)
        menu.exec(self._mail_list.viewport().mapToGlobal(pos))

    # ------------------------------------------------------------------
    # Logout
    # ------------------------------------------------------------------

    def _logout(self) -> None:
        self._ews.disconnect()
        self.logout_requested.emit()

    # ------------------------------------------------------------------
    # Inbox
    # ------------------------------------------------------------------

    def _start_load_folder(self) -> None:
        panel_label = next(
            (pl for key, _, pl in _FOLDERS if key == self._current_folder),
            "Dossier"
        )
        self._run(
            self._ews.load_folder,
            self._current_folder,
            on_result=self._on_folder_loaded,
            on_error_prefix="Chargement",
            busy_msg=f"Chargement de {panel_label.lower()}…",
            show_progress=True,
        )

    def _on_folder_loaded(self, items: list[MailItem]) -> None:
        self._all_items = items
        self._apply_filter()
        self._refresh_folder_label()
        count = len(items)
        self._set_status(f"{count} message(s) chargé(s).")

    def _refresh_folder_label(self) -> None:
        panel_label = next(
            (pl for key, _, pl in _FOLDERS if key == self._current_folder),
            "Dossier"
        )
        count = len(self._all_items)
        unread = sum(1 for m in self._all_items if m.is_unread)
        if unread:
            self._lbl_mailbox.setText(
                f"{panel_label}  ·  {unread} non lu{'s' if unread > 1 else ''}  /  {count}"
            )
        else:
            self._lbl_mailbox.setText(f"{panel_label}  ·  {count}")

    def _apply_filter(self) -> None:
        query = self._txt_search.text().strip().lower()
        filtered = (
            [m for m in self._all_items
             if query in m.subject_display.lower() or query in m.sender_display.lower()]
            if query else list(self._all_items)
        )
        self._visible_items = filtered
        self._mail_model.clear()
        for mail in filtered:
            item = QStandardItem()
            item.setData(mail, Qt.ItemDataRole.UserRole)
            item.setEditable(False)
            self._mail_model.appendRow(item)
        self._set_status(
            f"{len(filtered)} résultat(s) pour « {query} »."
            if query else f"{len(filtered)} message(s) affiché(s)."
        )

    # ------------------------------------------------------------------
    # Selection & preview
    # ------------------------------------------------------------------

    def _on_selection_changed(self) -> None:
        selected = self._mail_list.selectionModel().selectedIndexes()
        self._set_action_buttons(bool(selected))
        if not selected:
            self._show_empty_preview()
            return
        idx = selected[0].row()
        if idx < 0 or idx >= len(self._visible_items):
            return

        mail = self._visible_items[idx]
        self._lbl_subject.setText(mail.subject_display)
        self._header_card.hide()
        self._attach_bar.hide()
        self._empty_state.hide()
        self._mail_head.show()
        self._txt_body.clear()
        self._txt_body.hide()

        # Load body — no progress bar shown (avoids flicker on every click)
        self._run(
            self._ews.load_body,
            mail.item_id,
            mail.change_key,
            on_result=self._on_body_loaded,
            on_error_prefix="Lecture du mail",
            busy_msg="",
            show_progress=False,
        )

    def _on_body_loaded(self, mail: MailItem) -> None:
        self._current_full_mail = mail
        if mail.is_unread:
            list_item = next((m for m in self._visible_items if m.item_id == mail.item_id), None)
            if list_item:
                self._mark_read(list_item, True)
        self._lbl_subject.setText(mail.subject_display)

        letter = (mail.sender_display[0] if mail.sender_display else "?").upper()
        color  = _sender_color(mail.sender_display)
        self._lbl_avatar.setText(letter)
        self._lbl_avatar.setStyleSheet(
            f"QLabel{{background:{color};color:#fff;"
            "border-radius:21px;font-size:15px;font-weight:bold;border:none;}}"
        )
        self._lbl_sender_name.setText(mail.sender_display)
        self._lbl_sender_email_lbl.setText(
            mail.sender_email if mail.sender_name else ""
        )
        self._lbl_date_detail.setText(
            mail.date_received.strftime("%d %b %Y  •  %H:%M")
        )
        self._lbl_recipients.setText(
            ", ".join(mail.recipients) if mail.recipients else "—"
        )
        self._header_card.show()
        self._populate_attach_bar(mail)
        self._txt_body.show()

        if mail.is_html_body:
            wrapped = (
                "<html><head><style>"
                "body{background:#fff;color:#1a1a1a;"
                "font-family:'Segoe UI',Arial,sans-serif;"
                "font-size:13px;margin:0;line-height:1.6;}"
                "a{color:#1565c0;} img{max-width:100%;}"
                "</style></head><body>" + mail.body + "</body></html>"
            )
            self._txt_body.setHtml(wrapped)
        else:
            self._txt_body.setPlainText(mail.body)

        self._btn_toggle_read.setText(
            "○  Marquer non-lu" if not mail.is_unread else "✓  Marquer lu"
        )

    # ------------------------------------------------------------------
    # Mail actions
    # ------------------------------------------------------------------

    def _open_compose(self, mode: str) -> None:
        mail = self._current_full_mail if mode != "new" else None
        if mode != "new" and mail is None:
            QMessageBox.information(self, "Action", "Sélectionnez d'abord un message.")
            return
        ComposeWindow(self._ews, mode=mode, mail=mail, contacts=self._ad_users, parent=self).exec()

    def _delete_selected(self) -> None:
        selected = self._mail_list.selectionModel().selectedIndexes()
        if not selected:
            return
        idx = selected[0].row()
        if idx < 0 or idx >= len(self._visible_items):
            return
        mail = self._visible_items[idx]
        reply = QMessageBox.question(
            self, "Supprimer",
            f"Supprimer le message « {mail.subject_display} » ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._run(
            self._ews.delete_email,
            mail.item_id, mail.change_key,
            on_result=lambda _: self._on_deleted(mail),
            on_error_prefix="Suppression",
            busy_msg="Suppression en cours…",
            show_progress=True,
        )

    def _on_deleted(self, mail: MailItem) -> None:
        if mail in self._all_items:
            self._all_items.remove(mail)
        self._current_full_mail = None
        self._apply_filter()
        self._show_empty_preview()
        self._set_status("Message supprimé.")

    def _toggle_read_selected(self) -> None:
        mail = self._current_full_mail
        if mail is None:
            selected = self._mail_list.selectionModel().selectedIndexes()
            if not selected:
                return
            idx = selected[0].row()
            if idx < 0 or idx >= len(self._visible_items):
                return
            mail = self._visible_items[idx]
        self._mark_read(mail, mail.is_unread)

    def _mark_read(self, mail: MailItem, is_read: bool) -> None:
        self._run(
            self._ews.mark_read,
            mail.item_id, mail.change_key, is_read,
            on_result=lambda _: self._on_read_toggled(mail, is_read),
            on_error_prefix="Marquage",
            busy_msg="",
            show_progress=False,
        )

    def _on_read_toggled(self, mail: MailItem, is_read: bool) -> None:
        mail.is_unread = not is_read
        if self._current_full_mail and self._current_full_mail.item_id == mail.item_id:
            self._current_full_mail.is_unread = not is_read
            self._btn_toggle_read.setText(
                "○  Marquer non-lu" if is_read else "✓  Marquer lu"
            )
        self._mail_list.viewport().update()
        self._refresh_folder_label()
        self._set_status("Statut de lecture mis à jour.")

    # ------------------------------------------------------------------
    # UI helpers
    # ------------------------------------------------------------------

    def _set_action_buttons(self, enabled: bool) -> None:
        for btn in (
            self._btn_reply, self._btn_reply_all, self._btn_forward,
            self._btn_delete, self._btn_toggle_read,
        ):
            btn.setEnabled(enabled)

    def _set_busy(self, busy: bool) -> None:
        self._progress.setVisible(busy)

    def _set_status(self, text: str) -> None:
        self._lbl_status.setText(text)

    def _show_empty_preview(self) -> None:
        self._mail_head.hide()
        self._txt_body.hide()
        self._txt_body.clear()
        self._empty_state.show()
        self._header_card.hide()
        self._attach_bar.hide()
        self._current_full_mail = None

    # ------------------------------------------------------------------
    # Attachment helpers
    # ------------------------------------------------------------------

    def _populate_attach_bar(self, mail: MailItem) -> None:
        while self._attach_layout.count():
            item = self._attach_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not mail.attachments:
            self._attach_bar.hide()
            return

        for att in mail.attachments:
            name    = att.get("name", "Pièce jointe")
            size    = att.get("size", 0)
            att_id  = att.get("id", "")
            btn = QPushButton(f"📎  {name}  ({_fmt_size(size)})")
            btn.setFixedHeight(28)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                "QPushButton{background:#eff6ff;color:#1d4ed8;"
                "border:1px solid #bfdbfe;border-radius:13px;"
                "padding:0 12px;font-size:11px;}"
                "QPushButton:hover{background:#dbeafe;border-color:#93c5fd;}"
            )
            btn.clicked.connect(
                lambda _c, m=mail, aid=att_id, n=name: self._download_attachment(m, aid, n)
            )
            self._attach_layout.addWidget(btn)

        self._attach_layout.addStretch()
        self._attach_bar.show()

    def _download_attachment(self, mail: MailItem, attachment_id: str, filename: str) -> None:
        self._run(
            self._ews.download_attachment,
            mail.item_id, mail.change_key, attachment_id,
            on_result=self._save_attachment,
            on_error_prefix="Téléchargement",
            busy_msg=f"Téléchargement de {filename}…",
            show_progress=True,
        )

    def _save_attachment(self, result) -> None:
        name, content = result
        downloads = Path.home() / "Downloads"
        downloads.mkdir(exist_ok=True)
        dest = downloads / name
        counter = 1
        while dest.exists():
            dest = downloads / f"{Path(name).stem} ({counter}){Path(name).suffix}"
            counter += 1
        dest.write_bytes(content)
        self._set_status(f"✓ Téléchargé : {dest.name}")
        reply = QMessageBox.question(
            self, "Téléchargement terminé",
            f"Fichier enregistré dans Téléchargements :\n{dest.name}\n\nOuvrir ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            os.startfile(str(dest))

    # ------------------------------------------------------------------
    # Worker launcher
    # ------------------------------------------------------------------

    def _run(
        self, fn, *args,
        on_result=None,
        on_error_prefix: str = "Erreur",
        busy_msg: str = "",
        show_progress: bool = True,
    ) -> None:
        if busy_msg:
            self._set_status(busy_msg)
        if show_progress:
            self._set_busy(True)

        worker = _Worker(fn, *args)
        self._workers.append(worker)

        def _done():
            if show_progress:
                self._set_busy(False)
            if worker in self._workers:
                self._workers.remove(worker)

        worker.signals.finished.connect(_done)
        if on_result:
            worker.signals.result.connect(on_result)
        worker.signals.error.connect(
            lambda msg: (
                self._set_status(f"Erreur : {msg[:80]}"),
                QMessageBox.critical(self, on_error_prefix, msg),
            )
        )
        QThreadPool.globalInstance().start(worker)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt_size(size: int) -> str:
    if size < 1024:
        return f"{size} o"
    if size < 1024 * 1024:
        return f"{size // 1024} Ko"
    return f"{size / (1024 * 1024):.1f} Mo"


_AVATAR_COLORS = [
    "#1565c0", "#6a1b9a", "#00695c", "#2e7d32",
    "#bf360c", "#4e342e", "#37474f", "#ad1457",
    "#0277bd", "#558b2f",
]


def _sender_color(sender: str) -> str:
    return _AVATAR_COLORS[hash(sender) % len(_AVATAR_COLORS)]


# ---------------------------------------------------------------------------
# Shared theme extras
# ---------------------------------------------------------------------------

_THEME_EXTRA: dict = {
    "font_family":   "Segoe UI",
    "density_scale": "0",
}
