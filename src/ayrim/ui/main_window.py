"""Ana pencere: PDF açma/kapatma, sayfa gezinme, kalıp listesi, önizleme, ölçüm ve belge bilgisi."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, QThreadPool, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDockWidget,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..composite import PROCESS_RGB, RGB, composite, grayscale, inks_at
from ..gs import Renderer
from ..pdfinfo import DocInfo, read_pdf_info
from ..separations import Separation
from . import icons
from .info_panel import InfoPanel
from .page_view import PageView
from .plate_list import PlateList
from .theme import DARK, LIGHT, Theme, apply_theme, save_theme, saved_theme
from .widgets import ToggleSwitch
from .worker import DetailsTask, RenderTask

UNKNOWN_SPOT_RGB: RGB = (0.6, 0.6, 0.6)
MAX_CACHED_RENDERS = 8
# Otomatik modda seçilebilecek çözünürlükler ve sayfa başına piksel sınırı (bellek için).
DPI_STEPS = (72, 100, 150, 200, 300, 400, 600, 800, 1200)
MAX_PIXELS = 60_000_000
MANUAL_DPIS = (72, 150, 300, 600)


class MainWindow(QMainWindow):
    def __init__(self, renderer: Renderer) -> None:
        super().__init__()
        self.renderer = renderer
        self.pool = QThreadPool.globalInstance()
        self.pdf: Path | None = None
        self.info: DocInfo | None = None
        self.page = 1
        self.manual_dpi: int | None = None  # None = otomatik
        self.shown_dpi = 0
        self.overprint = True
        self.seps: list[Separation] = []
        self.render_cache: dict[tuple[int, int], list[Separation]] = {}  # (sayfa, dpi)
        self.pending: set[tuple[int, int]] = set()
        self.checked: dict[str, bool] = {}
        self.color_overrides: dict[str, RGB] = {}
        self._request = 0
        self._doc_floor = 0  # bu numaraya kadarki istekler kapatılmış/önceki belgeye ait
        self._doc_id = 0

        self.setWindowTitle("Ayrım")
        self.resize(1200, 800)
        self.setAcceptDrops(True)

        self.view = PageView()
        self.view.hovered.connect(self._on_hover)
        self.view.left.connect(lambda: self.readout.setText(""))
        self.setCentralWidget(self.view)
        # Yakınlaştırma bitince gerekirse daha yüksek çözünürlükte yeniden işle.
        self._zoom_timer = QTimer(self)
        self._zoom_timer.setSingleShot(True)
        self._zoom_timer.setInterval(300)
        self._zoom_timer.timeout.connect(self._ensure_render)
        self.view.view_changed.connect(self._zoom_timer.start)
        self.dpi_label = QLabel("")
        self.statusBar().addPermanentWidget(self.dpi_label)

        self._build_plate_dock()
        self._build_readout_dock()
        self._build_info_dock()
        self._build_toolbar()
        self.set_theme(saved_theme(), save=False)
        self.statusBar().showMessage(f"Ghostscript {renderer.gs.version} — {renderer.gs.path}")
        self._update_nav()

    # ------------------------------------------------------------ arayüz kurulumu

    def _build_toolbar(self) -> None:
        tb = QToolBar("Araçlar")
        tb.setMovable(False)
        tb.setIconSize(QSize(18, 18))
        tb.setContextMenuPolicy(Qt.ContextMenuPolicy.PreventContextMenu)
        self.addToolBar(tb)
        self._icon_buttons: list[tuple[QAction, str]] = []  # tema değişince yeniden boyanır

        def action(text, slot, shortcut=None, icon=None, tip=None) -> QAction:
            act = QAction(text, self)
            if shortcut:
                act.setShortcut(QKeySequence(shortcut))
            if slot:
                act.triggered.connect(slot)
            if tip:
                act.setToolTip(tip)
            if icon:
                self._icon_buttons.append((act, icon))
            return act

        def button(act: QAction, text_beside: bool = False, group: str | None = None) -> QToolButton:
            btn = QToolButton()
            btn.setDefaultAction(act)
            btn.setToolButtonStyle(
                Qt.ToolButtonStyle.ToolButtonTextBesideIcon if text_beside else Qt.ToolButtonStyle.ToolButtonIconOnly
            )
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            if group:
                btn.setProperty("group", group)
            tb.addWidget(btn)
            return btn

        def joined(*widgets) -> None:
            # Gruplu düğmeler aralarında boşluk olmadan yan yana durur.
            box = QWidget()
            lay = QHBoxLayout(box)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(0)
            for w in widgets:
                lay.addWidget(w)
            tb.addWidget(box)

        open_act = action("Aç", self.open_dialog, QKeySequence.StandardKey.Open, "folder", "PDF aç (⌘O)")
        self.close_act = action(
            "Kapat", self.close_pdf, QKeySequence.StandardKey.Close, "close", "Belgeyi kapat; uygulama açık kalır (⌘W)"
        )
        self.close_act.setEnabled(False)
        button(open_act, text_beside=True)
        button(self.close_act, text_beside=True)

        info_act = self.info_dock.toggleViewAction()
        info_act.setShortcut(QKeySequence("Ctrl+I"))
        info_act.setToolTip("Belge bilgisi panelini aç/kapat (⌘I)")
        self._icon_buttons.append((info_act, "document"))
        button(info_act)
        self.theme_act = action("Koyu tema", None, "Ctrl+Shift+T")
        self.theme_act.setCheckable(True)
        self.theme_act.toggled.connect(lambda dark: self.set_theme(DARK if dark else LIGHT))
        self.theme_btn = button(self.theme_act)
        self.theme_btn.setProperty("plain", True)  # işaretli görünmesin; yalnızca simgesi değişir

        file_menu = self.menuBar().addMenu("Dosya")
        file_menu.addAction(open_act)
        file_menu.addAction(self.close_act)
        view_menu = self.menuBar().addMenu("Görünüm")
        view_menu.addAction(info_act)
        view_menu.addAction(self.theme_act)

        tb.addWidget(QLabel("Çözünürlük:"))
        self.dpi_combo = QComboBox()
        self.dpi_combo.addItem("Otomatik", None)
        for d in MANUAL_DPIS:
            self.dpi_combo.addItem(f"{d} dpi", d)
        self.dpi_combo.setToolTip("Otomatik: ekrana ve yakınlaştırmaya göre seçilir.")
        self.dpi_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.dpi_combo.currentIndexChanged.connect(self._on_dpi_mode)
        tb.addWidget(self.dpi_combo)

        self.gray_box = ToggleSwitch("Tek kalıbı gri göster")
        self.gray_box.setToolTip("Yalnızca bir kalıp seçiliyken o kalıbı gri tonlu gösterir.")
        self.gray_box.toggled.connect(self.refresh_preview)
        tb.addWidget(self.gray_box)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)

        self.prev_act = action("Önceki sayfa", lambda: self.go_to(self.page - 1), Qt.Key.Key_PageUp, "minus",
                               "Önceki sayfa (PageUp)")
        self.next_act = action("Sonraki sayfa", lambda: self.go_to(self.page + 1), Qt.Key.Key_PageDown, "plus",
                               "Sonraki sayfa (PageDown)")
        prev_btn = QToolButton()
        prev_btn.setDefaultAction(self.prev_act)
        prev_btn.setProperty("group", "left")
        self.page_label = QLabel("0 / 0")
        self.page_label.setObjectName("pageLabel")
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        next_btn = QToolButton()
        next_btn.setDefaultAction(self.next_act)
        next_btn.setProperty("group", "right")
        joined(prev_btn, self.page_label, next_btn)

        line = QFrame()
        line.setObjectName("toolbarLine")
        tb.addWidget(line)

        zoom_out = action("Uzaklaştır", lambda: self.view.zoom(1 / 1.25), QKeySequence.StandardKey.ZoomOut,
                          "zoom-out", "Uzaklaştır (⌘−)")
        zoom_in = action("Yakınlaştır", lambda: self.view.zoom(1.25), QKeySequence.StandardKey.ZoomIn,
                         "zoom-in", "Yakınlaştır (⌘+)")
        out_btn, in_btn = QToolButton(), QToolButton()
        out_btn.setDefaultAction(zoom_out)
        out_btn.setProperty("group", "left")
        in_btn.setDefaultAction(zoom_in)
        in_btn.setProperty("group", "right")
        joined(out_btn, in_btn)
        fit_act = action("Sığdır", self.view.fit, "Ctrl+0", "fit", "Sayfayı pencereye sığdır (⌘0)")
        button(fit_act)
        view_menu.addSeparator()
        for act in (zoom_in, zoom_out, fit_act):
            view_menu.addAction(act)
        for btn in tb.findChildren(QToolButton):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

    def _refresh_icons(self) -> None:
        t = self.theme
        for act, name in self._icon_buttons:
            act.setIcon(icons.icon(name, t.text, t.key))
        self.theme_act.setIcon(icons.icon("sun" if t.is_dark else "moon", t.text, t.key))
        self.theme_act.setToolTip("Açık temaya geç (⌘⇧T)" if t.is_dark else "Koyu temaya geç (⌘⇧T)")

    def set_theme(self, theme: Theme, save: bool = True) -> None:
        """Açık/koyu temayı tüm uygulamaya uygular."""
        self.theme = theme
        app = QApplication.instance()
        if app is not None:
            apply_theme(app, theme)
        self.view.set_colors(theme.bg, theme.page_outline)
        self.info_panel.set_theme(theme)
        self.theme_act.blockSignals(True)
        self.theme_act.setChecked(theme.is_dark)
        self.theme_act.blockSignals(False)
        self._refresh_icons()
        self.plates.update()
        if save:
            save_theme(theme)

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
        dock.setMinimumWidth(280)
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

    def _build_info_dock(self) -> None:
        self.info_dock = QDockWidget("Belge bilgisi", self)
        self.info_dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetClosable)
        self.info_panel = InfoPanel()
        self.info_dock.setWidget(self.info_panel)
        self.info_dock.setMinimumWidth(260)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.info_dock)

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
        self._reset_document()
        self.pdf, self.info = path, info
        self.close_act.setEnabled(True)
        self.info_panel.show_message("Belge bilgisi okunuyor…")
        task = DetailsTask(path, self._doc_id)
        task.signals.finished.connect(self._on_details)
        task.signals.failed.connect(self._on_details_failed)
        self.pool.start(task)
        self.view.fit()
        self.checked.clear()
        self.color_overrides.clear()
        self.seps = []
        self.setWindowTitle(f"Ayrım — {path.name}")
        self.page = 0
        self.go_to(1)

    def close_pdf(self) -> None:
        """Belgeyi kapatır; pencere boş haline döner."""
        if self.pdf is None:
            return
        self._reset_document()
        self.pdf, self.info = None, None
        self.page = 1
        self.seps, self.shown_dpi = [], 0
        self.checked.clear()
        self.color_overrides.clear()
        self.plates.set_plates([], {})
        self.view.clear()
        self.readout.setText("")
        self.dpi_label.setText("")
        self.info_panel.show_message("Belge açılmadı.")
        self.close_act.setEnabled(False)
        self.setWindowTitle("Ayrım")
        self._update_nav()

    def _reset_document(self) -> None:
        """Önceki belgeden gelecek geç sonuçları yok say."""
        self._doc_floor = self._request
        self._doc_id += 1
        self.render_cache.clear()
        self.pending.clear()
        self.view.unsetCursor()
        self.statusBar().clearMessage()

    def _on_details(self, doc_id: int, details) -> None:
        if doc_id == self._doc_id:
            self.info_panel.set_details(details, self.page)
            self._update_overprint()

    def _on_details_failed(self, doc_id: int, msg: str) -> None:
        if doc_id == self._doc_id:
            self.info_panel.show_message(f"Belge bilgisi okunamadı: {msg}")

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
        self.info_panel.set_page(page)
        info = self.info.pages[page - 1]
        self.view.set_page(info.width_pt, info.height_pt)
        self.seps, self.shown_dpi = [], 0
        # Daha önce işlenmiş bir sürüm varsa (en yüksek DPI'lı) hemen göster.
        cached = sorted(d for p, d in self.render_cache if p == page)
        if cached:
            self._show_page(self.render_cache[(page, cached[-1])], cached[-1])
        else:
            self.view.clear()
        self._ensure_render()

    def target_dpi(self) -> int:
        """Gösterilecek çözünürlük: elle seçilen ya da ekranın gerektirdiği."""
        if self.manual_dpi:
            return self.manual_dpi
        info = self.info.pages[self.page - 1]
        need = self.view.physical_scale() * 72.0
        limit = (MAX_PIXELS / max(info.width_pt * info.height_pt, 1.0)) ** 0.5 * 72.0
        allowed = [d for d in DPI_STEPS if d <= limit] or [DPI_STEPS[0]]
        return next((d for d in allowed if d >= need), allowed[-1])

    def _ensure_render(self) -> None:
        if not self.info or not (1 <= self.page <= self.info.page_count):
            return
        dpi = self.target_dpi()
        if self.manual_dpi is None and self.shown_dpi >= dpi:
            return  # otomatik modda daha keskin bir görüntü zaten ekranda
        if dpi == self.shown_dpi:
            return
        key = (self.page, dpi)
        if key in self.render_cache:
            self._show_page(self.render_cache[key], dpi)
            return
        if key in self.pending:
            return
        self.pending.add(key)
        self._request += 1
        self.statusBar().showMessage(f"Sayfa {self.page} {dpi} dpi işleniyor…")
        self.view.setCursor(Qt.CursorShape.BusyCursor)
        task = RenderTask(self.renderer, self.pdf, self.page, dpi, self.overprint, self._request)
        task.signals.finished.connect(self._on_rendered)
        task.signals.failed.connect(self._on_failed)
        self.pool.start(task)

    def _on_dpi_mode(self) -> None:
        self.manual_dpi = self.dpi_combo.currentData()
        self._ensure_render()

    def _on_rendered(self, request_id: int, page: int, dpi: int, seps: list[Separation]) -> None:
        if request_id <= self._doc_floor:
            return  # kapatılmış ya da değiştirilmiş belgeye ait
        self.pending.discard((page, dpi))
        self.render_cache[(page, dpi)] = seps
        while len(self.render_cache) > MAX_CACHED_RENDERS:
            self.render_cache.pop(next(k for k in self.render_cache if k[0] != self.page))
        if not self.pending:
            self.view.unsetCursor()
            self.statusBar().clearMessage()
        if page != self.page:
            return  # kullanıcı başka sayfaya geçmiş
        auto_sharper = self.manual_dpi is None and dpi > self.shown_dpi
        if dpi == self.target_dpi() or auto_sharper or not self.seps:
            self._show_page(seps, dpi)
        self._ensure_render()  # bu arada yakınlaştırma değişmiş olabilir

    def _on_failed(self, request_id: int, page: int, msg: str) -> None:
        if request_id <= self._doc_floor:
            return
        self.pending = {k for k in self.pending if k[0] != page}
        if request_id != self._request:
            return
        self.view.unsetCursor()
        self.statusBar().clearMessage()
        QMessageBox.critical(self, "Ghostscript hatası", msg)

    def _show_page(self, seps: list[Separation], dpi: int) -> None:
        same_plates = [s.name for s in seps] == [s.name for s in self.seps]
        self.seps, self.shown_dpi = seps, dpi
        if not same_plates:
            plates = []
            for s in seps:
                color, known = self.plate_color(s.name)
                plates.append((s.name, color, s.coverage(), known))
            self.plates.set_plates(plates, self.checked)
        self._update_overprint()
        self.dpi_label.setText(f"{dpi} dpi")
        self.refresh_preview()

    def _update_overprint(self) -> None:
        d = self.info_panel.details
        ok = d is not None and 1 <= self.page <= len(d.pages)
        self.plates.set_overprint(d.pages[self.page - 1].overprint if ok else ())

    def _update_nav(self) -> None:
        n = self.info.page_count if self.info else 0
        self.page_label.setText(f"{self.page if n else 0} / {n}")
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
        self.view.set_image(rgb, self.shown_dpi)

    def _on_hover(self, x: int, y: int) -> None:
        if not self.seps:
            return
        values, tac = inks_at([(s.name, s.ink) for s in self.seps], x, y)
        parts = []
        for name, v in values.items():
            r, g, b = (int(c * 255) for c in self.plate_color(name)[0])
            parts.append(f"<span style='color:rgb({r},{g},{b})'>■</span> {name}: <b>{v:.0f}%</b>")
        self.readout.setText("&nbsp;&nbsp; ".join(parts) + f"&nbsp;&nbsp;&nbsp; | &nbsp;TAC: <b>{tac:.0f}%</b>")
