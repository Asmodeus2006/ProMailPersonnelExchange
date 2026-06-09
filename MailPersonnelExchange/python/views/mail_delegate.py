from __future__ import annotations

from PyQt6.QtCore import QRect, QSize, Qt
from PyQt6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QPainter,
    QPen,
)
from PyQt6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem

from models.mail_item import MailItem

_ROW_HEIGHT      = 70
_ROW_HEIGHT_TALL = 88
_H_PAD = 16
_V_PAD = 11

# Light-mode palette (explicit — does not depend on qt-material theme)
_BG_NORMAL    = QColor("#ffffff")
_BG_UNREAD    = QColor("#eef5ff")
_BG_SELECTED  = QColor("#dbeafe")
_BG_HOVER     = QColor("#f0f6ff")
_FG_MAIN      = QColor("#0f172a")
_FG_SELECTED  = QColor("#1e3a8a")
_FG_MUTED     = QColor("#64748b")
_FG_MUTED_SEL = QColor("#3b82f6")
_DOT_COLOR    = QColor("#1976d2")
_SEP_COLOR    = QColor("#e8eef7")


class MailDelegate(QStyledItemDelegate):
    """Paints each email row: sender (bold) + date on top, subject below."""

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:
        mail: MailItem | None = index.data(Qt.ItemDataRole.UserRole)
        h = _ROW_HEIGHT_TALL if (mail and mail.recipients) else _ROW_HEIGHT
        return QSize(option.rect.width(), h)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        mail: MailItem | None = index.data(Qt.ItemDataRole.UserRole)
        if mail is None:
            super().paint(painter, option, index)
            return

        painter.save()

        # ── Selection state ──────────────────────────────────────────
        is_selected = bool(option.state & option.state.State_Selected)

        if is_selected:
            painter.fillRect(option.rect, _BG_SELECTED)
            fg_main  = _FG_SELECTED
            fg_muted = _FG_MUTED_SEL
        elif mail.is_unread:
            painter.fillRect(option.rect, _BG_UNREAD)
            fg_main  = _FG_MAIN
            fg_muted = _FG_MUTED
        else:
            painter.fillRect(option.rect, _BG_NORMAL)
            fg_main  = _FG_MAIN
            fg_muted = _FG_MUTED

        # ── Geometry ────────────────────────────────────────────────
        # leave space on the left for the unread dot (8px gutter)
        dot_gutter = 14
        r = option.rect.adjusted(_H_PAD + dot_gutter, _V_PAD, -_H_PAD, -_V_PAD)

        base_pt = option.font.pointSizeF()
        sender_pt = base_pt + 0.5 if base_pt > 0 else 10.5
        small_pt  = max(7.0, base_pt - 0.5) if base_pt > 0 else 9.0

        # ── Sender font (bold if unread) ─────────────────────────────
        sender_font = QFont(option.font)
        sender_font.setPointSizeF(sender_pt)
        sender_font.setBold(mail.is_unread)
        fm_s = QFontMetrics(sender_font)

        # ── Date / subject fonts ─────────────────────────────────────
        date_font = QFont(option.font)
        date_font.setPointSizeF(small_pt)
        fm_d = QFontMetrics(date_font)

        subj_font = QFont(option.font)
        subj_font.setPointSizeF(small_pt)
        subj_font.setBold(mail.is_unread)
        fm_subj = QFontMetrics(subj_font)

        # ── Row 1: sender + date ─────────────────────────────────────
        date_str = mail.date_display
        date_w = fm_d.horizontalAdvance(date_str) + 4

        date_rect   = QRect(r.right() - date_w, r.top(), date_w, fm_s.height())
        sender_rect = QRect(r.left(), r.top(), r.width() - date_w - 6, fm_s.height())

        painter.setFont(sender_font)
        painter.setPen(QPen(fg_main))
        painter.drawText(
            sender_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            fm_s.elidedText(mail.sender_display, Qt.TextElideMode.ElideRight, sender_rect.width()),
        )

        painter.setFont(date_font)
        painter.setPen(QPen(fg_muted))
        painter.drawText(
            date_rect,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            date_str,
        )

        # ── Row 2: subject ───────────────────────────────────────────
        subj_top = r.top() + fm_s.height() + 6
        attach_w = fm_subj.horizontalAdvance("📎 ") if mail.has_attachments else 0
        subj_rect = QRect(r.left() + attach_w, subj_top, r.width() - attach_w, fm_subj.height())

        painter.setFont(subj_font)
        painter.setPen(QPen(fg_main if mail.is_unread else fg_muted))
        if mail.has_attachments:
            painter.drawText(
                QRect(r.left(), subj_top, attach_w, fm_subj.height()),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                "📎",
            )
        painter.drawText(
            subj_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            fm_subj.elidedText(mail.subject_display, Qt.TextElideMode.ElideRight, subj_rect.width()),
        )

        # ── Row 3: recipients ───────────────────────────────────────
        if mail.recipients:
            recip_top = subj_top + fm_subj.height() + 4
            recip_font = QFont(option.font)
            recip_font.setPointSizeF(max(7.0, small_pt - 0.5))
            fm_recip = QFontMetrics(recip_font)

            first = mail.recipients[0]
            extra = len(mail.recipients) - 1
            recip_str = (
                f"À : {first}  +{extra} autre{'s' if extra > 1 else ''}"
                if extra > 0 else f"À : {first}"
            )

            recip_rect = QRect(r.left(), recip_top, r.width(), fm_recip.height())
            painter.setFont(recip_font)
            painter.setPen(QPen(fg_muted))
            painter.drawText(
                recip_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                fm_recip.elidedText(recip_str, Qt.TextElideMode.ElideRight, recip_rect.width()),
            )

        # ── Bottom separator ─────────────────────────────────────────
        if not is_selected:
            painter.setPen(QPen(_SEP_COLOR, 1))
            painter.drawLine(
                option.rect.left() + _H_PAD + dot_gutter,
                option.rect.bottom(),
                option.rect.right() - _H_PAD,
                option.rect.bottom(),
            )

        # ── Unread indicator bar (left edge) ─────────────────────────
        if mail.is_unread and not is_selected:
            painter.setBrush(_DOT_COLOR)
            painter.setPen(Qt.PenStyle.NoPen)
            cx = option.rect.left() + 6
            cy = option.rect.top() + option.rect.height() // 2
            painter.drawEllipse(cx - 4, cy - 4, 8, 8)

        painter.restore()
