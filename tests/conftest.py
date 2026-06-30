import pytest
from anki.collection import Collection
from hanky.hanky import Hanky
from hanky.config import Config
import hanky.hanky as hanky_module
import hanky.config as config_module


@pytest.fixture(autouse=True)
def fake_default_config(tmp_path, monkeypatch):
    """Useful if testing on a system with default config file which
    we don't want to use
    """
    monkeypatch.setattr(
        hanky_module, "_DEFAULT_CONFIG_PATH", tmp_path / "no_such_config.toml"
    )


@pytest.fixture(autouse=True)
def fake_default_backup_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(
        config_module,
        "_get_default_backup_folder",
        lambda: str(tmp_path / "default_backups"),
    )


@pytest.fixture(autouse=True)
def app(tmp_path, fake_default_config, fake_default_backup_folder):
    db_path = tmp_path / "collection.anki2"

    # create new collection, then close so it can be opened in test
    Collection(str(db_path)).close()

    app = Hanky(
        Config(
            ANKI_DB_PATH=str(db_path),
            DO_SAFETY_CHECK=False,
            BACKUP_FOLDER=str(tmp_path / "backups"),
        )
    )
    _ = app._open_collection()
    yield app
    app._close_collection()
