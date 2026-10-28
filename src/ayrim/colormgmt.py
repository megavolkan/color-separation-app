"""CMYK kalıplarını ICC profiliyle ekran rengine (sRGB) çevirme.

Önizleme, belgenin CMYK profiliyle (çıktı amacı ya da gömülü CMYK ICC profili, örn. Coated
FOGRA39) yapılır; belgede yoksa Ghostscript'in kendi varsayılan CMYK profili kullanılır.
Dönüşüm Little CMS (Pillow ImageCms) ile, göreli kolorimetrik amaç ve siyah nokta
dengelemesiyle yapılır; tasarım programlarının ekran önizlemesiyle aynı yöntemdir.
"""

from __future__ import annotations

import glob
import io
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageCms

from .composite import RGB
from .docdetails import read_icc


def is_cmyk_icc(data: bytes) -> bool:
    return len(data) >= 132 and data[36:40] == b"acsp" and data[16:20] == b"CMYK"


def profile_name(data: bytes) -> str:
    info = read_icc(data)
    return info.name if info else "(adsız profil)"


def ghostscript_cmyk_profile(gs_path: str | None) -> Path | None:
    """Kurulu Ghostscript'in default_cmyk.icc dosyası (Homebrew, Windows, Linux düzenleri)."""
    roots: list[Path] = []
    if gs_path:
        for p in dict.fromkeys((Path(gs_path), Path(os.path.realpath(gs_path)))):
            roots += [p.parent.parent, p.parent]  # <önek>/bin/gs → <önek>
    patterns = []
    for root in roots:
        patterns += [
            str(root / "share" / "ghostscript" / "*" / "iccprofiles" / "default_cmyk.icc"),
            str(root / "share" / "ghostscript" / "iccprofiles" / "default_cmyk.icc"),
            str(root / "iccprofiles" / "default_cmyk.icc"),  # Windows: C:\Program Files\gs\gs10.x
        ]
    patterns += [
        "/usr/share/color/icc/ghostscript/default_cmyk.icc",
        "/usr/share/ghostscript/*/iccprofiles/default_cmyk.icc",
    ]
    for pattern in patterns:
        hits = sorted(glob.glob(pattern), reverse=True)
        if hits:
            return Path(hits[0])
    return None


@dataclass(frozen=True)
class ProfileSource:
    name: str  # profilin adı (desc etiketi)
    origin: str  # "belgeden" | "Ghostscript varsayılanı"
    data: bytes


class CmykPreview:
    """Bir CMYK profili → sRGB dönüşümü."""

    def __init__(self, source: ProfileSource) -> None:
        self.source = source
        profile = ImageCms.ImageCmsProfile(io.BytesIO(source.data))
        self._transform = ImageCms.buildTransform(
            profile,
            ImageCms.createProfile("sRGB"),
            "CMYK",
            "RGB",
            renderingIntent=ImageCms.Intent.RELATIVE_COLORIMETRIC,
            flags=ImageCms.Flags.BLACKPOINTCOMPENSATION,
        )

    @property
    def label(self) -> str:
        return f"{self.source.name} ({self.source.origin})"

    def to_rgb(self, cmyk: np.ndarray) -> np.ndarray:
        """H×W×4 mürekkep (float 0..1 ya da uint8) → H×W×3 uint8 sRGB."""
        if cmyk.dtype != np.uint8:
            cmyk = np.clip(cmyk * 255.0 + 0.5, 0, 255).astype(np.uint8)
        im = Image.fromarray(np.ascontiguousarray(cmyk), "CMYK")
        return np.asarray(ImageCms.applyTransform(im, self._transform))

    def color(self, c: float, m: float, y: float, k: float) -> RGB:
        px = self.to_rgb(np.array([[[c, m, y, k]]], dtype=np.float32))[0, 0]
        return (px[0] / 255, px[1] / 255, px[2] / 255)


def choose_profile(doc_profile: bytes | None, gs_path: str | None) -> CmykPreview | None:
    """Önce belgenin CMYK profili, yoksa Ghostscript'inki; ikisi de yoksa None (basit önizleme)."""
    candidates: list[tuple[bytes, str]] = []
    if doc_profile and is_cmyk_icc(doc_profile):
        candidates.append((doc_profile, "belgeden"))
    gs_icc = ghostscript_cmyk_profile(gs_path)
    if gs_icc is not None:
        try:
            candidates.append((gs_icc.read_bytes(), "Ghostscript varsayılanı"))
        except OSError:
            pass
    for data, origin in candidates:
        try:
            return CmykPreview(ProfileSource(profile_name(data), origin, data))
        except Exception:  # bozuk ya da desteklenmeyen profil: sıradakini dene
            continue
    return None
