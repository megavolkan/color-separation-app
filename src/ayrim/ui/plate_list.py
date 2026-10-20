"""Kalıp listesi: onay kutusu, renk örneği, ad ve kapsama oranı."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import QColorDialog, QListWidget, QListWidgetItem

from ..composite import RGB

ROLE_NAME = Qt.ItemDataRole.UserRole


def swatch(color: RGB, size: int = 16) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(QColor.fromRgbF(*color))
    return QIcon(pm)


class PlateList(QListWidget):
    selection_changed = Signal()
    color_changed = Signal(str, object)  # ad, RGB

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._updating = False
        self.itemChanged.connect(self._on_item_changed)
        self.itemDoubleClicked.connect(self._pick_color)
        self.setToolTip("Kalıbı açıp kapatmak için onay kutusunu kullanın; rengini değiştirmek için çift tıklayın.")

    def set_plates(self, plates: list[tuple[str, RGB, float, bool]], checked: dict[str, bool]) -> None:
        """plates: (ad, renk, kapsama 0..1, renk PDF'ten okundu mu)."""
        self._updating = True
        self.clear()
        for name, color, coverage, known in plates:
            item = QListWidgetItem(swatch(color), f"{name}   {coverage * 100:.1f}%")
            item.setData(ROLE_NAME, name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if checked.get(name, True) else Qt.CheckState.Unchecked)
            if not known:
                item.setToolTip("Rengi PDF'ten okunamadı; seçmek için çift tıklayın.")
            self.addItem(item)
        self._updating = False

    def checked_names(self) -> list[str]:
        return [
            self.item(i).data(ROLE_NAME)
            for i in range(self.count())
            if self.item(i).checkState() == Qt.CheckState.Checked
        ]

    def set_all(self, state: bool) -> None:
        self._updating = True
        for i in range(self.count()):
            self.item(i).setCheckState(Qt.CheckState.Checked if state else Qt.CheckState.Unchecked)
        self._updating = False
        self.selection_changed.emit()

    def _on_item_changed(self, _item) -> None:
        if not self._updating:
            self.selection_changed.emit()

    def _pick_color(self, item: QListWidgetItem) -> None:
        name = item.data(ROLE_NAME)
        color = QColorDialog.getColor(parent=self, title=f"{name} rengi")
        if color.isValid():
            rgb = (color.redF(), color.greenF(), color.blueF())
            self._updating = True
            item.setIcon(swatch(rgb))
            self._updating = False
            self.color_changed.emit(name, rgb)
