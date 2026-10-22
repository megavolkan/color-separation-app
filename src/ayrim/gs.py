"""Ghostscript bulma, tiffsep ile sayfa işleme ve önbellek."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

# Finder'dan açılan macOS uygulamaları Homebrew PATH'ini görmez; bu yollara da bakılır.
_EXTRA_GS_PATHS = [
    "/opt/homebrew/bin/gs",
    "/usr/local/bin/gs",
    "/opt/local/bin/gs",
    "/usr/bin/gs",
]

# -sOverprint ayarı Ghostscript 9.53+ ile geldi; -dSimulateOverprint artık desteklenmiyor.
MIN_GS_VERSION = (9, 53)

# Ghostscript çağrı biçimi değişince artırılır; eski önbellek kullanılmaz.
CACHE_VERSION = 2


class GhostscriptError(RuntimeError):
    pass


class GhostscriptNotFound(GhostscriptError):
    pass


@dataclass(frozen=True)
class Ghostscript:
    path: str
    version: str

    @property
    def version_tuple(self) -> tuple[int, ...]:
        return tuple(int(p) for p in self.version.split(".") if p.isdigit())


def find_ghostscript() -> Ghostscript:
    """`gs` yolunu ve sürümünü bulur; bulunamazsa GhostscriptNotFound fırlatır."""
    candidates = []
    env = os.environ.get("AYRIM_GS")
    if env:
        candidates.append(env)
    which = shutil.which("gs")
    if which:
        candidates.append(which)
    candidates += _EXTRA_GS_PATHS
    for path in candidates:
        if not (os.path.isfile(path) and os.access(path, os.X_OK)):
            continue
        try:
            out = subprocess.run(
                [path, "--version"], capture_output=True, text=True, timeout=10, check=True
            )
        except (OSError, subprocess.SubprocessError):
            continue
        gs = Ghostscript(path, out.stdout.strip())
        if gs.version_tuple < MIN_GS_VERSION:
            raise GhostscriptNotFound(
                f"Ghostscript {gs.version} çok eski ({path}); en az "
                f"{'.'.join(map(str, MIN_GS_VERSION))} gerekli."
            )
        return gs
    hint = (
        "brew install ghostscript" if sys.platform == "darwin" else "pacman -S ghostscript"
    )
    raise GhostscriptNotFound(f"Ghostscript (gs) bulunamadı. Kurulum: {hint}")


def default_cache_dir() -> Path:
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Caches"
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / "ayrim"


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass(frozen=True)
class RenderResult:
    """Bir sayfanın tiffsep çıktısı: kompozit dosya ve kalıp dosyaları."""

    directory: Path
    page: int
    dpi: int
    overprint: bool

    @property
    def stem(self) -> str:
        return f"p{self.page}"

    @property
    def composite(self) -> Path:
        return self.directory / f"{self.stem}.tif"


class Renderer:
    """tiffsep çağrılarını önbellekle yönetir. Arayüzden bağımsızdır."""

    def __init__(self, gs: Ghostscript | None = None, cache_dir: Path | None = None) -> None:
        self.gs = gs or find_ghostscript()
        self.cache_dir = Path(cache_dir) if cache_dir else default_cache_dir()
        self._hashes: dict[tuple[str, float, int], str] = {}

    def _hash(self, pdf: Path) -> str:
        st = pdf.stat()
        key = (str(pdf.resolve()), st.st_mtime, st.st_size)
        if key not in self._hashes:
            self._hashes[key] = file_hash(pdf)
        return self._hashes[key]

    def cache_path(self, pdf: Path, page: int, dpi: int, overprint: bool) -> Path:
        op = "op" if overprint else "noop"
        return self.cache_dir / self._hash(pdf)[:24] / f"v{CACHE_VERSION}_p{page}_{dpi}dpi_{op}"

    def render(self, pdf: Path | str, page: int, dpi: int = 150, overprint: bool = True) -> RenderResult:
        """Sayfayı işler (önbellekte varsa yeniden işlemez). Sayfa numarası 1'den başlar."""
        pdf = Path(pdf)
        target = self.cache_path(pdf, page, dpi, overprint)
        result = RenderResult(target, page, dpi, overprint)
        if (target / ".done").exists():
            return result
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = Path(tempfile.mkdtemp(prefix=".tmp_", dir=target.parent))
        cmd = [
            self.gs.path,
            "-q",
            "-dSAFER",
            "-dBATCH",
            "-dNOPAUSE",
            "-sDEVICE=tiffsep",
            f"-r{dpi}",
            f"-dFirstPage={page}",
            f"-dLastPage={page}",
            f"-sOverprint={'simulate' if overprint else 'disable'}",
            # Gömülü ICC profillerini yok say: ICCBased CMYK değerleri (Affinity, PDF/X)
            # Ghostscript'in kendi CMYK profiline dönüştürülmeden olduğu gibi kalıplara gider.
            # Bu olmadan 0/100/100/0 bir renk örneğin 2/79/100/0 olarak ölçülüyordu.
            "-dOverrideICC",
            "-o",
            str(tmp / f"p{page}.tif"),
            str(pdf),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0 or not (tmp / f"p{page}.tif").exists():
            shutil.rmtree(tmp, ignore_errors=True)
            msg = (proc.stderr or proc.stdout).strip()
            raise GhostscriptError(f"Ghostscript sayfa {page} işlenemedi: {msg[-2000:]}")
        (tmp / ".done").touch()
        try:
            tmp.rename(target)
        except OSError:
            # Aynı anda başka bir iş aynı sayfayı bitirmiş olabilir.
            shutil.rmtree(tmp, ignore_errors=True)
            if not (target / ".done").exists():
                raise
        return result
