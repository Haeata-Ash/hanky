import pytest
from hanky.config import Config
from hanky.hanky import Hanky


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
    app = Hanky(Config(ANKI_DB_PATH=str(missing), DO_SAFETY_CHECK=False))

    with pytest.raises(FileNotFoundError):
        _ = app.col
