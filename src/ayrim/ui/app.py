"""Uygulama giriş noktası: `uv run ayrim [dosya.pdf]` veya Ayrim.app."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication, QMessageBox

from ..gs import GhostscriptError, Renderer, find_ghostscript
from .main_window import MainWindow


class AyrimApp(QApplication):
    """macOS'ta Finder'dan "Birlikte Aç" ya da Dock simgesine bırakılan PDF'leri karşılar."""

    def __init__(self, argv: list[str]) -> None:
        super().__init__(argv)
        self.window: MainWindow | None = None
        self.pending: list[Path] = []

    def event(self, e: QEvent) -> bool:
        if e.type() == QEvent.Type.FileOpen:
            path = Path(e.file())
            if self.window:
                self.window.open_pdf(path)
            else:
                self.pending.append(path)
            return True
        return super().event(e)


def main() -> int:
    app = AyrimApp(sys.argv)
    app.setApplicationName("Ayrım")
    app.setOrganizationName("Ayrim")  # tema tercihi QSettings ile saklanır
    try:
        gs = find_ghostscript()
    except GhostscriptError as e:
        QMessageBox.critical(None, "Ghostscript bulunamadı", str(e))
        return 1
    app.window = MainWindow(Renderer(gs))
    app.window.show()
    files = app.pending + [Path(a) for a in sys.argv[1:] if a.lower().endswith(".pdf")]
    if files:
        app.window.open_pdf(files[-1])
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
