# mypy: disable-error-code="import-untyped"

import anthropic
import boto3
import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel

from hanky import CardMedia, HankyPipeline


# Claude model used to write the example sentences. See
# https://docs.claude.com/en/docs/about-claude/models for the model list.
CLAUDE_MODEL = "claude-opus-4-8"

# See https://docs.aws.amazon.com/polly/latest/dg/available-voices.html
# the (French) voice used to read the translation and example sentence.
VOICE = "Lea"


# WordReference language-pair path (English to French).
WR_PAIR = "enfr"

# WordReference returns an empty body to clients without a browser-like UA.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120 Safari/537.36"
    )
}


def scrape_translation(word: str, lang_pair: str) -> str:
    """Scrape the primary translation for ``word`` from WordReference.

    Note: WordReference is a third-party site. The page could change and request
    volumes should be kept low.

    Args:
        word: the English head word to look up.
        lang_pair: WordReference language-pair path, e.g. ``"enfr"``.

    Returns:
        The primary translation of ``word``.

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
    for row in table.find_all("tr", class_=["odd", "even"]):
        to_word = row.find("td", class_="ToWrd")
        if to_word and to_word.get_text(strip=True):
            head = to_word.find(string=True)
            translation = head.strip() if head else ""
            if translation:
                return translation

    raise ValueError(f"Could not find a translation for '{word}' at {url}.")


class ExampleSentence(BaseModel):
    """An example sentence and its English translation."""

    french: str
    english: str


def generate_example_sentence(translation: str, level: str) -> ExampleSentence:
    """Ask Claude for a French example sentence using ``translation``.

    Uses structured outputs so the response is guaranteed to match
    ``ExampleSentence``. Requires the ``ANTHROPIC_API_KEY`` environment variable.

    Anthropic API: https://docs.claude.com/en/api/overview

    Args:
        translation: the French word the sentence should use.
        level: the target CEFR level, e.g. ``"A2"`` or ``"B1"``.

    Returns:
        The French example sentence and its English translation.
    """
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment

    response = client.messages.parse(
        model=CLAUDE_MODEL,
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Write a single natural French example sentence that uses the "
                    f"word '{translation}', pitched at CEFR level {level}. Keep the "
                    f"vocabulary and grammar appropriate for that level, then give a "
                    f"faithful English translation of your sentence."
                ),
            }
        ],
        output_format=ExampleSentence,
    )

    return response.parsed_output


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


@hanky.card_processor("lang-vocab", expected_args=[], card_fields=["word"])
def add_translation(card: dict):
    """Look up the English 'word' on WordReference and write the French
    'translation' onto the card."""
    card["translation"] = scrape_translation(card["word"], WR_PAIR)
    return card


@hanky.card_processor(
    "lang-vocab", expected_args=["level"], card_fields=["word", "translation"]
)
def add_example(card: dict, level):
    """Generate a French example sentence at the CEFR 'level' from the
    'translation', writing the French sentence and its English gloss onto the
    card. The English gloss goes on the front alongside the word."""
    example = generate_example_sentence(card["translation"], level)
    card["example-french"] = example.french
    card["example-english"] = example.english
    return card


@hanky.card_processor(
    "lang-vocab", expected_args=[], card_fields=["translation", "example-french"]
)
def add_audio(card: dict):
    """Generate French speech for both the 'translation' and the
    'example-french' sentence, referencing the resulting anki media in the
    'translation-audio' and 'example-audio' fields."""
    word_audio = CardMedia(generate_neural_speech(card["translation"], VOICE), ".mp3")
    example_audio = CardMedia(
        generate_neural_speech(card["example-french"], VOICE), ".mp3"
    )

    card["translation-audio"] = word_audio.media_ref
    card["example-audio"] = example_audio.media_ref

    return card, [word_audio, example_audio]


# run the hanky cli application by running this python file, for example:
#   python3 demo_example_sentences.py load lang-vocab words.csv --args level=B1
hanky.run()
