"""Açık ve koyu tema: renkler, uygulama paleti ve ortak stil."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QPointF, QSettings, Qt
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPalette, QPen, QPixmap
from PySide6.QtWidgets import QApplication


@dataclass(frozen=True)
class Theme:
    name: str  # "light" | "dark"
    bg: str  # tüm uygulamanın arka planı
    text: str  # değerler ve başlıklar
    key: str  # tablo anahtarları, ikincil metin
    accent: str  # vurgulu metin (RGB uyarısı, gömülmemiş font…)
    border: str  # bölüm ayırıcıları ve kenarlıklar
    control: str  # düğme ve giriş kutusu zemini
    page_outline: str  # sayfanın çevresindeki ince çerçeve

    @property
    def is_dark(self) -> bool:
        return self.name == "dark"


# Renkler kullanıcının verdiği tasarım görsellerinden ölçüldü.
LIGHT = Theme("light", "#ffffff", "#000000", "#737373", "#6b59a6", "#efefef", "#f5f5f5", "#cfcfcf")
DARK = Theme("dark", "#1b2933", "#ffffff", "#7695ab", "#75c2f6", "#313e47", "#24333e", "#313e47")
THEMES = {t.name: t for t in (LIGHT, DARK)}

_SETTINGS_KEY = "tema"


def saved_theme() -> Theme:
    """Kaydedilmiş tema; yoksa sistemin açık/koyu ayarı."""
    name = QSettings().value(_SETTINGS_KEY, "", str)
    if name in THEMES:
        return THEMES[name]
    hints = QGuiApplication.styleHints()
    if hasattr(hints, "colorScheme") and hints.colorScheme() == Qt.ColorScheme.Dark:
        return DARK
    return LIGHT


def save_theme(theme: Theme) -> None:
    QSettings().setValue(_SETTINGS_KEY, theme.name)


def palette(t: Theme) -> QPalette:
    p = QPalette()
    bg, text, key, accent = QColor(t.bg), QColor(t.text), QColor(t.key), QColor(t.accent)
    control, border = QColor(t.control), QColor(t.border)
    for group in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive):
        p.setColor(group, QPalette.ColorRole.Window, bg)
        p.setColor(group, QPalette.ColorRole.Base, control)  # onay kutusu, sayı kutusu zemini
        p.setColor(group, QPalette.ColorRole.AlternateBase, control)
        p.setColor(group, QPalette.ColorRole.Button, control)
        p.setColor(group, QPalette.ColorRole.ToolTipBase, control)
        for role in (
            QPalette.ColorRole.WindowText,
            QPalette.ColorRole.Text,
            QPalette.ColorRole.ButtonText,
            QPalette.ColorRole.ToolTipText,
            QPalette.ColorRole.BrightText,
        ):
            p.setColor(group, role, text)
        p.setColor(group, QPalette.ColorRole.PlaceholderText, key)
        p.setColor(group, QPalette.ColorRole.Highlight, accent)
        p.setColor(group, QPalette.ColorRole.HighlightedText, bg)
        p.setColor(group, QPalette.ColorRole.Link, accent)
        p.setColor(group, QPalette.ColorRole.Light, control)
        p.setColor(group, QPalette.ColorRole.Midlight, border)
        p.setColor(group, QPalette.ColorRole.Mid, border)
        p.setColor(group, QPalette.ColorRole.Dark, key)
        p.setColor(group, QPalette.ColorRole.Shadow, border)
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Window, bg)
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Base, bg)
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Button, control)
    for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText):
        p.setColor(QPalette.ColorGroup.Disabled, role, key)
    return p


def _check_icon(t: Theme) -> str:
    """Onay işareti resmi; Qt stil sayfası resmi yalnızca dosyadan okuyabildiği için diske yazılır."""
    path = Path(tempfile.gettempdir()) / f"ayrim-check-{t.name}-{t.bg.lstrip('#')}.png"
    if not path.exists():
        pm = QPixmap(28, 28)  # Retina için 2x; stil sayfası kutuya sığdırır
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(t.bg), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.drawPolyline([QPointF(6, 14.5), QPointF(11.5, 20), QPointF(22, 8.5)])
        p.end()
        if not pm.save(str(path), "PNG"):
            return ""
    return path.as_posix()


def stylesheet(t: Theme) -> str:
    check = _check_icon(t)
    return f"""
    QCheckBox::indicator {{ width: 14px; height: 14px; border: 1px solid {t.key}; border-radius: 3px;
                            background: {t.control}; }}
    QCheckBox::indicator:checked {{ background: {t.accent}; border-color: {t.accent};
                                    image: url("{check}"); }}
    QMainWindow, QDockWidget, QScrollArea, QScrollArea > QWidget > QWidget {{ background: {t.bg}; }}
    QMainWindow::separator {{ background: {t.border}; width: 1px; height: 1px; }}
    QDockWidget {{ color: {t.text}; }}
    QDockWidget::title {{ background: {t.bg}; padding: 6px 10px; border-bottom: 1px solid {t.border}; }}
    QToolBar {{ background: {t.bg}; border: none; border-bottom: 1px solid {t.border}; spacing: 4px; padding: 2px 6px; }}
    QStatusBar {{ background: {t.bg}; color: {t.key}; border-top: 1px solid {t.border}; }}
    QMenuBar {{ background: {t.bg}; color: {t.text}; }}
    QToolTip {{ background: {t.control}; color: {t.text}; border: 1px solid {t.border}; }}
    QFrame#sectionLine {{ background: {t.border}; border: none; max-height: 1px; min-height: 1px; }}
    QLabel#sectionTitle {{ color: {t.text}; font-size: 13px; font-weight: bold; }}
    QLabel#key {{ color: {t.key}; font-size: 11px; }}
    QLabel#value {{ color: {t.text}; font-size: 11px; font-weight: bold; }}
    QLabel#muted {{ color: {t.key}; font-size: 11px; font-style: italic; }}
    """


def apply_theme(app: QApplication, t: Theme) -> None:
    """Temayı tüm uygulamaya uygular (Fusion stili paleti her sistemde aynen kullanır)."""
    if app.style().name().lower() != "fusion":
        app.setStyle("Fusion")
    app.setPalette(palette(t))
    app.setStyleSheet(stylesheet(t))
