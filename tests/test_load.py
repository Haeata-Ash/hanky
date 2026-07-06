from types import MappingProxyType

import pytest

from hanky.errors import ModelNotFoundError
from hanky.processors import CardProcessingException


def test_import_from_source_stamps_the_model_onto_a_processor_error(app):
    def boom(card):
        raise RuntimeError("api down")

    app.register_card_processor(boom)

    with pytest.raises(CardProcessingException) as exc_info:
        app.import_from_source(
            [{"Front": "chien", "Back": "dog"}], "French", fail_fast=True
        )

    assert exc_info.value.model == "Basic"
    assert "Basic" in str(exc_info.value)


def test_import_from_source_reports_a_processor_error_with_the_model(app):
    def boom(card):
        raise RuntimeError("api down")

    app.register_card_processor(boom)

    report = app.import_from_source([{"Front": "chien", "Back": "dog"}], "French")

    assert report.failed == 1
    assert "Basic" in report.errors[0].error


def test_import_from_source_adds_every_card_from_the_source(app):
    source = [
        {"Front": "bonjour", "Back": "hello"},
        {"Front": "chat", "Back": "cat"},
    ]

    report = app.import_from_source(source, "French")

    assert report.added == 2
    assert report.total == 2
    assert app._open_collection().note_count() == 2
    assert app._open_collection().decks.id("French", create=False) is not None


def test_import_from_source_creates_the_destination_deck(app):
    app.import_from_source([{"Front": "un", "Back": "one"}], "French::Numbers")

    assert app._open_collection().decks.id("French::Numbers", create=False) is not None


def test_import_from_source_reports_a_dupe_as_skipped(app):
    source = [
        {"Front": "bonjour", "Back": "hello"},
        {"Front": "bonjour", "Back": "hello"},
    ]

    report = app.import_from_source(source, "French")

    assert report.added == 1
    assert report.skipped == 1
    assert report.failed == 0
    assert app._open_collection().note_count() == 1


def test_import_from_source_accepts_a_non_dict_mapping(app):
    source = [MappingProxyType({"Front": "bonjour", "Back": "hello"})]

    report = app.import_from_source(source, "French")

    assert report.added == 1
    assert app._open_collection().note_count() == 1


def test_import_from_source_unknown_model_raises_model_not_found(app):
    app._model = "NoSuchModel"

    with pytest.raises(ModelNotFoundError, match="NoSuchModel"):
        app.import_from_source([{"Front": "a", "Back": "b"}], "French")


def test_import_from_source_unknown_model_does_not_consume_the_source(app):
    app._model = "NoSuchModel"
    consumed = []

    def source():
        for item in [{"Front": "a", "Back": "b"}]:
            consumed.append(item)
            yield item

    with pytest.raises(ModelNotFoundError):
        app.import_from_source(source(), "French")

    # the model check must happen before the source is iterated, so a source
    # with side effects (e.g. a network call) is never touched.
    assert consumed == []


def test_import_from_source_unknown_model_does_not_create_a_deck(app):
    app._model = "NoSuchModel"

    with pytest.raises(ModelNotFoundError):
        app.import_from_source([{"Front": "a", "Back": "b"}], "French")

    assert app._open_collection().decks.id("French", create=False) is None


@pytest.mark.parametrize("bad_item", ["not a dict", 42, ["Front", "x"], None])
def test_import_from_source_collects_a_non_mapping_item_as_an_error(app, bad_item):
    report = app.import_from_source([bad_item], "French")

    assert report.added == 0
    assert report.failed == 1
    assert report.errors[0].card == bad_item
    assert "dictionary" in report.errors[0].error


def test_import_from_source_continues_past_a_non_mapping_item(app):
    source = [
        {"Front": "bonjour", "Back": "hello"},
        "not a dict",
        {"Front": "chat", "Back": "cat"},
    ]

    report = app.import_from_source(source, "French")

    # both valid cards are added; only the bad item is recorded as an error
    assert report.added == 2
    assert report.failed == 1
    assert app._open_collection().note_count() == 2


def test_import_from_source_fail_fast_raises_and_stops_at_the_first_bad_item(app):
    source = [
        {"Front": "bonjour", "Back": "hello"},
        "not a dict",
        {"Front": "chat", "Back": "cat"},
    ]

    with pytest.raises(ValueError, match="dictionary"):
        app.import_from_source(source, "French", fail_fast=True)

    # the valid card before the bad item was still added; the one after was not
    assert app._open_collection().note_count() == 1


def test_import_from_source_collects_a_card_with_a_missing_field_as_an_error(app):
    source = [
        {"Front": "bonjour", "Back": "hello"},
        {"Front": "only the front"},
    ]

    report = app.import_from_source(source, "French")

    assert report.added == 1
    assert report.failed == 1
    assert app._open_collection().note_count() == 1


def test_import_from_source_accepts_a_generator_source(app):
    def gen():
        yield {"Front": "un", "Back": "one"}
        yield {"Front": "deux", "Back": "two"}

    report = app.import_from_source(gen(), "French")

    assert report.added == 2
    assert app._open_collection().note_count() == 2


def test_import_from_source_empty_source_adds_nothing_but_creates_the_deck(app):
    report = app.import_from_source(iter([]), "French")

    assert report.added == 0
    assert report.total == 0
    assert app._open_collection().note_count() == 0
    assert app._open_collection().decks.id("French", create=False) is not None
