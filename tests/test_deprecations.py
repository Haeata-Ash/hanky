"""The pre-0.2.0 names (the ``Hanky`` class and the ``load_*`` methods) were
renamed but kept as deprecated aliases. These tests pin that they still work
and emit a ``DeprecationWarning`` until they are removed in 0.3.0.
"""

import pytest

from hanky import Hanky, HankyPipeline
from hanky.config import Config


def test_hanky_class_is_a_deprecated_alias(tmp_path):
    from anki.collection import Collection

    db_path = tmp_path / "legacy.anki2"
    Collection(str(db_path)).close()

    with pytest.warns(DeprecationWarning, match="HankyPipeline"):
        legacy = Hanky(Config(ANKI_DB_PATH=str(db_path), DO_SAFETY_CHECK=False))

    assert isinstance(legacy, HankyPipeline)


def test_load_cards_is_a_deprecated_alias(app):
    with pytest.warns(DeprecationWarning, match="import_from_source"):
        report = app.load_cards([{"Front": "chien", "Back": "dog"}], "Basic", "French")

    assert report.added == 1


def test_load_deck_is_a_deprecated_alias(app, tmp_path):
    fpath = tmp_path / "French.json"
    fpath.write_text('{"Front": "chat", "Back": "cat"}')

    with pytest.warns(DeprecationWarning, match="import_from_file"):
        report = app.load_deck(str(fpath), "Basic")

    assert report.added == 1


def test_load_dir_is_a_deprecated_alias(app, tmp_path):
    root = tmp_path / "French"
    root.mkdir()
    (root / "animals.csv").write_text("Front,Back\nchien,dog\n")

    with pytest.warns(DeprecationWarning, match="import_from_dir"):
        report = app.load_dir("Basic", str(root), "*.csv")

    assert report.added == 1
