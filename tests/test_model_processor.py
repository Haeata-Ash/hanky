from functools import partial

import pytest

from hanky.media import CardMedia
from hanky.processors import CardProcessingException, ModelProcessor


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
        compose(procs, {"Front": "x"})


def test_missing_required_field_raises_keyerror():
    p = ModelProcessor("Basic", lambda card: card, [], ["Back"])

    with pytest.raises(KeyError, match="Back"):
        p({"Front": "x"})


def test_error_in_processor_is_wrapped_in_card_processing_exception():
    def boom(card):
        raise ValueError("kaboom")

    p = ModelProcessor("Basic", boom, [], [])

    with pytest.raises(CardProcessingException):
        p({"Front": "x"})


def test_wrapped_exception_preserves_original_as_cause():
    original = ValueError("kaboom")

    def boom(card):
        raise original

    p = ModelProcessor("Basic", boom, [], [])

    with pytest.raises(CardProcessingException) as exc_info:
        p({"Front": "x"})

    assert exc_info.value.__cause__ is original


def test_wrapped_exception_names_the_failing_processor():
    def translate(card):
        raise RuntimeError("api down")

    p = ModelProcessor("Basic", translate, [], [])

    with pytest.raises(CardProcessingException, match="translate"):
        p({"Front": "x"})


def test_wrapped_exception_exposes_processor_attribute():
    def translate(card):
        raise RuntimeError("api down")

    p = ModelProcessor("Basic", translate, [], [])

    with pytest.raises(CardProcessingException) as exc_info:
        p({"Front": "x"})

    assert exc_info.value.processor is translate


def test_validation_errors_are_not_wrapped_as_card_processing_exception():
    missing_field = ModelProcessor("Basic", lambda card: card, [], ["Back"])
    with pytest.raises(KeyError):
        missing_field({"Front": "x"})
    assert not isinstance(KeyError, CardProcessingException)

    missing_arg = ModelProcessor("Basic", lambda card, voice: card, ["voice"], [])
    with pytest.raises(KeyError) as exc_info:
        missing_arg({"Front": "x"})
    assert not isinstance(exc_info.value, CardProcessingException)


def test_keyboard_interrupt_is_not_swallowed():
    def interrupt(card):
        raise KeyboardInterrupt

    p = ModelProcessor("Basic", interrupt, [], [])

    with pytest.raises(KeyboardInterrupt):
        p({"Front": "x"})


def test_wrapped_exception_includes_model_and_card_context():
    def boom(card):
        raise RuntimeError("api down")

    p = ModelProcessor("French Vocab", boom, [], [])

    with pytest.raises(CardProcessingException) as exc_info:
        p({"Front": "chien"})

    message = str(exc_info.value)
    assert "French Vocab" in message
    assert "chien" in message
    assert exc_info.value.model == "French Vocab"
    assert exc_info.value.card == {"Front": "chien"}


def test_wrapping_works_for_callables_without_a_name():
    def translate(card, lang):
        raise RuntimeError("api down")

    # partial is a valid Callable processor but has no __name__
    proc = partial(translate, lang="fr")
    p = ModelProcessor("Basic", proc, [], [])

    with pytest.raises(CardProcessingException) as exc_info:
        p({"Front": "x"})

    assert exc_info.value.__cause__.args == ("api down",)
    assert exc_info.value.processor is proc
