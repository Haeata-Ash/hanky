from types import MappingProxyType

import pytest


# --- happy path -----------------------------------------------------------


def test_load_cards_adds_every_card_from_the_source(app):
    source = [
        {"Front": "bonjour", "Back": "hello"},
        {"Front": "chat", "Back": "cat"},
    ]

    count = app.load_cards(source, "Basic", "French")

    assert count == 2
    assert app.col.note_count() == 2
    assert app.col.decks.id("French", create=False) is not None


def test_load_cards_creates_the_destination_deck(app):
    app.load_cards([{"Front": "un", "Back": "one"}], "Basic", "French::Numbers")

    assert app.col.decks.id("French::Numbers", create=False) is not None


def test_load_cards_returns_count_of_added_cards_not_items_seen(app):
    # the second item is a duplicate of the first and is not added
    source = [
        {"Front": "bonjour", "Back": "hello"},
        {"Front": "bonjour", "Back": "hello"},
    ]

    count = app.load_cards(source, "Basic", "French")

    assert count == 1
    assert app.col.note_count() == 1


def test_load_cards_accepts_a_non_dict_mapping(app):
    # the source generalisation must accept any Mapping, not only dict.
    # MappingProxyType is a Mapping but not a dict subclass.
    source = [MappingProxyType({"Front": "bonjour", "Back": "hello"})]

    count = app.load_cards(source, "Basic", "French")

    assert count == 1
    assert app.col.note_count() == 1


# --- unknown model --------------------------------------------------------


def test_load_cards_unknown_model_raises_keyerror(app):
    with pytest.raises(KeyError, match="NoSuchModel"):
        app.load_cards([{"Front": "a", "Back": "b"}], "NoSuchModel", "French")


def test_load_cards_unknown_model_does_not_consume_the_source(app):
    consumed = []

    def source():
        for item in [{"Front": "a", "Back": "b"}]:
            consumed.append(item)
            yield item

    with pytest.raises(KeyError):
        app.load_cards(source(), "NoSuchModel", "French")

    # the model check must happen before the source is iterated, so a source
    # with side effects (e.g. a network call) is never touched.
    assert consumed == []


def test_load_cards_unknown_model_does_not_create_a_deck(app):
    with pytest.raises(KeyError):
        app.load_cards([{"Front": "a", "Back": "b"}], "NoSuchModel", "French")

    assert app.col.decks.id("French", create=False) is None


# --- source item validation ----------------------------------------------


@pytest.mark.parametrize("bad_item", ["not a dict", 42, ["Front", "x"], None])
def test_load_cards_non_mapping_item_raises_value_error(app, bad_item):
    with pytest.raises(ValueError, match="dictionary"):
        app.load_cards([bad_item], "Basic", "French")


def test_load_cards_stops_at_the_first_non_mapping_item(app):
    source = [
        {"Front": "bonjour", "Back": "hello"},
        "not a dict",
        {"Front": "chat", "Back": "cat"},
    ]

    with pytest.raises(ValueError, match="dictionary"):
        app.load_cards(source, "Basic", "French")

    # the valid card before the bad item was still added; the one after was not
    assert app.col.note_count() == 1


# --- generator as a source ------------------------------------------------


def test_load_cards_accepts_a_generator_source(app):
    def gen():
        yield {"Front": "un", "Back": "one"}
        yield {"Front": "deux", "Back": "two"}

    count = app.load_cards(gen(), "Basic", "French")

    assert count == 2
    assert app.col.note_count() == 2


def test_load_cards_fully_consumes_a_one_shot_generator(app):
    def gen():
        yield {"Front": "un", "Back": "one"}
        yield {"Front": "deux", "Back": "two"}
        yield {"Front": "trois", "Back": "three"}

    source = gen()
    count = app.load_cards(source, "Basic", "French")

    assert count == 3
    # the generator is exhausted, proving it was the actual data source
    assert list(source) == []


def test_load_cards_empty_source_adds_nothing_but_creates_the_deck(app):
    count = app.load_cards(iter([]), "Basic", "French")

    assert count == 0
    assert app.col.note_count() == 0
    assert app.col.decks.id("French", create=False) is not None
