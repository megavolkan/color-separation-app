"""Ana pencere: PDF açma, sayfa gezinme, kalıp listesi, önizleme ve ölçüm paneli."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from ..composite import PROCESS_RGB, RGB, composite, grayscale, inks_at
from ..gs import Renderer
from ..pdfinfo import DocInfo, read_pdf_info
from ..separations import Separation
from .page_view import PageView
from .plate_list import PlateList
from .worker import RenderTask

DEFAULT_DPI = 150
UNKNOWN_SPOT_RGB: RGB = (0.6, 0.6, 0.6)
MAX_CACHED_PAGES = 6


class MainWindow(QMainWindow):
    def __init__(self, renderer: Renderer) -> None:
        super().__init__()
        self.renderer = renderer
        self.pool = QThreadPool.globalInstance()
        self.pdf: Path | None = None
        self.info: DocInfo | None = None
        self.page = 1
        self.dpi = DEFAULT_DPI
        self.overprint = True
        self.seps: list[Separation] = []
        self.page_cache: dict[int, list[Separation]] = {}
        self.checked: dict[str, bool] = {}
        self.color_overrides: dict[str, RGB] = {}
        self._request = 0

        self.setWindowTitle("Ayrım")
        self.resize(1200, 800)
        self.setAcceptDrops(True)

        self.view = PageView()
        self.view.hovered.connect(self._on_hover)
        self.view.left.connect(lambda: self.readout.setText(""))
        self.setCentralWidget(self.view)

        self._build_plate_dock()
        self._build_readout_dock()
        self._build_toolbar()
        self.statusBar().showMessage(f"Ghostscript {renderer.gs.version} — {renderer.gs.path}")
        self._update_nav()

    # ------------------------------------------------------------ arayüz kurulumu

    def _build_toolbar(self) -> None:
        tb = QToolBar("Araçlar")
        tb.setMovable(False)
        self.addToolBar(tb)

        open_act = QAction("Aç…", self)
        open_act.setShortcut(QKeySequence.StandardKey.Open)
        open_act.triggered.connect(self.open_dialog)
        tb.addAction(open_act)
        self.menuBar().addMenu("Dosya").addAction(open_act)
        tb.addSeparator()

        self.prev_act = QAction("◀", self)
        self.prev_act.setShortcut(QKeySequence(Qt.Key.Key_PageUp))
        self.prev_act.triggered.connect(lambda: self.go_to(self.page - 1))
        tb.addAction(self.prev_act)
        self.page_spin = QSpinBox()
        self.page_spin.setMinimum(1)
        self.page_spin.valueChanged.connect(self.go_to)
        tb.addWidget(self.page_spin)
        self.page_total = QLabel(" / 0 ")
        tb.addWidget(self.page_total)
        self.next_act = QAction("▶", self)
        self.next_act.setShortcut(QKeySequence(Qt.Key.Key_PageDown))
        self.next_act.triggered.connect(lambda: self.go_to(self.page + 1))
        tb.addAction(self.next_act)
        tb.addSeparator()

        fit_act = QAction("Sığdır", self)
        fit_act.setShortcut(QKeySequence("Ctrl+0"))
        fit_act.triggered.connect(self.view.fit)
        tb.addAction(fit_act)
        tb.addSeparator()

        self.gray_box = QCheckBox("Tek kalıbı gri göster")
        self.gray_box.setToolTip("Yalnızca bir kalıp seçiliyken o kalıbı gri tonlu gösterir.")
        self.gray_box.toggled.connect(self.refresh_preview)
        tb.addWidget(self.gray_box)

    def _build_plate_dock(self) -> None:
        dock = QDockWidget("Kalıplar", self)
        dock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(4, 4, 4, 4)
        self.plates = PlateList()
        self.plates.selection_changed.connect(self._on_plate_selection)
        self.plates.color_changed.connect(self._on_color_changed)
        lay.addWidget(self.plates)
        row = QHBoxLayout()
        all_btn = QPushButton("Tümü")
        all_btn.clicked.connect(lambda: self.plates.set_all(True))
        none_btn = QPushButton("Hiçbiri")
        none_btn.clicked.connect(lambda: self.plates.set_all(False))
        row.addWidget(all_btn)
        row.addWidget(none_btn)
        lay.addLayout(row)
        dock.setWidget(w)
        dock.setMinimumWidth(240)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)

    def _build_readout_dock(self) -> None:
        dock = QDockWidget("İmleç altındaki mürekkep", self)
        dock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        self.readout = QLabel("")
        self.readout.setTextFormat(Qt.TextFormat.RichText)
        self.readout.setMinimumHeight(28)
        self.readout.setContentsMargins(8, 4, 8, 4)
        dock.setWidget(self.readout)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock)

    # ------------------------------------------------------------ dosya açma

    def open_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "PDF aç", "", "PDF dosyaları (*.pdf)")
        if path:
            self.open_pdf(Path(path))

    def open_pdf(self, path: Path) -> None:
        try:
            info = read_pdf_info(path)
        except Exception as e:
            QMessageBox.critical(self, "Açılamadı", f"{path.name} okunamadı:\n{e}")
            return
        if info.page_count == 0:
            QMessageBox.warning(self, "Boş belge", "Belgede sayfa yok.")
            return
        self.pdf, self.info = path, info
        self.page_cache.clear()
        self.checked.clear()
        self.color_overrides.clear()
        self.seps = []
        self.setWindowTitle(f"Ayrım — {path.name}")
        self.page = 0
        self.go_to(1)

    def dragEnterEvent(self, event) -> None:
        if any(u.toLocalFile().lower().endswith(".pdf") for u in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        for u in event.mimeData().urls():
            if u.toLocalFile().lower().endswith(".pdf"):
                self.open_pdf(Path(u.toLocalFile()))
                break

    # ------------------------------------------------------------ sayfa işleme

    def go_to(self, page: int) -> None:
        if not self.info or not (1 <= page <= self.info.page_count) or page == self.page:
            self._update_nav()
            return
        self.page = page
        self._update_nav()
        if page in self.page_cache:
            self._show_page(self.page_cache[page])
            return
        self._request += 1
        self.statusBar().showMessage(f"Sayfa {page} işleniyor…")
        self.view.setCursor(Qt.CursorShape.BusyCursor)
        task = RenderTask(self.renderer, self.pdf, page, self.dpi, self.overprint, self._request)
        task.signals.finished.connect(self._on_rendered)
        task.signals.failed.connect(self._on_failed)
        self.pool.start(task)

    def _on_rendered(self, request_id: int, page: int, seps: list[Separation]) -> None:
        self.page_cache[page] = seps
        while len(self.page_cache) > MAX_CACHED_PAGES:
            self.page_cache.pop(next(k for k in self.page_cache if k != self.page))
        if request_id != self._request or page != self.page:
            return  # kullanıcı başka sayfaya geçmiş
        self.view.unsetCursor()
        self.statusBar().showMessage(f"Sayfa {page}: {len(seps)} kalıp ({self.dpi} dpi)", 5000)
        self._show_page(seps)

    def _on_failed(self, request_id: int, page: int, msg: str) -> None:
        if request_id != self._request:
            return
        self.view.unsetCursor()
        self.statusBar().clearMessage()
        QMessageBox.critical(self, "Ghostscript hatası", msg)

    def _show_page(self, seps: list[Separation]) -> None:
        self.seps = seps
        plates = []
        for s in seps:
            color, known = self.plate_color(s.name)
            plates.append((s.name, color, s.coverage(), known))
        self.plates.set_plates(plates, self.checked)
        self.refresh_preview()

    def _update_nav(self) -> None:
        n = self.info.page_count if self.info else 0
        self.page_spin.blockSignals(True)
        self.page_spin.setMaximum(max(n, 1))
        self.page_spin.setValue(max(self.page, 1))
        self.page_spin.blockSignals(False)
        self.page_spin.setEnabled(n > 1)
        self.page_total.setText(f" / {n} ")
        self.prev_act.setEnabled(self.page > 1)
        self.next_act.setEnabled(self.page < n)

    # ------------------------------------------------------------ önizleme

    def plate_color(self, name: str) -> tuple[RGB, bool]:
        if name in self.color_overrides:
            return self.color_overrides[name], True
        if name in PROCESS_RGB:
            return PROCESS_RGB[name], True
        color = self.info.spot_colors.get(name) if self.info else None
        return (color, True) if color else (UNKNOWN_SPOT_RGB, False)

    def _on_plate_selection(self) -> None:
        names = set(self.plates.checked_names())
        for s in self.seps:
            self.checked[s.name] = s.name in names
        self.refresh_preview()

    def _on_color_changed(self, name: str, rgb: RGB) -> None:
        self.color_overrides[name] = rgb
        self.refresh_preview()

    def refresh_preview(self) -> None:
        if not self.seps:
            self.view.clear()
            return
        names = set(self.plates.checked_names())
        active = [s for s in self.seps if s.name in names]
        if len(active) == 1 and self.gray_box.isChecked():
            rgb = grayscale(active[0].ink)
        else:
            rgb = composite([(s.ink, self.plate_color(s.name)[0]) for s in active], shape=self.seps[0].ink.shape)
        self.view.set_image(rgb)

    def _on_hover(self, x: int, y: int) -> None:
        if not self.seps:
            return
        values, tac = inks_at([(s.name, s.ink) for s in self.seps], x, y)
        parts = []
        for name, v in values.items():
            r, g, b = (int(c * 255) for c in self.plate_color(name)[0])
            parts.append(f"<span style='color:rgb({r},{g},{b})'>■</span> {name}: <b>{v:.0f}%</b>")
        self.readout.setText("&nbsp;&nbsp; ".join(parts) + f"&nbsp;&nbsp;&nbsp; | &nbsp;TAC: <b>{tac:.0f}%</b>")
