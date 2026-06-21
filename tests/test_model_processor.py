import pytest

from hanky.media import CardMedia
from hanky.processors import ModelProcessor


def compose(processors, card, **model_args):
    """Mimick processor composition/chaining in the hanky class for tests"""
    media = []
    for p in processors:
        card, new_media = p(card, **model_args)
        media += new_media
    return card, media


def test_two_processors_run_in_order():
    def add_back(card):
        card["Back"] = "translated"
        return card

    def shout(card):
        card["Back"] = card["Back"].upper()
        return card

    first = ModelProcessor("Basic", add_back, [], [])
    second = ModelProcessor("Basic", shout, [], ["Back"])

    card, media = compose([first, second], {"Front": "hello"})

    assert card == {"Front": "hello", "Back": "TRANSLATED"}
    assert media == []


def test_each_processor_only_receives_the_args_it_declares():
    """If this fails with an error it likely means we pass in all args"""
    seen = {}

    def needs_lang(card, lang):
        seen["lang"] = lang
        return card

    def needs_voice(card, voice):
        seen["voice"] = voice
        return card

    procs = [
        ModelProcessor("Basic", needs_lang, ["lang"], []),
        ModelProcessor("Basic", needs_voice, ["voice"], []),
    ]

    card, _ = compose(procs, {"Front": "x"}, lang="french", voice="Lea")

    assert seen == {"lang": "french", "voice": "Lea"}
    assert card == {"Front": "x"}


def test_processor_with_no_declared_args_is_called_with_only_the_card():
    """If this fails with an error it likely means we pass in all args"""

    def no_args(card):
        return card

    p = ModelProcessor("Basic", no_args, [], [])

    card, _ = p({"Front": "x"}, lang="french", voice="Lea")

    assert card == {"Front": "x"}


def test_accumulate_media_from_every_processor():
    m1 = CardMedia(b"one", ".mp3")
    m2 = CardMedia(b"two", ".mp3")

    def first(card):
        card["A"] = m1.media_ref
        return card, [m1]

    def second(card):
        card["B"] = m2.media_ref
        return card, [m2]

    procs = [
        ModelProcessor("Basic", first, [], []),
        ModelProcessor("Basic", second, [], []),
    ]

    card, media = compose(procs, {"Front": "x"})

    assert media == [m1, m2]
    assert card["A"] == m1.media_ref
    assert card["B"] == m2.media_ref


def test_downstream_processor_sees_fields_written_by_an_upstream_one():
    """card_fields of a later processor can be satisfied by an earlier one."""

    def producer(card):
        card["target-lang"] = "bonjour"
        return card

    def consumer(card):
        assert card["target-lang"] == "bonjour"
        return card

    procs = [
        ModelProcessor("lang-vocab", producer, [], []),
        ModelProcessor("lang-vocab", consumer, [], ["target-lang"]),
    ]

    card, _ = compose(procs, {})

    assert card["target-lang"] == "bonjour"


def test_missing_declared_arg_raises_keyerror_for_the_right_processor():
    def needs_voice(card, voice):
        return card

    procs = [
        ModelProcessor("Basic", lambda card: card, [], []),
        ModelProcessor("Basic", needs_voice, ["voice"], []),
    ]

    with pytest.raises(KeyError, match="voice"):
        compose(procs, {"Front": "x"})  # voice never supplied


def test_missing_required_field_raises_keyerror():
    p = ModelProcessor("Basic", lambda card: card, [], ["Back"])

    with pytest.raises(KeyError, match="Back"):
        p({"Front": "x"})
