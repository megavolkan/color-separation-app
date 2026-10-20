"""Ghostscript işlemlerini arayüzü dondurmadan arka planda çalıştırır."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Signal

from ..gs import Renderer
from ..separations import load_separations


class RenderSignals(QObject):
    finished = Signal(int, int, object)  # istek no, sayfa, list[Separation]
    failed = Signal(int, int, str)


class RenderTask(QRunnable):
    def __init__(self, renderer: Renderer, pdf: Path, page: int, dpi: int, overprint: bool, request_id: int) -> None:
        super().__init__()
        self.renderer = renderer
        self.pdf = pdf
        self.page = page
        self.dpi = dpi
        self.overprint = overprint
        self.request_id = request_id
        self.signals = RenderSignals()

    def run(self) -> None:
        try:
            result = self.renderer.render(self.pdf, self.page, self.dpi, self.overprint)
            seps = load_separations(result)
        except Exception as e:  # arayüze hata olarak iletilir
            self.signals.failed.emit(self.request_id, self.page, str(e))
            return
        self.signals.finished.emit(self.request_id, self.page, seps)
