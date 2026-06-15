import pytest
from anki.collection import Collection
from hanky.hanky import Hanky
import hanky.hanky as hanky_module


@pytest.fixture(autouse=True)
def fake_default_config(tmp_path, monkeypatch):
    """Useful if testing on a system with default config file which
    we don't want to use
    """
    monkeypatch.setattr(
        hanky_module, "_DEFAULT_CONFIG_PATH", tmp_path / "no_such_config.toml"
    )


@pytest.fixture(autouse=True)
def app(tmp_path, fake_default_config):
    """A Hanky app backed by a fresh, empty, temporary anki collection."""
    db_path = tmp_path / "collection.anki2"
    # close new collection so Hanky can open it itself through the `col` property.
    Collection(str(db_path)).close()

    app = Hanky(ANKI_DB_PATH=str(db_path), DO_SAFETY_CHECK=False)
    yield app

    if app._col:
        app.col.close()
