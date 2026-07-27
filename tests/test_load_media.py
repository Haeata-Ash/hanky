from pathlib import Path

from hanky.media import CardMedia


def test_media_written_and_referenced_on_the_card(app):
    media = CardMedia(b"fake-audio-bytes", ".mp3")
    ref = media.media_ref

    def add_audio(card):
        card["Back"] = f"{card['Back']} {ref}"
        return card, media

    app.register_card_processor(add_audio)

    report = app.import_from_source([{"Front": "chien", "Back": "dog"}], "French")

    assert report.added == 1

    col = app._open_collection()
    note = col.get_note(col.find_notes("")[0])

    assert ref in note["Back"]
    assert col.media.have(media.desired_name)


def test_import_from_source_accumulates_media_from_a_list(app):
    one = CardMedia(b"audio-one", ".mp3")
    two = CardMedia(b"audio-two", ".mp3")

    def add_two(card):
        card["Front"] = f"{card['Front']} {one.media_ref} {two.media_ref}"
        return card, [one, two]

    app.register_card_processor(add_two)

    report = app.import_from_source([{"Front": "chat", "Back": "cat"}], "French")

    assert report.added == 1

    col = app._open_collection()
    note = col.get_note(col.find_notes("")[0])

    assert one.media_ref in note["Front"]
    assert two.media_ref in note["Front"]
    assert col.media.have(one.desired_name)
    assert col.media.have(two.desired_name)


def test_a_skipped_duplicate_leaves_no_media_behind(app):
    """Media belongs to the card. If the card is rejected as a duplicate, its
    media must never reach the collection."""

    def add_audio(card):
        # media derived from Back, so the duplicate's media is its own file
        # rather than one shared with the card that was added
        media = CardMedia(f"audio-for-{card['Back']}".encode(), ".mp3")
        card["Back"] = f"{card['Back']} {media.media_ref}"
        return card, media

    app.register_card_processor(add_audio)

    # anki dedupes on the first field, so the second card is a duplicate
    # despite carrying a different Back
    source = [{"Front": "chien", "Back": "dog"}, {"Front": "chien", "Back": "hound"}]
    report = app.import_from_source(source, "French")

    assert (report.added, report.skipped) == (1, 1)

    col = app._open_collection()
    assert len(col.media.check().unused) == 0
    # only the added card's media was ever written
    assert len(list(Path(col.media.dir()).iterdir())) == 1


def test_a_failed_card_leaves_no_media_behind(app):
    """A card whose fields don't match the model is rejected by prepare_card,
    which happens before any media is written."""

    def add_audio(card):
        media = CardMedia(f"audio-for-{card['Front']}".encode(), ".mp3")
        card["Back"] = f"{card['Back']} {media.media_ref}"
        return card, media

    app.register_card_processor(add_audio)

    # the processor succeeds, but "Bogus" is not a field on the Basic model,
    # so every card is rejected when its note is built
    source = [
        {"Front": "chien", "Back": "dog", "Bogus": "x"},
        {"Front": "chat", "Back": "cat", "Bogus": "x"},
    ]
    report = app.import_from_source(source, "French")

    assert report.added == 0
    assert report.failed == 2

    col = app._open_collection()
    assert len(col.media.check().unused) == 0
    # nothing was written in the first place, not merely unreferenced
    assert list(Path(col.media.dir()).iterdir()) == []


def test_media_shared_with_an_added_card_survives_a_duplicate(app):
    """Two cards carrying byte-identical media share one file. Rejecting the
    second card must not take the first card's media with it."""
    shared = CardMedia(b"one-and-the-same", ".mp3")

    def add_audio(card):
        card["Back"] = f"{card['Back']} {shared.media_ref}"
        return card, shared

    app.register_card_processor(add_audio)

    source = [{"Front": "chien", "Back": "dog"}, {"Front": "chien", "Back": "dog"}]
    report = app.import_from_source(source, "French")

    assert (report.added, report.skipped) == (1, 1)

    col = app._open_collection()
    assert col.media.have(shared.desired_name)
    assert len(col.media.check().unused) == 0


def test_media_is_taken_back_out_when_adding_the_note_fails(app, monkeypatch):
    """The one remaining window: the card passed every check, its media was
    written, and adding the note failed anyway."""
    media = CardMedia(b"doomed-audio", ".mp3")

    def add_audio(card):
        card["Back"] = f"{card['Back']} {media.media_ref}"
        return card, media

    app.register_card_processor(add_audio)

    col = app._open_collection()
    monkeypatch.setattr(
        type(col),
        "add_note",
        lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("db went away")),
    )

    report = app.import_from_source([{"Front": "chien", "Back": "dog"}], "French")

    assert report.added == 0
    assert report.failed == 1
    assert not col.media.have(media.desired_name)


def test_media_the_collection_already_had_is_not_taken_back_out(app, monkeypatch):
    """Rollback must only remove media this card introduced. A file an
    existing note already references has to survive."""
    shared = CardMedia(b"pre-existing-audio", ".mp3")

    def add_audio(card):
        card["Back"] = f"{card['Back']} {shared.media_ref}"
        return card, shared

    app.register_card_processor(add_audio)

    # first card lands and brings the media with it
    app.import_from_source([{"Front": "chien", "Back": "dog"}], "French")
    col = app._open_collection()
    assert col.media.have(shared.desired_name)

    # a later card reusing that media fails to be added
    monkeypatch.setattr(
        type(col),
        "add_note",
        lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("db went away")),
    )
    report = app.import_from_source([{"Front": "chat", "Back": "cat"}], "French")

    assert report.failed == 1
    assert col.media.have(shared.desired_name)
