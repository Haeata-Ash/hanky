# mypy: disable-error-code="import-untyped"

"""Example hanky script which builds English to French flash cards by *composing*
two card processors:

  1. ``scrape_translation`` scrapes https://www.wordreference.com/ to fill in a
     translation and an example sentence given an English word. When a word has
     several candidate translations you are prompted to pick one.
  2. ``add_audio`` uses AWS Polly (text to speech) to voice the scraped
     translation, attaching the audio as anki media.

Run, e.g.:
    python3 demo_scrape.py pipe words.xlsx
"""

import re
import sys
from typing import NamedTuple

import boto3
import requests
from bs4 import BeautifulSoup

from hanky import CardMedia, HankyPipeline


# WordReference language-pair path (English to French)
WR_PAIR = "enfr"

# See https://docs.aws.amazon.com/polly/latest/dg/available-voices.html
# the voice used to read the French translation.
VOICE = "Lea"

# WordReference returns an empty body to clients without a browser-like UA.
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:152.0) Gecko/20100101 Firefox/152.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip",
    "Referer": "https://www.wordreference.com/",
    "Connection": "keep-alive",
    "Cookie": "WRFavDicts=enfr|fren; nginx_wr_human=1; llang=enfri",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "DNT": "1",
    "Sec-GPC": "1",
    "Priority": "u=0, i",
    "Pragma": "no-cache",
    "Cache-Control": "no-cache",
}


class Translation(NamedTuple):
    """One candidate translation scraped from a WordReference entry."""

    word: str  # the target-language translation, e.g. "bavarder"
    pos: str  # part-of-speech marker, e.g. "vi"
    sense: str  # sense of the source word being translated, e.g. "(talk lightly)"
    note: str  # usage/register note, e.g. "(familier)"
    example: str  # target-language example sentence; may be empty


def scrape_wordreference(word: str, lang_pair: str) -> list[Translation]:
    """Scrape all candidate translations for ``word`` from WordReference.

    Note: WordReference is a third-party site. The page could change and request volumes
    should be kept low.

    Args:
        word: the English head word to look up.
        lang_pair: WordReference language-pair path, e.g. ``"enfr"``.

    Returns:
        Candidate :class:`Translation` s in page order (most common senses first).

    Raises:
        ValueError: no translation could be found for the word.
    """
    url = f"https://www.wordreference.com/{lang_pair}/{word}"
    with requests.Session() as sess:
        resp = sess.get(url, headers=_HEADERS, timeout=10)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find(id="articleWRD")
    if table is None:
        raise ValueError(f"No translation table found for '{word}' at {url}.")

    # Data rows have class 'odd'/'even' and are grouped into senses: a row with an
    # 'id' attribute starts a new sense. Each 'ToWrd' cell is one candidate translation
    # and 'ToEx' cells hold the sense's example sentences.
    candidates: list[Translation] = []
    sense = ""
    examples: list[str] = []  # 'ToEx' sentences of the sense being parsed
    sense_start = 0  # index into candidates of the current sense's first candidate

    def attach_examples() -> None:
        """Give each of the finished sense's candidates its best example: the first
        sentence using the translation, falling back to the sense's first example."""
        for i, cand in enumerate(candidates[sense_start:], sense_start):
            head = cand.word.split(",")[0].split()[0].lower()
            matching = (ex for ex in examples if head in ex.lower())
            example = next(matching, examples[0] if examples else "")
            candidates[i] = cand._replace(example=example)

    # The markup leaves <tr> tags unclosed, so rows nest into
    # each other when parsed.
    # Taking only each row's direct <td> children avoids double-counting
    # cells from nested rows.
    for row in table.find_all("tr", class_=["odd", "even"]):
        if row.get("id"):
            attach_examples()
            sense_start, sense, examples = len(candidates), "", []
        note = ""
        for cell in row.find_all("td", recursive=False):
            classes = cell.get("class") or []
            if "ToWrd" in classes:
                # The nested <em> is the part-of-speech marker; the rest is the
                # translation itself, with '⇒' link arrows sprinkled through it.
                pos_tag = cell.find("em")
                pos = pos_tag.get_text(strip=True) if pos_tag else ""
                if pos_tag:
                    pos_tag.extract()
                text = cell.get_text(" ", strip=True).replace("⇒", "")
                text = re.sub(r"\s*,[\s,]*", ", ", re.sub(r"\s+", " ", text)).strip(
                    " ,"
                )
                if text:
                    candidates.append(Translation(text, pos, sense, note, ""))
                note = ""
            elif "ToEx" in classes:
                if example := cell.get_text(" ", strip=True):
                    examples.append(example)
            elif not classes:
                # Unclassed cells hold prose: the sense gloss on a sense's first row,
                # register notes elsewhere.
                if (text := cell.get_text(" ", strip=True)) and not cell.find("a"):
                    if not sense and row.get("id"):
                        sense = text
                    else:
                        note = text
    attach_examples()

    if not candidates:
        raise ValueError(f"Could not find a translation for '{word}' at {url}.")
    return candidates


def choose_translation(word: str, translations: list[Translation]) -> Translation:
    """Ask the user to pick one of ``translations`` for ``word`` on the terminal.

    Falls back to the first (most common) translation when there is only one or
    when stdin is not interactive.
    """
    if len(translations) == 1 or not sys.stdin.isatty():
        return translations[0]

    print(f"\nTranslations for '{word}':")
    for i, t in enumerate(translations, 1):
        detail = " ".join(
            part for part in (f"[{t.pos}]" if t.pos else "", t.sense, t.note) if part
        )
        print(f"  {i:2}. {t.word}" + (f"  {detail}" if detail else ""))

    while True:
        choice = input(f"Select a translation for '{word}' [1]: ").strip()
        if not choice:
            return translations[0]
        if choice.isdigit() and 1 <= int(choice) <= len(translations):
            return translations[int(choice) - 1]
        print(f"Please enter a number between 1 and {len(translations)}.")


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


# instantiate the hanky app, creating cards with the "lang-vocab" model
hanky = HankyPipeline(
    "lang-vocab",
)


@hanky.card_processor(expected_args=[], required_fields=["word"])
def scrape_translation(card: dict):
    """Get the English 'word' translations from WordReference, let the user pick
    one, and write it and its example sentence to the 'translation' and 'example'
    fields on the card."""

    translations = scrape_wordreference(card["word"], WR_PAIR)
    chosen = choose_translation(card["word"], translations)

    card["translation"] = chosen.word
    card["example"] = chosen.example
    return card


@hanky.card_processor(expected_args=[], required_fields=["translation"])
def add_audio(card: dict):
    """Generate French speech for the 'translation' field and reference the
    resulting anki media in 'translation-audio'."""
    speech = generate_neural_speech(card["translation"], VOICE)

    audio = CardMedia(speech, ".mp3")
    card["translation-audio"] = audio.media_ref

    return card, [audio]


# run the hanky cli application by running this python file, for example:
#   python3 demo_scrape.py pipe words.csv
if __name__ == "__main__":
    hanky.run()
