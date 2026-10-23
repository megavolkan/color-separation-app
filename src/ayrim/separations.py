"""tiffsep çıktısını okuma, kalıp listesi ve piksel → mürekkep dönüşümü."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote_to_bytes

import numpy as np
from PIL import Image

from .gs import RenderResult

PROCESS_NAMES = ("Cyan", "Magenta", "Yellow", "Black")


def ink_from_pixel(pixels: np.ndarray) -> np.ndarray:
    """tiffsep kalıp pikselini mürekkep oranına (0..1) çevirir.

    Ghostscript 10.x ile test PDF'lerinde doğrulandı: 0 = %100 mürekkep, 255 = mürekkep yok
    (C100 kutusu 0, M50 kutusu 128, Y25 kutusu 192 okundu). Bu ilişki yalnızca burada tanımlıdır.
    """
    return 1.0 - pixels.astype(np.float32) / 255.0


def decode_separation_name(encoded: str) -> str:
    """tiffsep dosya adındaki kalıp adını çözer.

    Ghostscript dosya adına uygun olmayan baytları %XX biçiminde yazar
    (örn. '/' → %2F, '%' → %25, ':' → %3A). Boşluk, parantez vb. olduğu gibi kalır.
    """
    raw = unquote_to_bytes(encoded)
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def separation_files(result: RenderResult) -> dict[str, Path]:
    """Kalıp adı → tiff dosyası. Ad, 'p<N>(' öneki ile ').tif' soneki arasındaki her şeydir.

    Ghostscript 10.08 öneke çıktı dosyasının uzantısını da katar: 'p1.tif(Cyan).tif'.
    """
    prefixes = (f"{result.stem}(", f"{result.composite.name}(")
    out: dict[str, Path] = {}
    for f in result.directory.iterdir():
        n = f.name
        for prefix in prefixes:
            if n.startswith(prefix) and n.endswith(").tif"):
                out[decode_separation_name(n[len(prefix) : -len(").tif")])] = f
                break
    return out


@dataclass
class Separation:
    name: str
    ink: np.ndarray  # float32, H×W, 0..1

    @property
    def is_process(self) -> bool:
        return self.name in PROCESS_NAMES

    @property
    def used(self) -> bool:
        return bool(self.ink.max() > 0)

    def coverage(self) -> float:
        """Sayfadaki ortalama mürekkep oranı (0..1)."""
        return float(self.ink.mean())


def load_separations(result: RenderResult) -> list[Separation]:
    """Kalıpları okur: önce CMYK (sırasıyla), sonra spot renkler alfabetik."""
    files = separation_files(result)
    if not files:
        produced = ", ".join(sorted(f.name for f in result.directory.iterdir())) or "hiçbir dosya"
        raise ValueError(f"{result.directory} içinde kalıp dosyası yok. Bulunanlar: {produced}")
    order = [n for n in PROCESS_NAMES if n in files]
    order += sorted((n for n in files if n not in PROCESS_NAMES), key=str.casefold)
    seps = []
    for name in order:
        with Image.open(files[name]) as im:
            if im.mode != "L":
                im = im.convert("L")
            seps.append(Separation(name, ink_from_pixel(np.asarray(im))))
    return seps
