import pytest

from hanky.anki_utils import add_card, add_deck


def test_add_deck_creates_deck(app):
    col = app._open_collection()
    add_deck(col, "French")

    assert col.decks.id("French", create=False) is not None


def test_add_card_adds_a_note(app):
    col = app._open_collection()
    add_deck(col, "French")

    added = add_card(col, "French", "Basic", Front="bonjour", Back="hello")

    assert added is True
    assert col.note_count() == 1


def test_add_card_strips_whitespace_from_fields(app):
    col = app._open_collection()
    add_deck(col, "French")
    add_card(col, "French", "Basic", Front="  bonjour  ", Back="hello")

    note = col.get_note(col.find_notes("")[0])

    assert note["Front"] == "bonjour"


def test_add_card_rejects_duplicate(app):
    col = app._open_collection()
    add_deck(col, "French")
    add_card(col, "French", "Basic", Front="bonjour", Back="hello")

    added_again = add_card(col, "French", "Basic", Front="bonjour", Back="hello")

    assert added_again is False
    assert col.note_count() == 1


def test_add_card_allows_duplicate_when_enabled(app):
    col = app._open_collection()
    add_deck(col, "French")
    add_card(col, "French", "Basic", Front="bonjour", Back="hello")

    added_again = add_card(
        col, "French", "Basic", allow_duplicates=True, Front="bonjour", Back="hello"
    )

    assert added_again is True
    assert col.note_count() == 2


def test_add_card_unknown_model_raises(app):
    col = app._open_collection()
    add_deck(col, "French")

    with pytest.raises(ValueError):
        add_card(col, "French", "NoSuchModel", Front="a", Back="b")


def test_add_card_unknown_deck_raises(app):
    col = app._open_collection()

    with pytest.raises(ValueError):
        add_card(col, "NoSuchDeck", "Basic", Front="a", Back="b")


def test_add_card_missing_field_raises(app):
    col = app._open_collection()
    add_deck(col, "French")

    with pytest.raises(KeyError):
        add_card(col, "French", "Basic", Front="only the front")
