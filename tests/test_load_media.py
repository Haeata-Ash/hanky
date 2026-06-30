from hanky.media import CardMedia


def test_media_written_and_temp_ref_replaced(app):
    media = CardMedia(b"fake-audio-bytes", ".mp3")
    temp_ref = media.media_ref

    def add_audio(card):
        card["Back"] = f"{card['Back']} {temp_ref}"
        return card, media

    app.register_card_processor("Basic", add_audio)

    report = app.load_cards([{"Front": "chien", "Back": "dog"}], "Basic", "French")

    assert report.added == 1

    col = app._open_collection()
    note = col.get_note(col.find_notes("")[0])

    assert temp_ref not in note["Back"]
    assert "[sound:" in note["Back"]
    assert col.media.have(media.desired_name)


def test_load_cards_accumulates_media_from_a_list(app):
    one = CardMedia(b"audio-one", ".mp3")
    two = CardMedia(b"audio-two", ".mp3")

    def add_two(card):
        card["Front"] = f"{card['Front']} {one.media_ref} {two.media_ref}"
        return card, [one, two]

    app.register_card_processor("Basic", add_two)

    report = app.load_cards([{"Front": "chat", "Back": "cat"}], "Basic", "French")

    assert report.added == 1

    col = app._open_collection()
    note = col.get_note(col.find_notes("")[0])

    assert one._temp_ref_uuid not in note["Front"]
    assert two._temp_ref_uuid not in note["Front"]
    assert col.media.have(one.desired_name)
    assert col.media.have(two.desired_name)
