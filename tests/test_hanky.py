"""Tests for the core :class:`hanky.hanky.Hanky` object.

Safety: these tests must *never* touch a real anki collection.
  * ``no_real_config`` (autouse) redirects the default config path to a file
    that doesn't exist, so ``Hanky`` can never pick up the user's real config
    (which points at their real collection).
  * ``app`` builds a throwaway collection inside pytest's ``tmp_path``.

Scope: simple positive/negative cases only. Edge cases come later.
"""

import pytest
from anki.collection import Collection

import hanky.hanky as hanky_module
from hanky.hanky import Hanky


@pytest.fixture(autouse=True)
def fake_default_config(tmp_path, monkeypatch):
    """Useful if testing on a system with default config file which
    we don't want to use
    """
    monkeypatch.setattr(
        hanky_module, "DEFAULT_CONFIG_PATH", tmp_path / "no_such_config.toml"
    )


@pytest.fixture
def app(tmp_path):
    """A Hanky app backed by a fresh, empty, temporary anki collection."""
    db_path = tmp_path / "collection.anki2"
    # close new collection so Hanky can open it itself through the `col` property.
    Collection(str(db_path)).close()

    app = Hanky(ANKI_DB_PATH=str(db_path), DO_SAFETY_CHECK=False)
    yield app

    if app._col:
        app.col.close()


def test_add_deck_creates_deck(app):
    app.add_deck("French")

    assert app.col.decks.id("French", create=False) is not None


def test_add_card_adds_a_note(app):
    app.add_deck("French")

    added = app.add_card("French", "Basic", Front="bonjour", Back="hello")

    assert added is True
    assert app.col.note_count() == 1


def test_add_card_strips_whitespace_from_fields(app):
    app.add_deck("French")
    app.add_card("French", "Basic", Front="  bonjour  ", Back="hello")

    note = app.col.get_note(app.col.find_notes("")[0])

    assert note["Front"] == "bonjour"


def test_add_card_rejects_duplicate(app):
    app.add_deck("French")
    app.add_card("French", "Basic", Front="bonjour", Back="hello")

    added_again = app.add_card("French", "Basic", Front="bonjour", Back="hello")

    assert added_again is False
    assert app.col.note_count() == 1


def test_add_card_unknown_model_raises(app):
    app.add_deck("French")

    with pytest.raises(ValueError):
        app.add_card("French", "NoSuchModel", Front="a", Back="b")


def test_add_card_unknown_deck_raises(app):
    with pytest.raises(ValueError):
        app.add_card("NoSuchDeck", "Basic", Front="a", Back="b")


def test_add_card_missing_field_raises(app):
    app.add_deck("French")

    with pytest.raises(KeyError):
        app.add_card("French", "Basic", Front="only the front")


def test_col_raises_when_db_path_missing(tmp_path):
    missing = tmp_path / "does_not_exist.anki2"
    app = Hanky(ANKI_DB_PATH=str(missing), DO_SAFETY_CHECK=False)

    with pytest.raises(FileNotFoundError):
        _ = app.col
