"""Açık ve koyu tema: renkler, uygulama paleti ve ortak stil."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QColor, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication

from .icons import icon_file


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
    button: str  # araç çubuğu düğmeleri
    button_border: str
    button_hover: str
    track: str  # kapalı anahtarın (toggle) zemini

    @property
    def is_dark(self) -> bool:
        return self.name == "dark"


# Renkler kullanıcının verdiği tasarım görsellerinden ölçüldü.
LIGHT = Theme(
    "light", "#ffffff", "#000000", "#737373", "#6b59a6", "#efefef", "#f5f5f5", "#cfcfcf",
    button="#f4f4f5", button_border="#e1e1e3", button_hover="#eaeaec", track="#d4d4d8",
)
DARK = Theme(
    "dark", "#1b2933", "#ffffff", "#7695ab", "#75c2f6", "#313e47", "#24333e", "#313e47",
    button="#273743", button_border="#354652", button_hover="#30414e", track="#3a4b57",
)
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


def stylesheet(t: Theme) -> str:
    chevron = icon_file("chevron-down", t.text)
    return f"""
    QMainWindow, QDockWidget, QScrollArea, QScrollArea > QWidget > QWidget {{ background: {t.bg}; }}
    QMainWindow::separator {{ background: {t.border}; width: 1px; height: 1px; }}
    QDockWidget {{ color: {t.text}; }}
    QDockWidget::title {{ background: {t.bg}; padding: 6px 10px; border-bottom: 1px solid {t.border}; }}
    QToolBar {{ background: {t.bg}; border: none; border-bottom: 1px solid {t.border}; spacing: 8px; padding: 8px 10px; }}
    QToolBar QLabel, QToolBar ToggleSwitch {{ color: {t.text}; font-size: 14px; }}
    QToolBar QToolButton, QComboBox, QLabel#pageLabel {{
        color: {t.text}; font-size: 14px; background: {t.button};
        border: 1px solid {t.button_border}; border-radius: 8px; min-height: 22px; padding: 4px 9px; }}
    QToolBar QToolButton:hover, QComboBox:hover {{ background: {t.button_hover}; }}
    QToolBar QToolButton:pressed {{ background: {t.button_border}; }}
    QToolBar QToolButton:checked {{ border-color: {t.accent}; }}
    QToolBar QToolButton[plain="true"]:checked {{ border-color: {t.button_border}; }}
    QToolBar QToolButton:disabled {{ color: {t.key}; }}
    QToolBar QToolButton[group="left"] {{ border-top-right-radius: 0; border-bottom-right-radius: 0; }}
    QToolBar QToolButton[group="right"] {{ border-top-left-radius: 0; border-bottom-left-radius: 0; }}
    QLabel#pageLabel {{ border-radius: 0; border-left: none; border-right: none; padding: 4px 16px; }}
    QComboBox {{ padding-right: 28px; }}
    QComboBox::drop-down {{ border: none; width: 26px; }}
    QComboBox::down-arrow {{ image: url("{chevron}"); width: 12px; height: 12px; }}
    QComboBox QAbstractItemView {{ background: {t.control}; color: {t.text}; border: 1px solid {t.border};
        selection-background-color: {t.accent}; selection-color: {t.bg}; outline: none; }}
    QPushButton {{ color: {t.text}; background: {t.button}; border: 1px solid {t.button_border};
        border-radius: 8px; padding: 5px 10px; font-size: 13px; }}
    QPushButton:hover {{ background: {t.button_hover}; }}
    QPushButton:pressed {{ background: {t.button_border}; }}
    QFrame#toolbarLine {{ background: {t.border}; border: none; min-width: 1px; max-width: 1px; margin: 4px 4px; }}
    QLabel#opBadge {{ color: {t.accent}; border: 1px solid {t.accent}; border-radius: 4px;
        font-size: 9px; font-weight: bold; padding: 0px 3px; }}
    QToolButton#infoButton {{ border: none; background: transparent; padding: 0; }}
    QStatusBar {{ background: {t.bg}; color: {t.key}; border-top: 1px solid {t.border}; }}
    QMenuBar {{ background: {t.bg}; color: {t.text}; }}
    QToolTip {{ background: {t.control}; color: {t.text}; border: 1px solid {t.border}; }}
    QFrame#sectionLine {{ background: {t.border}; border: none; max-height: 1px; min-height: 1px; }}
    QLabel#sectionTitle {{ color: {t.text}; font-size: 13px; font-weight: bold; }}
    QLabel#key {{ color: {t.key}; font-size: 11px; }}
    QLabel#value {{ color: {t.text}; font-size: 11px; font-weight: bold; }}
    QLabel#muted {{ color: {t.key}; font-size: 11px; font-style: italic; }}
    """


_current = LIGHT


def current_theme() -> Theme:
    """En son uygulanan tema (kendi çizen bileşenler için)."""
    return _current


def apply_theme(app: QApplication, t: Theme) -> None:
    """Temayı tüm uygulamaya uygular (Fusion stili paleti her sistemde aynen kullanır)."""
    global _current
    _current = t
    if app.style().name().lower() != "fusion":
        app.setStyle("Fusion")
    app.setPalette(palette(t))
    app.setStyleSheet(stylesheet(t))
