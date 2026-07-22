import pytest

from hanky.config import Config
from hanky.errors import CollectionInUseError, CollectionNotFoundError
from hanky.hanky import HankyPipeline


def test_col_raises_when_db_path_missing(tmp_path):
    missing = tmp_path / "does_not_exist.anki2"
    app = HankyPipeline(
        "Basic", config=Config(ANKI_DB_PATH=str(missing), DO_SAFETY_CHECK=False)
    )

    with pytest.raises(CollectionNotFoundError):
        _ = app._open_collection()


def test_col_raises_when_in_use_by_another_process(tmp_path, monkeypatch):
    db_path = tmp_path / "collection.anki2"
    db_path.touch()
    app = HankyPipeline(
        "Basic", config=Config(ANKI_DB_PATH=str(db_path), DO_SAFETY_CHECK=True)
    )

    monkeypatch.setattr("hanky.hanky.has_handle", lambda _: True)

    with pytest.raises(CollectionInUseError):
        _ = app._open_collection()


def test_nested_sessions_keep_the_collection_open_until_the_outer_scope_exits(app):
    # start from a closed collection so the outermost session is the opener
    app._close_collection()

    with app.session() as outer:
        with app.session() as inner:
            # the inner session must hand back the same live collection
            assert inner is outer
        # leaving the inner scope must NOT close the collection, because the
        # inner scope did not open it: it is still the same live, usable handle
        assert app._col is outer
        assert outer.note_count() == 0

    # only the outer scope (which opened it) closes the collection on exit
    assert app._col is None


def test_session_closes_the_collection_when_the_body_raises(app):
    app._close_collection()

    with pytest.raises(RuntimeError, match="boom"):
        with app.session():
            assert app._col is not None
            raise RuntimeError("boom")

    # the finally clause must close and drop the collection even on error, so a
    # later session can re-open cleanly
    assert app._col is None
    with app.session() as col:
        assert col is not None
