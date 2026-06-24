import io
import json

import pytest

from hanky.fs import json_loader


def test_json_loader_reads_a_list_of_objects():
    f = io.StringIO(json.dumps([{"Front": "un", "Back": "one"}, {"Front": "deux"}]))

    cards = list(json_loader(f))

    assert cards == [{"Front": "un", "Back": "one"}, {"Front": "deux"}]


def test_json_loader_reads_a_single_object_as_one_card():
    f = io.StringIO(json.dumps({"Front": "un", "Back": "one"}))

    cards = list(json_loader(f))

    assert cards == [{"Front": "un", "Back": "one"}]


@pytest.mark.parametrize("top_level", [42, "a string", True])
def test_json_loader_rejects_other_top_level_shapes(top_level):
    f = io.StringIO(json.dumps(top_level))

    with pytest.raises(ValueError, match="object or a list"):
        list(json_loader(f))


def test_load_deck_reads_a_single_object_json_file(app, tmp_path):
    fpath = tmp_path / "french.json"
    fpath.write_text(json.dumps({"Front": "bonjour", "Back": "hello"}))

    report = app.load_deck(str(fpath), "Basic")

    assert report.added == 1
    assert app.col.note_count() == 1


def test_get_loader_unknown_extension_raises_helpful_value_error(app):
    with pytest.raises(ValueError, match=r"\.txt"):
        app.get_loader(".txt")


def test_get_loader_matches_extension_case_insensitively(app):
    assert app.get_loader(".CSV") is app.get_loader(".csv")


def test_register_loader_is_case_insensitive(app):
    app.register_loader(".XML", lambda f: iter([]))

    assert app.get_loader(".xml") is not None


def test_load_deck_reads_an_uppercase_extension(app, tmp_path):
    fpath = tmp_path / "FRENCH.CSV"
    fpath.write_text("Front,Back\nbonjour,hello\n")

    report = app.load_deck(str(fpath), "Basic")

    assert report.added == 1
    assert app.col.note_count() == 1
