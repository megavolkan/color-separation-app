"""ICC profilli CMYK önizlemesi."""

import numpy as np
import pytest

from ayrim.colormgmt import choose_profile, ghostscript_cmyk_profile
from ayrim.composite import composite_cmyk
from ayrim.pdfinfo import read_pdf_info

from make_fixtures import details_pdf
from test_docdetails import profile


@pytest.fixture
def preview(renderer):
    p = choose_profile(None, renderer.gs.path)
    if p is None:
        pytest.skip("Ghostscript'in CMYK profili bulunamadı")
    return p


def test_ghostscript_profile_found(renderer):
    path = ghostscript_cmyk_profile(renderer.gs.path)
    assert path is None or path.name == "default_cmyk.icc"


def test_orange_is_not_red(preview):
    # %75 Magenta + %100 Yellow turuncudur; basit çarpma neredeyse kırmızı veriyordu (G ≈ 0.24).
    r, g, b = preview.color(0, 0.75, 1, 0)
    assert r > 0.9 and 0.33 < g < 0.5 and b < 0.2
    assert preview.color(0, 0, 0, 0) == pytest.approx((1, 1, 1), abs=0.01)
    assert max(preview.color(1, 1, 1, 1)) < 0.05
    assert preview.source.origin == "Ghostscript varsayılanı"


def test_document_profile_preferred(tmp_path, renderer):
    pdf = tmp_path / "d.pdf"
    details_pdf(pdf, profile("ps_cmyk.icc"), profile("default_rgb.icc"))
    info = read_pdf_info(pdf)
    p = choose_profile(info.cmyk_profile, renderer.gs.path)
    assert p.source.origin == "belgeden" and p.source.name == "Artifex PS CMYK Profile"
    assert "belgeden" in p.label
    # Bozuk ya da CMYK olmayan profil yok sayılır.
    assert choose_profile(b"bozuk", renderer.gs.path).source.origin != "belgeden"


def test_composite_cmyk_layers_spots_over_profile(preview):
    shape = (1, 2)
    full = np.ones(shape, np.float32)
    seen = []

    def to_rgb(cmyk):
        seen.append(cmyk.copy())
        return preview.to_rgb(cmyk)

    rgb = composite_cmyk(to_rgb, {"Magenta": full * 0.75, "Yellow": full}, [], shape)
    assert seen[0][0, 0].tolist() == [0, 191, 255, 0]
    assert rgb[0, 0].tolist() == [round(v * 255) for v in preview.color(0, 0.75, 1, 0)]
    # Siyah bir spot üstüne tam basılınca sonuç siyah olur.
    black = composite_cmyk(preview.to_rgb, {"Yellow": full}, [(full, (0.0, 0.0, 0.0))], shape)
    assert black.max() == 0


def test_spot_cmyk_alternates(fixtures_dir):
    info = read_pdf_info(fixtures_dir / "multipage.pdf")
    assert info.spot_cmyk["PANTONE 185 C"] == pytest.approx((0, 0.91, 0.76, 0))
