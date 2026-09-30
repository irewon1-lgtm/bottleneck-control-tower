import pytest
from bct.config import Settings
from bct.db import migrate, session_factory


@pytest.fixture
def setup(tmp_path):
    settings = Settings(tmp_path / "var")
    migrate(settings)
    return settings, session_factory(settings)
