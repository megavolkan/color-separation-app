"""Bilinen değerli test PDF'lerinde ölçülen mürekkep yüzdelerini doğrular (±%2)."""

import numpy as np
import pytest

from ayrim.composite import total_ink
from ayrim.separations import PROCESS_NAMES, decode_separation_name, ink_from_pixel, load_separations

from make_fixtures import PAGE

DPI = 72  # 1 pt = 1 piksel
TOL = 2.0


def box_mean(ink: np.ndarray, box) -> float:
    x, y, w, h = box
    # PDF orijini sol altta, görüntü orijini sol üstte; kenarlardan içeride ölç
    top = PAGE - (y + h)
    mx, my = min(2, (w - 1) // 2), min(2, (h - 1) // 2)
    region = ink[top + my : top + h - my, x + mx : x + w - mx]
    assert region.size, f"boş ölçüm alanı: {box}"
    return float(region.mean()) * 100.0


def cases(expected):
    for fname, pages in expected.items():
        for page, boxes in pages.items():
            for box, inks in boxes:
                yield fname, page, box, inks


def test_ink_from_pixel_direction():
    assert ink_from_pixel(np.array([0, 255, 128], dtype=np.uint8)).tolist() == pytest.approx(
        [1.0, 0.0, 0.498], abs=1e-3
    )


@pytest.mark.parametrize(
    "encoded,name",
    [
        ("PANTONE 185 C", "PANTONE 185 C"),
        ("Spot Gold. 871%2FC", "Spot Gold. 871/C"),
        ("Weird (x)%25 %3A * ? %E9~#%5C", "Weird (x)% : * ? é~#\\"),
        ("Kırmızı %C3%A7", "Kırmızı ç"),
    ],
)
def test_decode_separation_name(encoded, name):
    assert decode_separation_name(encoded) == name


def test_known_boxes(renderer, expected, fixtures_dir):
    failures = []
    for fname, page, box, inks in cases(expected):
        seps = {s.name: s for s in load_separations(renderer.render(fixtures_dir / fname, page, DPI))}
        for name, want in inks.items():
            got = box_mean(seps[name].ink, box)
            if abs(got - want) > TOL:
                failures.append(f"{fname} s{page} {box} {name}: beklenen {want}, ölçülen {got:.1f}")
    assert not failures, "\n".join(failures)


def test_plate_lists_per_page(renderer, fixtures_dir):
    pdf = fixtures_dir / "multipage.pdf"
    names = [[s.name for s in load_separations(renderer.render(pdf, p, DPI))] for p in (1, 2, 3)]
    assert names[0] == [*PROCESS_NAMES, "PANTONE 185 C"]
    assert names[1] == [*PROCESS_NAMES, "Spot Gold. 871/C"]
    assert names[2] == [*PROCESS_NAMES, "Varnish"]


def test_overprint_off_knocks_out(renderer, fixtures_dir):
    seps = {s.name: s for s in load_separations(renderer.render(fixtures_dir / "basic.pdf", 1, DPI, overprint=False))}
    assert box_mean(seps["Cyan"].ink, (50, 50, 60, 60)) == pytest.approx(0, abs=TOL)


def test_tac_rich_black(renderer, fixtures_dir):
    seps = load_separations(renderer.render(fixtures_dir / "basic.pdf", 1, DPI))
    tac = total_ink([s.ink for s in seps])
    assert box_mean(tac / 100.0, (160, 160, 50, 50)) == pytest.approx(240, abs=TOL)


def test_cache_reuse(renderer, fixtures_dir):
    a = renderer.render(fixtures_dir / "basic.pdf", 1, DPI)
    mtime = a.composite.stat().st_mtime
    b = renderer.render(fixtures_dir / "basic.pdf", 1, DPI)
    assert a.directory == b.directory and b.composite.stat().st_mtime == mtime


def test_special_spot_names(renderer, tmp_path):
    from make_fixtures import SPECIAL_SPOTS, special_names_pdf

    pdf = tmp_path / "special.pdf"
    special_names_pdf(pdf)
    names = [s.name for s in load_separations(renderer.render(pdf, 1, DPI))]
    assert names[4:] == sorted(SPECIAL_SPOTS, key=str.casefold)
    # PDF'ten okunan adlar Ghostscript'in dosya adlarından çözülenlerle aynı olmalı
    from ayrim.pdfinfo import read_pdf_info

    assert set(read_pdf_info(pdf).spot_colors) == set(SPECIAL_SPOTS)


def test_missing_plates_is_an_error(tmp_path):
    from ayrim.gs import RenderResult

    (tmp_path / "p1.tif").touch()
    with pytest.raises(ValueError, match="kalıp dosyası yok.*p1.tif"):
        load_separations(RenderResult(tmp_path, 1, DPI, True))
