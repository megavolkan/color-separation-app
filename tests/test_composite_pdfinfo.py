import numpy as np
import pytest

from ayrim.composite import PROCESS_RGB, composite, grayscale, highlight, inks_at
from ayrim.pdfinfo import _eval_postscript, cmyk_to_srgb, lab_to_srgb, read_pdf_info


def test_composite_formula():
    full = np.ones((1, 1), np.float32)
    half = np.full((1, 1), 0.5, np.float32)
    assert composite([], shape=(1, 1))[0, 0].tolist() == [255, 255, 255]
    assert composite([(full, (1.0, 0.0, 0.0))])[0, 0].tolist() == [255, 0, 0]
    # rgb *= 1 - t*(1-c): t=0.5, c=0 → 0.5
    assert composite([(half, (0.0, 0.0, 0.0))])[0, 0].tolist() == [128, 128, 128]
    # cyan + yellow → yeşilimsi
    r, g, b = composite([(full, PROCESS_RGB["Cyan"]), (full, PROCESS_RGB["Yellow"])])[0, 0]
    assert g > r and g > b


def test_grayscale_and_inks_at():
    ink = np.array([[0.0, 1.0]], np.float32)
    assert grayscale(ink)[0].tolist() == [[255] * 3, [0] * 3]
    values, tac = inks_at([("Cyan", ink), ("Black", ink)], 1, 0)
    assert values == {"Cyan": 100.0, "Black": 100.0} and tac == 200.0


def test_highlight():
    rgb = np.full((1, 2, 3), 255, np.uint8)
    out = highlight(rgb, np.array([[True, False]]), (0, 0, 0), alpha=1.0)
    assert out[0, 0].tolist() == [0, 0, 0] and out[0, 1].tolist() == [255, 255, 255]


def test_color_conversions():
    assert cmyk_to_srgb(0, 0, 0, 0) == (1, 1, 1)
    assert lab_to_srgb(100, 0, 0) == pytest.approx((1, 1, 1), abs=0.01)
    r, g, b = lab_to_srgb(50, 70, 50)  # kırmızı
    assert r > 0.7 and g < 0.3 and b < 0.3


def test_postscript_function():
    # Tint → CMYK: { dup 0.91 mul exch 0.76 mul 0 exch 0 } benzeri
    code = b"{ dup 0 mul exch dup 0.91 mul exch dup 0.76 mul exch 0 mul }"
    assert _eval_postscript(code, [1.0]) == pytest.approx([0, 0.91, 0.76, 0])
    assert _eval_postscript(b"{ 0.5 gt { 1 } { 0 } ifelse }", [0.7]) == [1.0]


def test_read_pdf_info(fixtures_dir):
    info = read_pdf_info(fixtures_dir / "multipage.pdf")
    assert info.page_count == 3
    assert info.pages[0].width_pt == 300
    assert set(info.spot_colors) == {"PANTONE 185 C", "Spot Gold. 871/C", "Varnish"}
    r, g, b = info.spot_colors["PANTONE 185 C"]
    assert r == pytest.approx(1.0) and g == pytest.approx(0.09, abs=0.01)
