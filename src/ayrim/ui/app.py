"""Uygulama giriş noktası: `uv run ayrim [dosya.pdf]`."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox

from ..gs import GhostscriptError, Renderer, find_ghostscript
from .main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Ayrım")
    try:
        gs = find_ghostscript()
    except GhostscriptError as e:
        QMessageBox.critical(None, "Ghostscript bulunamadı", str(e))
        return 1
    win = MainWindow(Renderer(gs))
    win.show()
    args = [a for a in sys.argv[1:] if a.lower().endswith(".pdf")]
    if args:
        win.open_pdf(Path(args[0]))
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
