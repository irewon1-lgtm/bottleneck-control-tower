import pytest
from bct.config import Settings
from bct.db import migrate, session_factory


@pytest.fixture(autouse=True)
def isolate_synthetic_actions_identity(monkeypatch):
    """Unit fixtures opt into Actions identity explicitly, even on CI runners."""
    monkeypatch.delenv('GITHUB_ACTIONS', raising=False)


@pytest.fixture
def setup(tmp_path):
    settings = Settings(tmp_path / "var")
    migrate(settings)
    return settings, session_factory(settings)
