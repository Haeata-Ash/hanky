import pytest
from hanky.config import Config
from hanky.hanky import Hanky


def test_add_deck_creates_deck(app):
    col = app._open_collection()
    app.add_deck(col, "French")

    assert col.decks.id("French", create=False) is not None


def test_add_card_adds_a_note(app):
    col = app._open_collection()
    app.add_deck(col, "French")

    added = app.add_card(col, "French", "Basic", Front="bonjour", Back="hello")

    assert added is True
    assert col.note_count() == 1


def test_add_card_strips_whitespace_from_fields(app):
    col = app._open_collection()
    app.add_deck(col, "French")
    app.add_card(col, "French", "Basic", Front="  bonjour  ", Back="hello")

    note = col.get_note(col.find_notes("")[0])

    assert note["Front"] == "bonjour"


def test_add_card_rejects_duplicate(app):
    col = app._open_collection()
    app.add_deck(col, "French")
    app.add_card(col, "French", "Basic", Front="bonjour", Back="hello")

    added_again = app.add_card(col, "French", "Basic", Front="bonjour", Back="hello")

    assert added_again is False
    assert col.note_count() == 1


def test_add_card_unknown_model_raises(app):
    col = app._open_collection()
    app.add_deck(col, "French")

    with pytest.raises(ValueError):
        app.add_card(col, "French", "NoSuchModel", Front="a", Back="b")


def test_add_card_unknown_deck_raises(app):
    col = app._open_collection()

    with pytest.raises(ValueError):
        app.add_card(col, "NoSuchDeck", "Basic", Front="a", Back="b")


def test_add_card_missing_field_raises(app):
    col = app._open_collection()
    app.add_deck(col, "French")

    with pytest.raises(KeyError):
        app.add_card(col, "French", "Basic", Front="only the front")


def test_col_raises_when_db_path_missing(tmp_path):
    missing = tmp_path / "does_not_exist.anki2"
    app = Hanky(Config(ANKI_DB_PATH=str(missing), DO_SAFETY_CHECK=False))

    with pytest.raises(FileNotFoundError):
        _ = app._open_collection()
