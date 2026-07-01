import pytest
from hanky.config import Config
from hanky.hanky import HankyPipeline


def test_col_raises_when_db_path_missing(tmp_path):
    missing = tmp_path / "does_not_exist.anki2"
    app = HankyPipeline(Config(ANKI_DB_PATH=str(missing), DO_SAFETY_CHECK=False))

    with pytest.raises(FileNotFoundError):
        _ = app._open_collection()
