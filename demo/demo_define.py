# mypy: disable-error-code="import-untyped"

import nltk
from nltk.corpus import wordnet

from hanky import Hanky


# WordNet ships as NLTK data rather than with the library itself, so make sure
# the corpus is present (this is a no-op once it has been downloaded once).
nltk.download("wordnet", quiet=True)

# WordNet's single-letter part-of-speech tags, mapped to readable labels.
_POS_LABELS = {
    "n": "noun",
    "v": "verb",
    "a": "adjective",
    "s": "adjective",
    "r": "adverb",
}


def define(word: str) -> str:
    """Return a dictionary definition for ``word`` using WordNet.

    The first (most common) sense is used, prefixed with its part of speech,
    e.g. ``"(noun) good luck in making unexpected ... discoveries"``.

    Args:
        word: the English word to define.

    Returns:
        A human-readable definition string.

    Raises:
        ValueError: WordNet has no entry for the word.
    """
    senses = wordnet.synsets(word)
    if not senses:
        raise ValueError(f"No definition found for '{word}'.")

    primary = senses[0]
    pos = _POS_LABELS.get(primary.pos(), primary.pos())
    return f"({pos}) {primary.definition()}"


# instantiate the hanky app
hanky = Hanky()


@hanky.card_processor("basic", expected_args=[], card_fields=["Front"])
def define_word(card: dict):
    """Set the back of each card to the definition of the word on the front"""
    card["Back"] = define(card["Front"])
    return card


# run the hanky cli application by running this python file, for example:
#   python3 demo_define.py load basic words.csv -d english::vocab
hanky.run()
