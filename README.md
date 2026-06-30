# hanky: A CLI Application For Generating Anki Decks

[![Hatch project](https://img.shields.io/badge/%F0%9F%A5%9A-Hatch-4051b5.svg)](https://github.com/pypa/hatch)

Hanky is an extendable cli tool which loads flash cards from files, transforms them, then adds them to
Anki.

For example, a single hanky pipeline might take an English word and:

1. scrape a French translation and example sentence from a dictionary site, then
2. generate spoken audio of that translation with a text-to-speech service,

turning a one-column spreadsheet into rich, audio-enabled cards.

*Hanky is not affiliated or associated with the [Anki application/org](https://apps.ankiweb.net/).*

## Table of Contents

- [Installation](#installation)
- [Quickstart](#quickstart)
- [Configuration](#configuration)
- [Card Processors & Pipelines](#card-processors--pipelines)
  - [The processor contract](#the-processor-contract)
  - [Pipelines with multiple processors](#pipelines-with-multiple-processors)
  - [Attaching media](#attaching-media)
- [Custom file loaders](#custom-file-loaders)
- [Loading from non-file sources](#loading-from-non-file-sources)
- [Examples](#examples)
- [CLI Reference](#cli-reference)
- [Development](#development)
- [Publishing](#publishing)

## Installation

```sh
pip install hanky
```

## Quickstart

The idea is simple. You extend hanky in your own python script `my_script.py` by writing functions called **card processors**. These functions contain the logic to transform cards. Hanky then handles the cli interface, calling your processors, and finally adding the cards to anki.

To illustrate what this looks like in practice, we will create a simple hanky script which ensures all the text on a card is lower case.


See [Card Processors & Pipelines](#card-processors--pipelines) or the [demo folder](/demo/) for more complex, real world examples.

```python
# my_script.py
from hanky import Hanky


# instantiate the hanky app
hanky = Hanky()


@hanky.card_processor("basic", expected_args=[], card_fields=[])
def lowercase_card(card: dict):
    """Lower-case the text on every field of the card."""
    return {field: value.lower() for field, value in card.items()}


# run the hanky cli application by running this python file, for example:
#   python3 my_script.py load basic words.csv -d english::vocab
hanky.run()

```

### Running your hanky script

You run a hanky script like you would any other python script. 

Given **words.csv**:

```csv
Front,Back
Serendipity,A Pleasant Surprise
Ephemeral,Lasting A VERY Short Time
```


We would run our new script like so

```sh
python3 my_script.py load basic words.csv --deck english::vocab
```

Here we tell hanky to **load** each line of the **words.csv**, transform each line of the csv with the *lowercase_card* card processor, before finally adding each card, of type **basic**, into the anki deck **english::vocab**.

This would leave us with a **english::vocab** deck containing the following cards:

| Front | Back |
| --- | --- |
| serendipity | a pleasant surprise |
| ephemeral | lasting a very short time |



> **Note:** hanky only *adds* cards, media, and decks. The Anki **models/note types**
> you load into must already exist in your collection — create them in Anki's UI
> first. See [Adding a Note Type](https://docs.ankiweb.net/editing.html#adding-a-note-type).


## Configuration

There are two ways to configure Hanky; via a configuration file or via a configuration object. 

**You will only need configuration if you do not use the default Anki profile (`User 1`).**


#### 1. Via TOML file at `~/.config/hanky/hanky.toml`** (loaded automatically if present):

```toml
# Path to the Anki collection (the sqlite db Anki stores cards in).
# Required only if you do NOT use the default profile, "User 1".
# Defaults:
#   Linux:  ~/.local/share/Anki2/User 1/collection.anki2
#   macOS:  ~/Library/Application Support/Anki2/User 1/collection.anki2
ANKI_DB_PATH = "~/.local/share/Anki2/User 1/collection.anki2"

# Check whether another process (e.g. Anki itself) is using the collection
# before opening it. Default: true. Disabling this risks database corruption.
DO_SAFETY_CHECK = true

# Allow cards whose fields duplicate an existing card. Default: false.
ALLOW_DUPLICATES = false

# Where hanky writes backups of the collection.
# Default: ~/.local/share/hanky/backups
BACKUP_FOLDER = "~/.local/share/hanky/backups"
```

**2. A `Config` object passed to `Hanky(...)`** in your script (takes precedence
over the file). Useful if you want different config for different scripts:

```python
from hanky import Hanky
from hanky.config import Config

hanky = Hanky(config=Config(ALLOW_DUPLICATES=True))
```

## Card Processors & Pipelines

A **card processor** is a Python function that runs on each card *before* it is
added to Anki. You could use one to enrich a card (fetch a translation, generate audio) or
transform it (lower-case a field, render LaTeX).

Multiple processors can be registered on a `Hanky` app to create a pipeline.

### The processor contract

A processor is registered with three things:

```python
@hanky.card_processor(model, expected_args=[...], card_fields=[...])
def my_processor(card: dict, **expected_args):
    ...
```

| Part | Meaning |
| --- | --- |
| `model` | The Anki model/note-type name. The processor runs on every card of this model. |
| `card_fields` | Fields that **must already be present** on the card when this processor runs. Hanky checks this and raises a clear error if one is missing. It lets a processor declare what an *earlier* step must have produced. |
| `expected_args` | Names of CLI arguments the processor needs. They are passed in from the command line via `--args key=value` and arrive as keyword arguments. For example, you might have the same pipeline for different languages, so you would pass in `lang=german` or `lang=french`|

When hanky calls your processors, the first argument is always the `card`; a plain `dict` representing a a cards fields. Any declared `expected_args` are then passed in as key word arguments. So if you declared


```python
@hanky.card_processor(model, expected_args=["lang"], card_fields=[...])
def my_processor(card: dict, lang):
    ...
```

Your processor could be called like:

```python
my_processor(card, lang="german")
```


A processor must **return** one of:

- `card` — the (modified) dict, when it adds no media;
- `(card, media)` — a card plus a single [`CardMedia`](#attaching-media);
- `(card, [media, ...])` — a card plus a list of media.

Whatever changes a processor makes to a `card` become visible to every processor
that runs after it.

### Pipelines with multiple processors

If you register more than one processor they form a pipeline. They run in the order you registered them, each receiving the card in the state the previous one returned it. 

This example below builds flash cards for learning french vocabulary as an english speaker. Given a spreadsheet whose only column is `word`:


| Word |
| --- |
| thanks |
| hello |
| ... |
| goodbye |

We want to creates flash cards with the french translation/definition, an example sentence (in both french and english), and french speech audio for the example sentence.

The two processors in our pipeline will be:

1. `scrape_translation`: takes an english `word` and scrapes a website to produce a `translation` and an `example`.
2. `add_audio` — takes the `translation` and `example` produced in step 1 then produces French
   audio.

Note that for brevity the `scrape_wordreference` and `generate_neural_speech` functions are not included. See the [full demo file](/demo/demo_scrape.py) for the complete code.

```python
from hanky import CardMedia, Hanky

def scrape_wordreference(word: str, lang_pair: str) -> tuple[str, str]:
    ...

def generate_neural_speech(utf_8_str: str, voice: str) -> bytes:
    ...

hanky = Hanky()

# Stage 1: requires `word` (this comes straight from the csv), produces `translation` + `example`.
@hanky.card_processor("lang-vocab", expected_args=[], card_fields=["word"])
def scrape_translation(card: dict):
    translation, example = scrape_wordreference(card["word"], "enfr")
    card["translation"] = translation
    card["example"] = example
    return card

# Stage 2: requires `translation` (from stage 1), attaches audio media.
@hanky.card_processor("lang-vocab", expected_args=[], card_fields=["translation"])
def add_audio(card: dict):
    speech = generate_neural_speech(card["translation"], voice="Lea")
    audio = CardMedia(speech, ".mp3")
    card["translation-audio"] = audio.media_ref
    return card, [audio]

hanky.run()
```

Then we would run the script like normal. `python3 my_script.py load lang-vocab words.xlsx -d french::vocab`

> Note that we are no longer using a *basic* model. That means we are assuming that a model called *lang-vocab* has already been created in the anki ui. See the [Anki documentation for adding a note type](https://docs.ankiweb.net/editing.html#adding-a-note-type) to learn how this is done.


### Attaching media

Anki handles media seperately to flash cards, so Hanky does as well. 

To add audio (or other media), you create `CardMedia` objects, add a reference to the media via `.media_ref` onto your card before finally returning the `CardMedia` object from the processor. 

The `CardMedia` objects are created from raw bytes and a file extension `CardMedia(audio_bytes, ".mp3")`or from an existing file `CardMedia.from_file("my_sound_file.mp3")`.

```python
audio = CardMedia(mp3_bytes, ".mp3")
card["Speech"] = audio.media_ref
return card, [audio]
```

`media_ref` is how anki knows where the media should go, so it must be placed somewhere on the card. Hanky will make sure that the data will end up in Anki's media store.

Supported media is currently only audio: `.mp3`, `.oga`, `.opus`, `.wav`, `.weba`, `.aac`. 

## Custom file loaders

To load formats beyond CSV/JSON, register a loader against a file extension. A
loader takes an open file object and yields one `dict` per card. Once registered,
that extension works everywhere — `load`, `load-dir`, and through your pipelines.

```python
import pandas

def excel_loader(f_obj):
    df = pandas.read_excel(f_obj)
    for _, row in df.iterrows():
        yield row.to_dict()

# is_text=False because .xlsx must be opened in binary mode
hanky.register_loader(".xlsx", excel_loader, is_text=False)
```

## Loading from non-file sources

The CLI loads cards from files, but you can also build cards in your own script
and add them by calling `load_cards` directly. It takes any iterable of dicts,
one dict per card, so the source can be a list, a generator, rows from an API,
or anything else.

```python
import random

from hanky import Hanky

DICTIONARY = {
    "ephemeral": "lasting for a very short time",
    "serendipity": "the occurrence of happy events by chance",
    "petrichor": "the smell of rain falling on dry ground",
    "lucid": "expressed clearly and easy to understand",
    "gregarious": "fond of the company of others; sociable",
    # ...
}

hanky = Hanky()


def random_word_cards(n):
    for word in random.sample(list(DICTIONARY), n):
        yield {"Front": word, "Back": DICTIONARY[word]}


# add 20 cards straight from the generator, with no file involved
report = hanky.load_cards(random_word_cards(20), "basic", "english::vocab")
print(f"Added {report.added}, skipped {report.skipped}, failed {report.failed}.")
```

`load_cards` runs the same processor pipeline as the CLI and returns a
`LoadReport` with counts of the cards that were added, skipped, and failed.

## Examples

Complete, runnable scripts live in the [`demo/`](demo/) directory, ordered here
from simplest to most involved. Install their dependencies with
`pip install -r demo/requirements.txt`.

- [`demo_lowercase.py`](demo/demo_lowercase.py) — The minimal example: a single,
  dependency-free processor that lower-cases every field on a card.
- [`demo_random_words.py`](demo/demo_random_words.py) — A non-file source: builds
  cards from an in-script word list and adds them with `load_cards`.
- [`demo_define.py`](demo/demo_define.py) — A single processor that fills the
  back of each card with a dictionary definition of the word on its front,
  looked up offline via WordNet (NLTK).
- [`demo_audio.py`](demo/demo_audio.py) — Registers a custom `.xlsx` loader and uses AWS
  Polly to attach text-to-speech audio, choosing the language from a CLI
  argument (`--args lang=french`).
- [`demo_scrape.py`](demo/demo_scrape.py) — A two-stage English→French pipeline
  that scrapes a translation and example sentence from WordReference, then
  voices the translation with AWS Polly.
- [`demo_example_sentences.py`](demo/demo_example_sentences.py) — A three-stage
  English→French pipeline that scrapes a translation from WordReference, asks
  Claude for an example sentence at a given CEFR level, then adds French audio
  for both the word and the sentence with AWS Polly.

## CLI Reference

Both the `hanky` command and your own scripts share the same interface:

```
[hanky | python3 my_script.py] <operation> <model> <file|dir> [pattern] [options]
```

**`load`** — load cards from a single file:

```
hanky load [-h] [-d DECK] [--fail-fast] [--args K=V ...] model file
  model         Anki model/note-type name to create cards with.
  file          File to load from (.csv, .json, or a registered extension).
  -d, --deck    Destination deck. Defaults to the filename without extension.
  --fail-fast   Stop and raise on the first card that can't be added, instead
                of skipping it and reporting it at the end.
  --args        key=value args forwarded to your card processors (scripts only).
```

**`load-dir`** — load many files from a directory, deriving deck names from paths:

```
hanky load-dir [-h] [-r] [--fail-fast] [--args K=V ...] model dir pattern
  model            Anki model/note-type name to create cards with.
  dir              Directory to load from.
  pattern          Glob selecting files, e.g. "*.csv".
  -r, --recursive  Also descend into sub-directories.
  --fail-fast      Stop and raise on the first card that can't be added, instead
                   of skipping it and reporting it at the end.
  --args           key=value args forwarded to your card processors (scripts only).
```

For example, to load every CSV under `french/` while building deck names from
the folder structure:

```sh
hanky load-dir basic "french/" "*.csv" -r
```

```
french/                        decks created
├── animals.csv          ->    french::animals
├── bodies.csv           ->    french::bodies
└── grammar/
    └── passe_compose.csv ->   french::grammar::passe_compose
```

CSV (`.csv`) and JSON (`.json`) files work with no setup. The column/key names in
your file must match the field names of the Anki model you target.


## Development

```sh
uv sync                    # install dependencies (incl. dev + demo groups)
uv run pytest              # run tests (CI runs Python 3.11, 3.12, 3.13)
uv run ruff format .       # format
uv run ruff check .        # lint
uv run mypy src/hanky      # type check
```

## Publishing

1. Bump `__version__` in `src/hanky/__about__.py`.
2. Build the distributions:

   ```sh
   rm -rf dist && uv build
   ```

3. Publish (needs a PyPI API token in `UV_PUBLISH_TOKEN`):

   ```sh
   uv publish
   ```

4. Sanity check:

   ```sh
   uv run --with hanky --refresh-package hanky --no-project -- python -c "import hanky"
   ```
