import random
from typing import Iterator

from hanky import HankyPipeline


# A small word/meaning dictionary to draw cards from. In a real script this
# could come from anywhere: an API, a database, a scraped page, and so on.
DICTIONARY = {
    "ephemeral": "lasting for a very short time",
    "serendipity": "the occurrence of happy events by chance",
    "petrichor": "the smell of rain falling on dry ground",
    "lucid": "expressed clearly and easy to understand",
    "gregarious": "fond of the company of others; sociable",
    "quell": "to put an end to, usually by force",
    "candid": "truthful and straightforward; frank",
    "nebulous": "vague or ill-defined",
    "wane": "to decrease in size, extent, or strength",
    "zenith": "the highest point reached by something",
    "austere": "severe or strict in manner or appearance",
    "placate": "to make someone less angry or hostile",
    "verbose": "using more words than are needed",
    "tenacious": "holding firmly to something; persistent",
    "fervent": "having or showing intense feeling",
    "mundane": "lacking interest or excitement; dull",
    "elated": "very happy and excited",
    "frugal": "sparing or economical with money or food",
    "opaque": "not able to be seen through; not transparent",
    "rescind": "to revoke, cancel, or repeal",
    "salient": "most noticeable or important",
    "trepidation": "a feeling of fear about something that may happen",
    "ubiquitous": "present or found everywhere",
    "venerate": "to regard with great respect",
}


def random_word_cards(n: int) -> Iterator[dict]:
    """Yield ``n`` cards, each a random word and its meaning from DICTIONARY.

    Args:
        n: how many cards to generate.

    Yields:
        A dict with the word on ``Front`` and its meaning on ``Back``.
    """
    for word in random.sample(list(DICTIONARY), n):
        yield {"Front": word, "Back": DICTIONARY[word]}


hanky = HankyPipeline("basic")

# import_from_source takes any iterable of dicts, so the cards can come straight
# from the generator above without ever touching a file.
report = hanky.import_from_source(random_word_cards(20), "english::vocab")

print(f"Added {report.added}, skipped {report.skipped}, failed {report.failed}.")
