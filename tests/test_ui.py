"""Arayüz duman testi (ekransız Qt)."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")


@pytest.fixture(scope="module")
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def wait_for(app, cond, timeout=20.0):
    import time

    end = time.time() + timeout
    while time.time() < end:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return False


def test_open_navigate_and_measure(app, renderer, fixtures_dir):
    from ayrim.ui.main_window import MainWindow

    win = MainWindow(renderer)
    win.dpi = 72
    win.open_pdf(fixtures_dir / "multipage.pdf")
    assert wait_for(app, lambda: win.seps)
    assert win.plates.checked_names() == ["Cyan", "Magenta", "Yellow", "Black", "PANTONE 185 C"]

    win.go_to(2)
    assert wait_for(app, lambda: any(s.name == "Spot Gold. 871/C" for s in win.seps))
    # şeffaf spot kutusunun ortası (pdf 60,240 → görüntü y=59)
    win._on_hover(60, 59)
    assert "Spot Gold. 871/C: <b>50%</b>" in win.readout.text()

    # tek kalıp + gri
    win.plates.set_all(False)
    win.plates.item(4).setCheckState(win.plates.item(4).checkState().Checked)
    win.gray_box.setChecked(True)
    assert win.plates.checked_names() == ["Spot Gold. 871/C"]
    img = win.view._item.pixmap().toImage()
    assert img.pixelColor(60, 59).red() == pytest.approx(127, abs=3)
    win.close()
