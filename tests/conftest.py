import sys
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
sys.path.insert(0, str(FIXTURES))

import make_fixtures  # noqa: E402  (içe aktarılınca PDF'leri yeniden üretir)

from ayrim.gs import Renderer, find_ghostscript  # noqa: E402


@pytest.fixture(scope="session")
def renderer(tmp_path_factory) -> Renderer:
    try:
        gs = find_ghostscript()
    except Exception as e:  # pragma: no cover
        pytest.skip(str(e))
    return Renderer(gs, tmp_path_factory.mktemp("cache"))


@pytest.fixture(scope="session")
def expected():
    return make_fixtures.EXPECTED


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return FIXTURES
