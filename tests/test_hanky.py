import pytest
from hanky.config import Config
from hanky.errors import CollectionInUseError
from hanky.hanky import HankyPipeline


def test_col_raises_when_db_path_missing(tmp_path):
    missing = tmp_path / "does_not_exist.anki2"
    app = HankyPipeline(Config(ANKI_DB_PATH=str(missing), DO_SAFETY_CHECK=False))

    with pytest.raises(FileNotFoundError):
        _ = app._open_collection()


def test_col_raises_when_in_use_by_another_process(tmp_path, monkeypatch):
    db_path = tmp_path / "collection.anki2"
    db_path.touch()
    app = HankyPipeline(Config(ANKI_DB_PATH=str(db_path), DO_SAFETY_CHECK=True))

    monkeypatch.setattr("hanky.hanky.has_handle", lambda _: True)

    with pytest.raises(CollectionInUseError):
        _ = app._open_collection()


def test_in_use_error_is_runtime_error_for_back_compat():
    assert issubclass(CollectionInUseError, RuntimeError)
