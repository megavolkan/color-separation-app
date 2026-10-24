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
    win.dpi_combo.setCurrentIndex(win.dpi_combo.findData(72))
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
    win.plates.set_checked("Spot Gold. 871/C", True)
    win.gray_box.setChecked(True)
    assert win.plates.checked_names() == ["Spot Gold. 871/C"]
    img = win.view._item.pixmap().toImage()
    assert img.pixelColor(60, 59).red() == pytest.approx(127, abs=3)
    win.close()


def test_auto_dpi_follows_zoom(app, renderer, fixtures_dir):
    from ayrim.ui.main_window import MainWindow

    win = MainWindow(renderer)
    win.resize(900, 700)
    win.show()
    win.open_pdf(fixtures_dir / "basic.pdf")
    assert wait_for(app, lambda: win.seps)
    first = win.shown_dpi
    assert first >= 72
    win.view.zoom(4.0)
    assert wait_for(app, lambda: win.shown_dpi > first)
    # görüntü sahnede aynı boyutta kalır (PDF noktası birimi)
    assert win.view._item.sceneBoundingRect().width() == pytest.approx(300, abs=1)
    # dosya bırakma sayfa alanında yutulmaz, ana pencereye geçer
    assert not win.view.viewport().acceptDrops() and win.acceptDrops()
    win.close()


def test_info_panel_and_close(app, renderer, tmp_path, fixtures_dir):
    from make_fixtures import details_pdf
    from test_docdetails import profile

    from ayrim.ui.main_window import MainWindow

    pdf = tmp_path / "details.pdf"
    details_pdf(pdf, profile("ps_cmyk.icc"), profile("default_rgb.icc"))
    win = MainWindow(renderer)
    win.dpi_combo.setCurrentIndex(win.dpi_combo.findData(72))
    assert not win.close_act.isEnabled()
    win.open_pdf(pdf)
    assert wait_for(app, lambda: win.seps and win.info_panel.details)
    lines = win.info_panel.text().splitlines()
    for part in ("Sürüm:", "1.6", "PDF/X-4", "FOGRA39", "Artifex PS CMYK Profile (CMYK, ICC 4.2)",
                 "Kesim (TrimBox):", "95.2 × 95.2 mm", "Taşma payı:", "3.0 mm", "Gelecek",
                 "TrueType · gömülü, alt küme", "Helvetica", "Type1 · gömülü değil"):
        assert part in lines, part
    assert any(line.startswith("ICC RGB RGB nesneler") for line in lines)

    # tema düğmesi tüm uygulamanın arka planını değiştirir
    from ayrim.ui.theme import DARK, LIGHT

    win.set_theme(LIGHT, save=False)
    win.theme_act.trigger()
    assert win.theme is DARK and app.palette().window().color().name() == DARK.bg
    assert win.view.backgroundBrush().color().name() == DARK.bg
    win.theme_act.trigger()
    assert win.theme is LIGHT and app.palette().window().color().name() == LIGHT.bg

    win.close_pdf()
    assert not win.seps and win.info is None and not win.plates.rows
    assert win.windowTitle() == "Ayrım" and not win.close_act.isEnabled()
    assert "Belge açılmadı." in win.info_panel.text()

    # kapatmadan hemen önce başlayan işleme sonradan gelse de gösterilmez
    win.open_pdf(fixtures_dir / "basic.pdf")
    win.close_pdf()
    wait_for(app, lambda: False, timeout=2.0)
    assert not win.seps and not win.render_cache
    win.close()


def test_toolbar_toggles_and_overprint_badge(app, renderer, fixtures_dir):
    from ayrim.ui.main_window import MainWindow
    from ayrim.ui.widgets import ToggleSwitch

    win = MainWindow(renderer)
    win.dpi_combo.setCurrentIndex(win.dpi_combo.findData(72))
    win.open_pdf(fixtures_dir / "multipage.pdf")
    assert wait_for(app, lambda: win.seps)
    assert win.page_label.text() == "1 / 3"
    assert not win.prev_act.isEnabled() and win.next_act.isEnabled()
    win.next_act.trigger()
    assert win.page_label.text() == "2 / 3"
    # onay kutusu kalmadı; kalıplar ve gri gösterim anahtarla açılıp kapanır
    assert isinstance(win.gray_box, ToggleSwitch)
    assert all(isinstance(r.check, ToggleSwitch) for r in win.plates.rows)

    win.open_pdf(fixtures_dir / "basic.pdf")
    assert wait_for(app, lambda: win.seps and win.info_panel.details)
    badges = {r.name: not r.op_badge.isHidden() for r in win.plates.rows}
    assert badges["PANTONE 185 C"] and not badges["Black"]
    assert "Üste baskı:" in win.info_panel.text().splitlines()
    win.close()


def test_about_shows_license_and_ghostscript(app, renderer):
    from ayrim.ui.about import SOURCE_URL, about_html

    html = about_html(renderer.gs)
    assert "Affero" in html and SOURCE_URL in html and renderer.gs.version in html
    assert "Ghostscript bulunamadı" in about_html(None)
