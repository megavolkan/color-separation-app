"""Ghostscript bulma ve paketlenmiş uygulamada ortam değişkenleri."""

import sys

import pytest

from ayrim import gs as gsmod


def test_frozen_linux_restores_library_path(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("LD_LIBRARY_PATH", "/uygulama/_internal")
    monkeypatch.setenv("LD_LIBRARY_PATH_ORIG", "/usr/lib/ozel")
    assert gsmod.subprocess_env()["LD_LIBRARY_PATH"] == "/usr/lib/ozel"

    monkeypatch.delenv("LD_LIBRARY_PATH_ORIG")
    assert "LD_LIBRARY_PATH" not in gsmod.subprocess_env()


def test_not_frozen_keeps_environment(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert gsmod.subprocess_env() is None


def test_broken_gs_is_reported(monkeypatch, tmp_path):
    fake = tmp_path / "gs"
    fake.write_text("#!/bin/sh\necho 'gs: symbol lookup error: libtiff.so.6' >&2\nexit 127\n")
    fake.chmod(0o755)
    if sys.platform == "win32":
        pytest.skip("kabuk betiği Windows'ta çalışmaz")
    monkeypatch.setenv("AYRIM_GS", str(fake))
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setattr(gsmod, "_EXTRA_GS_PATHS", [])
    with pytest.raises(gsmod.GhostscriptNotFound, match="(?s)çalıştırılamadı.*symbol lookup error"):
        gsmod.find_ghostscript()
