# mypy: disable-error-code="import-untyped"

from typing import IO

import boto3
import pandas
import requests
from bs4 import BeautifulSoup

from hanky import CardMedia, HankyPipeline

"""Example hanky script which builds English to French flash cards by *composing*
two card processors:

  1. ``scrape_translation`` scrapes https://www.wordreference.com/ to fill in a
     translation and an example sentence given an English word.
  2. ``add_audio`` uses AWS Polly (text to speech) to voice the scraped
     translation, attaching the audio as anki media.

Run, e.g.:
    python3 demo_scrape.py pipe words.xlsx --model lang-vocab
"""


# WordReference language-pair path (English to French)
WR_PAIR = "enfr"

# See https://docs.aws.amazon.com/polly/latest/dg/available-voices.html
# the voice used to read the French translation.
VOICE = "Lea"

# WordReference returns an empty body to clients without a browser-like UA.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120 Safari/537.36"
    )
}


def scrape_wordreference(word: str, lang_pair: str) -> tuple[str, str]:
    """Scrape a translation and example sentence for ``word`` from WordReference.

    Note: WordReference is a third-party site. The page could change and request volumes
    should be kept low.

    Args:
        word: the English head word to look up.
        lang_pair: WordReference language-pair path, e.g. ``"enfr"``.

    Returns:
        A ``(translation, example)`` tuple. ``example`` may be an empty string
        if the entry has no target-language example sentence.

    Raises:
        ValueError: no translation could be found for the word.
    """
    url = f"https://www.wordreference.com/{lang_pair}/{word}"
    resp = requests.get(url, headers=_HEADERS, timeout=10)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find(id="articleWRD")
    if table is None:
        raise ValueError(f"No translation table found for '{word}' at {url}.")

    # The first data row (class 'odd'/'even') with a non-empty 'ToWrd' cell holds
    # the primary translation. The leading text node is the word itself; the
    # nested <em> is the part-of-speech marker (e.g. 'nm'), which we drop.
    translation = ""
    for row in table.find_all("tr", class_=["odd", "even"]):
        to_word = row.find("td", class_="ToWrd")
        if to_word and to_word.get_text(strip=True):
            head = to_word.find(string=True)
            translation = head.strip() if head else ""
            if translation:
                break

    if not translation:
        raise ValueError(f"Could not find a translation for '{word}' at {url}.")

    # First target-language example sentence anywhere in the table, if present.
    example_cell = table.find("td", class_="ToEx")
    example = example_cell.get_text(" ", strip=True) if example_cell else ""

    return translation, example


def generate_neural_speech(utf_8_str: str, voice: str) -> bytes:
    """Generate speech (audio) from text using AWS Polly. Requires a free aws
    account and boto credentials configured on this machine.

    AWS Polly: https://aws.amazon.com/polly/pricing/
    Boto3 Credentials: https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html
    """
    client = boto3.client("polly")
    res = client.synthesize_speech(
        Engine="neural", OutputFormat="mp3", Text=utf_8_str, VoiceId=voice
    )
    return res["AudioStream"].read()


# instantiate the hanky app
hanky = HankyPipeline()


def excel_loader(f_obj: IO):
    """Load card fields and values from an excel file.

    Args:
        f_obj: file object to read from.
    Yields:
        dictionary of fields mapped to their values.
    """
    df = pandas.read_excel(f_obj)
    for _, row in df.iterrows():
        yield row.to_dict()


# register the loader against the ".xlsx" extension
hanky.register_loader(".xlsx", excel_loader, is_text=False)


@hanky.card_processor("lang-vocab", expected_args=[], card_fields=["word"])
def scrape_translation(card: dict):
    """Get the English 'word' translation and example sentene from WordReference
    and write them to the 'translation' and 'example' fields on the card."""

    translation, example = scrape_wordreference(card["word"], WR_PAIR)

    card["translation"] = translation
    card["example"] = example
    return card


@hanky.card_processor("lang-vocab", expected_args=[], card_fields=["translation"])
def add_audio(card: dict):
    """Generate French speech for the 'translation' field and reference the
    resulting anki media in 'translation-audio'."""
    speech = generate_neural_speech(card["translation"], VOICE)

    audio = CardMedia(speech, ".mp3")
    card["translation-audio"] = audio.media_ref

    return card, [audio]


# run the hanky cli application by running this python file, for example:
#   python3 demo_scrape.py pipe words.xlsx --model lang-vocab
hanky.run()
