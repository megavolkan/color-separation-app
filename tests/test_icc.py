"""ICCBased CMYK değerleri dönüştürülmeden kalıplara gitmeli (Affinity PDF/X)."""

import glob
from pathlib import Path

import pytest

from ayrim.separations import load_separations

from make_fixtures import icc_cmyk_pdf
from test_separations import TOL, box_mean

# Ghostscript'in varsayılandan farklı CMYK profili (kurulumla gelir).
PROFILE_GLOBS = [
    "/usr/share/color/icc/ghostscript/ps_cmyk.icc",
    "/usr/share/ghostscript/*/iccprofiles/ps_cmyk.icc",
    "/opt/homebrew/share/ghostscript/*/iccprofiles/ps_cmyk.icc",
    "/usr/local/share/ghostscript/*/iccprofiles/ps_cmyk.icc",
]


def find_profile() -> Path | None:
    for pattern in PROFILE_GLOBS:
        hits = sorted(glob.glob(pattern))
        if hits:
            return Path(hits[-1])
    return None


def test_icc_cmyk_values_pass_through(renderer, tmp_path):
    profile = find_profile()
    if profile is None:
        pytest.skip("Ghostscript ps_cmyk.icc bulunamadı")
    pdf = tmp_path / "icc.pdf"
    boxes = icc_cmyk_pdf(pdf, profile.read_bytes())
    seps = {s.name: s for s in load_separations(renderer.render(pdf, 1, 72))}
    failures = [
        f"{box} {name}: beklenen {want}, ölçülen {got:.1f}"
        for box, inks in boxes
        for name, want in inks.items()
        if abs((got := box_mean(seps[name].ink, box)) - want) > TOL
    ]
    assert not failures, "\n".join(failures)
