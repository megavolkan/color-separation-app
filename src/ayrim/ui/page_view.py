"""Sayfa görüntüsü: QGraphicsView, imleç konumu bildirimi ve yakınlaştırma."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsScene, QGraphicsView


def qimage_from_rgb(rgb: np.ndarray) -> QImage:
    rgb = np.ascontiguousarray(rgb)
    h, w, _ = rgb.shape
    img = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
    return img.copy()  # numpy belleğinden bağımsız kopya


class PageView(QGraphicsView):
    hovered = Signal(int, int)  # görüntü pikseli (x, y)
    left = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self._item = QGraphicsPixmapItem()
        self._item.setTransformationMode(Qt.TransformationMode.FastTransformation)
        self.scene().addItem(self._item)
        self.setBackgroundBrush(QColor(80, 80, 80))
        self.setMouseTracking(True)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        self._size: tuple[int, int] | None = None
        self._fit = True

    def set_image(self, rgb: np.ndarray) -> None:
        h, w, _ = rgb.shape
        new_size = self._size != (w, h)
        self._item.setPixmap(QPixmap.fromImage(qimage_from_rgb(rgb)))
        self._size = (w, h)
        self.scene().setSceneRect(0, 0, w, h)
        if new_size and self._fit:
            self.fit()

    def clear(self) -> None:
        self._item.setPixmap(QPixmap())
        self._size = None

    def fit(self) -> None:
        self._fit = True
        self.fitInView(self._item, Qt.AspectRatioMode.KeepAspectRatio)

    def zoom(self, factor: float) -> None:
        self._fit = False
        self.scale(factor, factor)

    def wheelEvent(self, event) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.zoom(1.25 if event.angleDelta().y() > 0 else 0.8)
        else:
            super().wheelEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._fit and self._size:
            self.fit()

    def mouseMoveEvent(self, event) -> None:
        super().mouseMoveEvent(event)
        if not self._size:
            return
        p: QPointF = self.mapToScene(event.position().toPoint())
        x, y = int(p.x()), int(p.y())
        if 0 <= x < self._size[0] and 0 <= y < self._size[1]:
            self.hovered.emit(x, y)
        else:
            self.left.emit()

    def leaveEvent(self, event) -> None:
        super().leaveEvent(event)
        self.left.emit()
