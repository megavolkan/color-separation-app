"""Sayfa görüntüsü: QGraphicsView, imleç konumu bildirimi ve yakınlaştırma.

Sahne birimi PDF noktasıdır (1/72 inç). Görüntü hangi DPI'da işlenmiş olursa olsun
72/dpi ölçeğiyle sahneye yerleşir; böylece DPI değişince görünüm yerinde kalır.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsScene, QGraphicsView

# Bu büyütmenin üstünde pikseller yumuşatılmadan gösterilir (ölçüm için net kenarlar).
SHARP_ABOVE = 2.0


def qimage_from_rgb(rgb: np.ndarray) -> QImage:
    rgb = np.ascontiguousarray(rgb)
    h, w, _ = rgb.shape
    img = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
    return img.copy()  # numpy belleğinden bağımsız kopya


class PageView(QGraphicsView):
    hovered = Signal(int, int)  # görüntü pikseli (x, y)
    left = Signal()
    view_changed = Signal()  # yakınlaştırma veya pencere boyutu değişti

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self._item = QGraphicsPixmapItem()
        self.scene().addItem(self._item)
        self.setBackgroundBrush(QColor(80, 80, 80))
        self.setMouseTracking(True)
        # Bırakılan dosyalar ana pencereye geçsin (QGraphicsView varsayılan olarak yutar).
        self.setAcceptDrops(False)
        self.viewport().setAcceptDrops(False)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        self._page: tuple[float, float] | None = None
        self._fit = True

    def set_page(self, width_pt: float, height_pt: float) -> None:
        """Yeni sayfanın boyutunu ayarlar (görüntü gelmeden önce)."""
        changed = self._page != (width_pt, height_pt)
        self._page = (width_pt, height_pt)
        self.scene().setSceneRect(0, 0, width_pt, height_pt)
        if changed and self._fit:
            self.fit()

    def set_image(self, rgb: np.ndarray, dpi: int) -> None:
        self._item.setPixmap(QPixmap.fromImage(qimage_from_rgb(rgb)))
        self._item.setScale(72.0 / dpi)
        self._update_smoothing()

    def clear(self) -> None:
        self._item.setPixmap(QPixmap())

    def physical_scale(self) -> float:
        """Bir PDF noktasının ekranda kaç fiziksel piksel tuttuğu (Retina dahil)."""
        return self.transform().m11() * self.devicePixelRatioF()

    def fit(self) -> None:
        self._fit = True
        if self._page:
            self.fitInView(self.scene().sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self._changed()

    def zoom(self, factor: float) -> None:
        self._fit = False
        self.scale(factor, factor)
        self._changed()

    def _changed(self) -> None:
        self._update_smoothing()
        self.view_changed.emit()

    def _update_smoothing(self) -> None:
        # görüntü pikseli başına ekran pikseli
        px = self.transform().m11() * self._item.scale() * self.devicePixelRatioF()
        mode = (
            Qt.TransformationMode.FastTransformation
            if px > SHARP_ABOVE
            else Qt.TransformationMode.SmoothTransformation
        )
        self._item.setTransformationMode(mode)

    def wheelEvent(self, event) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.zoom(1.25 if event.angleDelta().y() > 0 else 0.8)
        else:
            super().wheelEvent(event)

    def viewportEvent(self, event) -> bool:
        # macOS trackpad kıstırma hareketi
        if event.type() == QEvent.Type.NativeGesture:
            if event.gestureType() == Qt.NativeGestureType.ZoomNativeGesture:
                self.zoom(1.0 + event.value())
            return True
        return super().viewportEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._fit and self._page:
            self.fit()

    def mouseMoveEvent(self, event) -> None:
        super().mouseMoveEvent(event)
        pm = self._item.pixmap()
        if pm.isNull():
            return
        p = self._item.mapFromScene(self.mapToScene(event.position().toPoint()))
        x, y = int(p.x()), int(p.y())
        if 0 <= x < pm.width() and 0 <= y < pm.height():
            self.hovered.emit(x, y)
        else:
            self.left.emit()

    def leaveEvent(self, event) -> None:
        super().leaveEvent(event)
        self.left.emit()
