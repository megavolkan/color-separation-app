"""Kalıpları ekranda birleştirme ve TAC hesabı.

CMYK kalıpları birlikte, bir ICC profiliyle sRGB'ye çevrilir (`colormgmt.CmykPreview`).
Spot kalıplar ve profil yoksa tüm kalıplar, beyazdan başlayarak `rgb *= 1 - t * (1 - c)`
ile çarpılarak eklenir.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

import numpy as np

from .separations import PROCESS_NAMES

RGB = tuple[float, float, float]

# Profil bulunamazsa CMYK kalıpları için sabit sRGB karşılıkları (0..1).
PROCESS_RGB: dict[str, RGB] = {
    "Cyan": (0 / 255, 174 / 255, 239 / 255),
    "Magenta": (236 / 255, 0 / 255, 140 / 255),
    "Yellow": (255 / 255, 242 / 255, 0 / 255),
    "Black": (35 / 255, 31 / 255, 32 / 255),
}


def composite(plates: Sequence[tuple[np.ndarray, RGB]], shape: tuple[int, int] | None = None) -> np.ndarray:
    """(mürekkep, renk) çiftlerini birleştirir; H×W×3 uint8 sRGB döner."""
    if shape is None:
        if not plates:
            raise ValueError("Kalıp yok ve boyut verilmedi")
        shape = plates[0][0].shape
    rgb = np.ones((*shape, 3), dtype=np.float32)
    for ink, color in plates:
        c = np.asarray(color, dtype=np.float32)
        rgb *= 1.0 - ink[..., None] * (1.0 - c)
    return np.clip(rgb * 255.0 + 0.5, 0, 255).astype(np.uint8)


def composite_cmyk(
    to_rgb: Callable[[np.ndarray], np.ndarray],
    process: dict[str, np.ndarray],
    others: Sequence[tuple[np.ndarray, RGB]],
    shape: tuple[int, int],
) -> np.ndarray:
    """CMYK kalıplarını profille çevirir, diğerlerini (spot) üzerine çarpar. H×W×3 uint8.

    process: kalıp adı → mürekkep; olmayan kalıp boş sayılır. to_rgb: H×W×4 uint8 → H×W×3 uint8.
    """
    cmyk = np.zeros((*shape, 4), dtype=np.uint8)
    for i, name in enumerate(PROCESS_NAMES):
        if name in process:
            cmyk[..., i] = np.clip(process[name] * 255.0 + 0.5, 0, 255).astype(np.uint8)
    base = to_rgb(cmyk)
    if not others:
        return base
    rgb = base.astype(np.float32) / 255.0
    for ink, color in others:
        c = np.asarray(color, dtype=np.float32)
        rgb *= 1.0 - ink[..., None] * (1.0 - c)
    return np.clip(rgb * 255.0 + 0.5, 0, 255).astype(np.uint8)


def grayscale(ink: np.ndarray) -> np.ndarray:
    """Tek kalıbı gri tonlu gösterir: siyah = %100 mürekkep. H×W×3 uint8."""
    g = np.clip((1.0 - ink) * 255.0 + 0.5, 0, 255).astype(np.uint8)
    return np.repeat(g[..., None], 3, axis=2)


def total_ink(inks: Sequence[np.ndarray]) -> np.ndarray:
    """Toplam mürekkep (TAC), yüzde cinsinden, H×W float32."""
    if not inks:
        raise ValueError("Kalıp yok")
    tac = np.zeros(inks[0].shape, dtype=np.float32)
    for ink in inks:
        tac += ink
    return tac * 100.0


def inks_at(named: Sequence[tuple[str, np.ndarray]], x: int, y: int) -> tuple[dict[str, float], float]:
    """(x, y) pikselinde her kalıbın yüzdesi ve toplamı."""
    values = {name: float(ink[y, x]) * 100.0 for name, ink in named}
    return values, sum(values.values())


def highlight(rgb: np.ndarray, mask: np.ndarray, color: tuple[int, int, int] = (0, 255, 0), alpha: float = 0.7) -> np.ndarray:
    """Maskelenen pikselleri verilen renkle vurgular (TAC uyarısı için)."""
    out = rgb.copy()
    c = np.asarray(color, dtype=np.float32)
    out[mask] = (out[mask].astype(np.float32) * (1 - alpha) + c * alpha).astype(np.uint8)
    return out
