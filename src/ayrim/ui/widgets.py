"""Ortak bileşenler: anahtar (toggle) düğmesi ve bilgi (i) düğmesi."""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QAbstractButton, QSizePolicy, QToolButton

from . import icons
from .theme import current_theme

TRACK_W, TRACK_H, GAP = 30, 18, 8


class ToggleSwitch(QAbstractButton):
    """Onay kutusu yerine kullanılan aç/kapa anahtarı; metni sağında durur."""

    def __init__(self, text: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setText(text)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    def sizeHint(self) -> QSize:
        fm = self.fontMetrics()
        w = TRACK_W + (GAP + fm.horizontalAdvance(self.text()) if self.text() else 0)
        return QSize(w + 2, max(TRACK_H, fm.height()) + 4)

    def minimumSizeHint(self) -> QSize:
        # Dar alanda metin kısaltılarak (…) sığdırılır.
        return QSize(TRACK_W + (GAP + 40 if self.text() else 0) + 2, self.sizeHint().height())

    def paintEvent(self, event) -> None:
        t = current_theme()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        y = (self.height() - TRACK_H) / 2
        track = QRectF(1, y, TRACK_W, TRACK_H)
        on = self.isChecked()
        color = QColor(t.accent if on else t.track)
        if not self.isEnabled():
            color.setAlphaF(0.5)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        p.drawRoundedRect(track, TRACK_H / 2, TRACK_H / 2)
        d = TRACK_H - 4
        knob_x = track.right() - d - 2 if on else track.left() + 2
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(QRectF(knob_x, y + 2, d, d))
        if self.text():
            p.setPen(self.palette().color(self.foregroundRole()) if self.isEnabled() else QColor(t.key))
            p.setFont(self.font())
            text_rect = self.rect().adjusted(TRACK_W + GAP + 1, 0, 0, 0)
            text = self.fontMetrics().elidedText(self.text(), Qt.TextElideMode.ElideRight, text_rect.width())
            p.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)
        p.end()

    def hitButton(self, pos) -> bool:
        return self.rect().contains(pos)


class InfoButton(QToolButton):
    """Üzerine gelince açıklama gösteren (i) düğmesi."""

    def __init__(self, tooltip: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("infoButton")
        self.setToolTip(tooltip)
        self.setCursor(Qt.CursorShape.WhatsThisCursor)
        self.setIconSize(QSize(14, 14))
        self.refresh()

    def refresh(self) -> None:
        t = current_theme()
        self.setIcon(icons.icon("info", t.key, t.key))
