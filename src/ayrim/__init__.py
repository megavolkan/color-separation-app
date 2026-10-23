"""Ayrım: PDF renk ayrımı önizleyicisi."""

from importlib.metadata import PackageNotFoundError, version

# Sürüm numarasının tek kaynağı pyproject.toml'dur.
try:
    __version__ = version("ayrim")
except PackageNotFoundError:  # pragma: no cover - kurulmadan çalıştırılırsa
    __version__ = "0+bilinmiyor"
