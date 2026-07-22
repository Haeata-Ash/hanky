import pytest

from hanky.errors import ModelNotFoundError
from hanky.media import CardMedia


def test_dry_run_does_not_create_the_deck(app):
    app.import_from_source([{"Front": "chien", "Back": "dog"}], "French", dry_run=True)

    assert app._open_collection().decks.id("French", create=False) is None


def test_dry_run_does_not_add_a_card(app):
    report = app.import_from_source(
        [{"Front": "chien", "Back": "dog"}], "French", dry_run=True
    )

    assert report.added == 1
    assert report.total == 1
    assert app._open_collection().note_count() == 0


def test_dry_run_does_not_write_media_but_fills_in_the_field(app):
    media = CardMedia(b"fake-audio-bytes", ".mp3")
    temp_ref = media.media_ref

    def add_audio(card):
        card["Back"] = f"{card['Back']} {temp_ref}"
        return card, media

    app.register_card_processor(add_audio)

    app.import_from_source([{"Front": "chien", "Back": "dog"}], "French", dry_run=True)

    col = app._open_collection()
    assert not col.media.have(media.desired_name)


def test_dry_run_still_reports_processor_errors(app):
    def boom(card):
        raise RuntimeError("api down")

    app.register_card_processor(boom)

    report = app.import_from_source(
        [{"Front": "chien", "Back": "dog"}], "French", dry_run=True
    )

    assert report.failed == 1
    assert report.added == 0


def test_dry_run_still_raises_for_a_missing_model(app):
    app._model = "NoSuchModel"

    with pytest.raises(ModelNotFoundError):
        app.import_from_source([{"Front": "a", "Back": "b"}], "French", dry_run=True)


def test_dry_run_propagates_through_import_from_file(app, tmp_path):
    fpath = tmp_path / "French.csv"
    fpath.write_text("Front,Back\nchien,dog\n")

    report = app.import_from_file(str(fpath), dry_run=True)

    assert report.added == 1
    assert app._open_collection().note_count() == 0
    assert app._open_collection().decks.id("French", create=False) is None


def test_dry_run_propagates_through_import_from_dir(app, tmp_path):
    (tmp_path / "french.csv").write_text("Front,Back\nchien,dog\n")

    report = app.import_from_dir(str(tmp_path), "*.csv", dry_run=True)

    assert report.added == 1
    assert app._open_collection().note_count() == 0
