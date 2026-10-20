"""Kalıp listesi: her satırda onay kutusu, renk örneği, ad ve kapsama oranı.

Satırlar gerçek QCheckBox'lardır; QListWidget'ın öğe onay kutuları macOS koyu temada
düzgün çizilmiyordu.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QHBoxLayout,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..composite import RGB


def swatch(color: RGB, size: int = 16) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(QColor.fromRgbF(*color))
    return QIcon(pm)


class PlateRow(QWidget):
    toggled = Signal()
    color_clicked = Signal(str)

    def __init__(self, name: str, color: RGB, coverage: float, known: bool, checked: bool) -> None:
        super().__init__()
        self.name = name
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 2, 6, 2)
        self.check = QCheckBox(f"{name}   {coverage * 100:.1f}%")
        self.check.setChecked(checked)
        self.check.toggled.connect(self.toggled)
        self.color_btn = QToolButton()
        self.color_btn.setAutoRaise(True)
        self.color_btn.setIconSize(QSize(18, 18))
        self.color_btn.clicked.connect(lambda: self.color_clicked.emit(self.name))
        self.set_color(color)
        self.color_btn.setToolTip(
            "Rengi değiştirmek için tıklayın."
            if known
            else "Rengi PDF'ten okunamadı; seçmek için tıklayın."
        )
        lay.addWidget(self.check, 1)
        lay.addWidget(self.color_btn)

    def set_color(self, color: RGB) -> None:
        self.color_btn.setIcon(swatch(color, 18))


class PlateList(QScrollArea):
    selection_changed = Signal()
    color_changed = Signal(str, object)  # ad, RGB

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self._inner = QWidget()
        self._lay = QVBoxLayout(self._inner)
        self._lay.setContentsMargins(0, 4, 0, 4)
        self._lay.setSpacing(0)
        self._lay.addStretch(1)
        self.setWidget(self._inner)
        self.rows: list[PlateRow] = []
        self._updating = False

    def set_plates(self, plates: list[tuple[str, RGB, float, bool]], checked: dict[str, bool]) -> None:
        """plates: (ad, renk, kapsama 0..1, renk PDF'ten okundu mu)."""
        for row in self.rows:
            row.setParent(None)
            row.deleteLater()
        self.rows = []
        for name, color, coverage, known in plates:
            row = PlateRow(name, color, coverage, known, checked.get(name, True))
            row.toggled.connect(self._on_toggled)
            row.color_clicked.connect(self._pick_color)
            self._lay.insertWidget(len(self.rows), row)
            self.rows.append(row)

    def checked_names(self) -> list[str]:
        return [r.name for r in self.rows if r.check.isChecked()]

    def set_checked(self, name: str, state: bool) -> None:
        for r in self.rows:
            if r.name == name:
                r.check.setChecked(state)

    def set_all(self, state: bool) -> None:
        self._updating = True
        for r in self.rows:
            r.check.setChecked(state)
        self._updating = False
        self.selection_changed.emit()

    def _on_toggled(self) -> None:
        if not self._updating:
            self.selection_changed.emit()

    def _pick_color(self, name: str) -> None:
        color = QColorDialog.getColor(parent=self, title=f"{name} rengi")
        if not color.isValid():
            return
        rgb = (color.redF(), color.greenF(), color.blueF())
        for r in self.rows:
            if r.name == name:
                r.set_color(rgb)
        self.color_changed.emit(name, rgb)
