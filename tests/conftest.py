import pytest
from anki.collection import Collection
from hanky.hanky import Hanky
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
    # close new collection so Hanky can open it itself through the `col` property.
    Collection(str(db_path)).close()

    app = Hanky(
        ANKI_DB_PATH=str(db_path),
        DO_SAFETY_CHECK=False,
        BACKUP_FOLDER=str(tmp_path / "backups"),
    )
    yield app

    if app._col:
        app.col.close()
