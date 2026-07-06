from functools import partial

import pytest

from hanky.media import CardMedia
from hanky.processors import CardProcessingException, CardProcessor


def compose(processors, card, **model_args):
    """Mimick processor composition/chaining in the hanky class for tests"""
    media = []
    for p in processors:
        card, new_media = p(card, **model_args)
        media += new_media
    return card, media


def _processor_returning(value):
    """A CardProcessor whose function returns ``value`` regardless of input."""
    return CardProcessor(lambda card: value, [], [])


def test_two_processors_run_in_order():
    def add_back(card):
        card["Back"] = "translated"
        return card

    def shout(card):
        card["Back"] = card["Back"].upper()
        return card

    first = CardProcessor(add_back, [], [])
    second = CardProcessor(shout, [], ["Back"])

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
        CardProcessor(needs_lang, ["lang"], []),
        CardProcessor(needs_voice, ["voice"], []),
    ]

    card, _ = compose(procs, {"Front": "x"}, lang="french", voice="Lea")

    assert seen == {"lang": "french", "voice": "Lea"}
    assert card == {"Front": "x"}


def test_processor_with_no_declared_args_is_called_with_only_the_card():
    """If this fails with an error it likely means we pass in all args"""

    def no_args(card):
        return card

    p = CardProcessor(no_args, [], [])

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
        CardProcessor(first, [], []),
        CardProcessor(second, [], []),
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
        CardProcessor(producer, [], []),
        CardProcessor(consumer, [], ["target-lang"]),
    ]

    card, _ = compose(procs, {})

    assert card["target-lang"] == "bonjour"


def test_missing_declared_arg_raises_keyerror_for_the_right_processor():
    def needs_voice(card, voice):
        return card

    procs = [
        CardProcessor(lambda card: card, [], []),
        CardProcessor(needs_voice, ["voice"], []),
    ]

    with pytest.raises(KeyError, match="voice"):
        compose(procs, {"Front": "x"})


def test_missing_required_field_raises_keyerror():
    p = CardProcessor(lambda card: card, [], ["Back"])

    with pytest.raises(KeyError, match="Back"):
        p({"Front": "x"})


def test_error_in_processor_is_wrapped_in_card_processing_exception():
    def boom(card):
        raise ValueError("kaboom")

    p = CardProcessor(boom, [], [])

    with pytest.raises(CardProcessingException):
        p({"Front": "x"})


def test_wrapped_exception_preserves_original_as_cause():
    original = ValueError("kaboom")

    def boom(card):
        raise original

    p = CardProcessor(boom, [], [])

    with pytest.raises(CardProcessingException) as exc_info:
        p({"Front": "x"})

    assert exc_info.value.__cause__ is original


def test_wrapped_exception_names_the_failing_processor():
    def translate(card):
        raise RuntimeError("api down")

    p = CardProcessor(translate, [], [])

    with pytest.raises(CardProcessingException, match="translate"):
        p({"Front": "x"})


def test_wrapped_exception_exposes_processor_attribute():
    def translate(card):
        raise RuntimeError("api down")

    p = CardProcessor(translate, [], [])

    with pytest.raises(CardProcessingException) as exc_info:
        p({"Front": "x"})

    assert exc_info.value.processor is translate


def test_validation_errors_are_not_wrapped_as_card_processing_exception():
    missing_field = CardProcessor(lambda card: card, [], ["Back"])
    with pytest.raises(KeyError):
        missing_field({"Front": "x"})
    assert not isinstance(KeyError, CardProcessingException)

    missing_arg = CardProcessor(lambda card, voice: card, ["voice"], [])
    with pytest.raises(KeyError) as exc_info:
        missing_arg({"Front": "x"})
    assert not isinstance(exc_info.value, CardProcessingException)


def test_keyboard_interrupt_is_not_swallowed():
    def interrupt(card):
        raise KeyboardInterrupt

    p = CardProcessor(interrupt, [], [])

    with pytest.raises(KeyboardInterrupt):
        p({"Front": "x"})


def test_wrapped_exception_includes_card_context():
    def boom(card):
        raise RuntimeError("api down")

    p = CardProcessor(boom, [], [])

    with pytest.raises(CardProcessingException) as exc_info:
        p({"Front": "chien"})

    # the processor is model-agnostic: it knows the card but not the model,
    # which is supplied later by HankyPipeline (see test_load.py).
    assert "chien" in str(exc_info.value)
    assert exc_info.value.card == {"Front": "chien"}
    assert exc_info.value.model is None


def test_wrapping_works_for_callables_without_a_name():
    def translate(card, lang):
        raise RuntimeError("api down")

    # partial is a valid Callable processor but has no __name__
    proc = partial(translate, lang="fr")
    p = CardProcessor(proc, [], [])

    with pytest.raises(CardProcessingException) as exc_info:
        p({"Front": "x"})

    assert exc_info.value.__cause__.args == ("api down",)
    assert exc_info.value.processor is proc


# --- return value normalisation -------------------------------------------
# Every processor return shape should be normalised to
# Tuple[Dict[str, str], List[CardMedia]].


def test_bare_dict_is_normalised_to_card_and_empty_media():
    card = {"Front": "x"}
    p = _processor_returning(card)

    result_card, media = p({"Front": "x"})

    assert result_card is card
    assert media == []


def test_card_and_single_media_is_normalised_to_card_and_list():
    m = CardMedia(b"audio", ".mp3")
    p = _processor_returning(({"Front": "x"}, m))

    result_card, media = p({"Front": "x"})

    assert result_card == {"Front": "x"}
    assert media == [m]


def test_card_and_media_list_is_returned_as_is():
    m1 = CardMedia(b"one", ".mp3")
    m2 = CardMedia(b"two", ".mp3")
    p = _processor_returning(({"Front": "x"}, [m1, m2]))

    result_card, media = p({"Front": "x"})

    assert result_card == {"Front": "x"}
    assert media == [m1, m2]


def test_card_and_empty_media_list_is_returned_as_is():
    p = _processor_returning(({"Front": "x"}, []))

    result_card, media = p({"Front": "x"})

    assert result_card == {"Front": "x"}
    assert media == []


@pytest.mark.parametrize("bad_return", [None, 42, "card", ["Front", "x"]])
def test_non_dict_non_tuple_return_raises_value_error(bad_return):
    p = _processor_returning(bad_return)

    with pytest.raises(ValueError, match="card dict"):
        p({"Front": "x"})


@pytest.mark.parametrize("bad_return", [({"Front": "x"},), ({"Front": "x"}, [], 1)])
def test_tuple_of_wrong_length_raises_value_error(bad_return):
    p = _processor_returning(bad_return)

    with pytest.raises(ValueError, match="card dict"):
        p({"Front": "x"})


def test_tuple_with_unsupported_media_raises_value_error():
    p = _processor_returning(({"Front": "x"}, "not-media"))

    with pytest.raises(ValueError, match="normalise"):
        p({"Front": "x"})


def test_tuple_with_non_dict_card_raises_value_error():
    p = _processor_returning(("not-a-dict", [CardMedia(b"a", ".mp3")]))

    with pytest.raises(ValueError, match="normalise"):
        p({"Front": "x"})
