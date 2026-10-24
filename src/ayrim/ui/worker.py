"""Ghostscript işlemlerini arayüzü dondurmadan arka planda çalıştırır."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Signal

from ..docdetails import read_doc_details
from ..gs import Renderer
from ..separations import load_separations


class RenderSignals(QObject):
    finished = Signal(int, int, int, object)  # istek no, sayfa, dpi, list[Separation]
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
        self.signals.finished.emit(self.request_id, self.page, self.dpi, seps)


class DetailsSignals(QObject):
    finished = Signal(int, object)  # belge no, DocDetails
    failed = Signal(int, str)


class DetailsTask(QRunnable):
    """Belge bilgisini (yazı tipleri, renk uzayları…) arka planda okur."""

    def __init__(self, pdf: Path, doc_id: int) -> None:
        super().__init__()
        self.pdf = pdf
        self.doc_id = doc_id
        self.signals = DetailsSignals()

    def run(self) -> None:
        try:
            details = read_doc_details(self.pdf)
        except Exception as e:
            self.signals.failed.emit(self.doc_id, str(e))
            return
        self.signals.finished.emit(self.doc_id, details)
