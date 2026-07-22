import hashlib

import pytest

from hanky.media import CardMedia


def test_desired_name_is_sha256_of_data_plus_ext():
    data = b"some-audio-bytes"
    media = CardMedia(data, ".mp3")

    assert media.desired_name == hashlib.sha256(data).hexdigest() + ".mp3"


def test_supported_audio_extensions_ref():
    data = b"some-audio-bytes"

    media = CardMedia(data, ".mp3")
    the_ref = f"[sound:{media._temp_ref_uuid}]"
    assert media.media_ref == the_ref


def test_unsupported_extension_raises():
    with pytest.raises(ValueError):
        CardMedia(b"data", ".png")


def test_temp_ref_is_unique_per_instance_even_for_identical_data():
    a = CardMedia(b"same", ".mp3")
    b = CardMedia(b"same", ".mp3")

    assert a._temp_ref_uuid != b._temp_ref_uuid


def test_from_file_reads_bytes_and_extension(tmp_path):
    f = tmp_path / "clip.mp3"
    f.write_bytes(b"file-bytes")

    media = CardMedia.from_file(str(f))

    assert media.data == b"file-bytes"
    assert media.desired_name == hashlib.sha256(b"file-bytes").hexdigest() + ".mp3"


def test_replace_temp_refs_substitutes_the_actual_name():
    media = CardMedia(b"data", ".mp3")
    card = {"Front": "bonjour", "Back": media.media_ref}

    media.replace_temp_refs("real_name.mp3", card)

    assert media._temp_ref_uuid not in card["Back"]
    assert "real_name.mp3" in card["Back"]


def test_replace_temp_refs_replaces_every_occurrence_in_a_field():
    media = CardMedia(b"data", ".mp3")
    card = {"Back": f"{media.media_ref} and again {media.media_ref}"}

    media.replace_temp_refs("real_name.mp3", card)

    assert media._temp_ref_uuid not in card["Back"]
    assert card["Back"].count("real_name.mp3") == 2


def test_replace_temp_refs_leaves_unrelated_fields_untouched():
    media = CardMedia(b"data", ".mp3")
    card = {"Front": "bonjour", "Back": media.media_ref}

    media.replace_temp_refs("real_name.mp3", card)

    assert card["Front"] == "bonjour"
