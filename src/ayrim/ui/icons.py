"""Çizgi ikonlar: SVG yolundan temanın rengiyle QIcon üretir."""

from __future__ import annotations

import tempfile
from pathlib import Path

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

# 24×24 görünüm kutusunda çizgi yolları.
PATHS = {
    "folder": "M3 7.5A2.5 2.5 0 0 1 5.5 5H9l2 2.2h7.5A2.5 2.5 0 0 1 21 9.7v7.8a2.5 2.5 0 0 1-2.5 2.5h-13A2.5 2.5 0 0 1 3 17.5z",
    "close": "M6.5 6.5l11 11M17.5 6.5l-11 11",
    "document": "M14 3H7.5A2.5 2.5 0 0 0 5 5.5v13A2.5 2.5 0 0 0 7.5 21h9a2.5 2.5 0 0 0 2.5-2.5V8zM14 3v5h5",
    "sun": "M12 8a4 4 0 1 0 0 8a4 4 0 1 0 0-8zM12 2.5v2M12 19.5v2M4.6 4.6l1.4 1.4M18 18l1.4 1.4"
    "M2.5 12h2M19.5 12h2M4.6 19.4L6 18M18 6l1.4-1.4",
    "moon": "M20 14.6A8.2 8.2 0 1 1 9.4 4a6.6 6.6 0 0 0 10.6 10.6z",
    "minus": "M5.5 12h13",
    "plus": "M12 5.5v13M5.5 12h13",
    "zoom-out": "M11 4a7 7 0 1 0 0 14a7 7 0 1 0 0-14zM20.5 20.5l-4.5-4.5M8 11h6",
    "zoom-in": "M11 4a7 7 0 1 0 0 14a7 7 0 1 0 0-14zM20.5 20.5l-4.5-4.5M8 11h6M11 8v6",
    "fit": "M4 9V5.5A1.5 1.5 0 0 1 5.5 4H9M15 4h3.5A1.5 1.5 0 0 1 20 5.5V9M20 15v3.5a1.5 1.5 0 0 1-1.5 1.5H15"
    "M9 20H5.5A1.5 1.5 0 0 1 4 18.5V15",
    "chevron-down": "M6.5 9.5l5.5 5.5 5.5-5.5",
    "info": "M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18zM12 11v5.5M12 7.6v.4",
}


def _svg(name: str, color: str, stroke: float = 1.7) -> bytes:
    return (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'>"
        f"<path d='{PATHS[name]}' fill='none' stroke='{color}' stroke-width='{stroke}' "
        "stroke-linecap='round' stroke-linejoin='round'/></svg>"
    ).encode()


def pixmap(name: str, color: str, size: int = 18, scale: float = 2.0) -> QPixmap:
    px = int(size * scale)
    pm = QPixmap(px, px)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    QSvgRenderer(QByteArray(_svg(name, color))).render(painter, QRectF(0, 0, px, px))
    painter.end()
    pm.setDevicePixelRatio(scale)
    return pm


def icon(name: str, color: str, disabled: str) -> QIcon:
    ic = QIcon()
    ic.addPixmap(pixmap(name, color), QIcon.Mode.Normal)
    ic.addPixmap(pixmap(name, disabled), QIcon.Mode.Disabled)
    return ic


def icon_file(name: str, color: str, size: int = 12) -> str:
    """Stil sayfası (QSS) resmi yalnızca dosyadan okuyabildiği için ikonu diske yazar."""
    path = Path(tempfile.gettempdir()) / f"ayrim-{name}-{color.lstrip('#')}-{size}.png"
    if not path.exists() and not pixmap(name, color, size).save(str(path), "PNG"):
        return ""
    return path.as_posix()
