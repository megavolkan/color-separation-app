"""Belge bilgisi: sürüm, PDF/X, çıktı amacı, ICC, renk uzayları, kutular, yazı tipleri."""

import glob
from pathlib import Path

import pytest

from ayrim.docdetails import bleed_mm, box_size_mm, read_doc_details, read_icc

from make_fixtures import details_pdf

ICC_DIRS = [
    "/usr/share/color/icc/ghostscript",
    "/usr/share/ghostscript/*/iccprofiles",
    "/opt/homebrew/share/ghostscript/*/iccprofiles",
    "/usr/local/share/ghostscript/*/iccprofiles",
]


def profile(name: str) -> bytes:
    for d in ICC_DIRS:
        hits = sorted(glob.glob(f"{d}/{name}"))
        if hits:
            return Path(hits[-1]).read_bytes()
    pytest.skip(f"Ghostscript {name} bulunamadı")


def test_icc_names_v2_and_v4():
    v4 = read_icc(profile("ps_cmyk.icc"))  # mluc etiketi
    v2 = read_icc(profile("default_rgb.icc"))  # desc etiketi
    assert (v4.name, v4.color_space, v4.version) == ("Artifex PS CMYK Profile", "CMYK", "4.2")
    assert (v2.name, v2.color_space) == ("Artifex Software sRGB ICC Profile", "RGB")
    assert read_icc(b"bozuk") is None


def test_document_details(tmp_path):
    pdf = tmp_path / "details.pdf"
    details_pdf(pdf, profile("ps_cmyk.icc"), profile("default_rgb.icc"))
    d = read_doc_details(pdf)
    assert d.pdf_version == "1.6"
    assert d.pdfx == "PDF/X-4"
    [oi] = d.output_intents
    assert (oi.subtype, oi.condition, oi.profile.name) == ("GTS_PDFX", "FOGRA39", "Artifex PS CMYK Profile")
    assert d.color_spaces == ["CMYK", "ICC RGB"]
    assert [p.name for p in d.icc_profiles] == ["Artifex Software sRGB ICC Profile"]
    fonts = {f.name: f for f in d.fonts}
    assert fonts["Gelecek"].embedded and fonts["Gelecek"].subset
    assert not fonts["Helvetica"].embedded
    page = d.pages[0]
    assert set(page.boxes) == {"MediaBox", "BleedBox", "TrimBox"}
    assert box_size_mm(page.boxes["TrimBox"]) == pytest.approx((95.25, 95.25))
    assert bleed_mm(page) == pytest.approx(3.0, abs=0.01)


def test_plain_fixture(fixtures_dir):
    d = read_doc_details(fixtures_dir / "multipage.pdf")
    assert d.pdfx is None and not d.output_intents and not d.fonts
    assert d.color_spaces == ["CMYK", "Spot"]
    assert len(d.pages) == 3 and bleed_mm(d.pages[0]) is None


def test_blend_space_and_page_ranges(tmp_path, fixtures_dir):
    import pikepdf

    from ayrim.docdetails import page_ranges
    from ayrim.ui.info_panel import sections
    from ayrim.ui.theme import LIGHT

    # Affinity çıktısı gibi: 1. sayfa CMYK, diğerleri ICC RGB karışım uzaylı saydamlık grubu
    src = pikepdf.open(fixtures_dir / "multipage.pdf")
    rgb = src.make_stream(profile("default_rgb.icc"), N=3)
    groups = [pikepdf.Name.DeviceCMYK, pikepdf.Array([pikepdf.Name.ICCBased, rgb]), pikepdf.Array([pikepdf.Name.ICCBased, rgb])]
    for page, cs in zip(src.pages, groups):
        page.obj.Group = pikepdf.Dictionary(S=pikepdf.Name.Transparency, CS=cs)
    pdf = tmp_path / "blend.pdf"
    src.save(pdf)

    d = read_doc_details(pdf)
    assert [p.blend_space for p in d.pages] == ["CMYK", "RGB", "RGB"]
    assert d.rgb_blend_pages == [2, 3]
    rows = dict(sections(d, 1, LIGHT)[1][1])
    assert "CMYK (sayfa 1)" in rows["Karışım uzayı"] and "RGB (sayfa 2–3)" in rows["Karışım uzayı"]
    assert read_doc_details(fixtures_dir / "basic.pdf").pages[0].blend_space is None
    assert page_ranges([2, 3, 4, 7, 9, 10]) == "2–4, 7, 9–10"
