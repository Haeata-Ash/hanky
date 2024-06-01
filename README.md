# hanky: A CLI Application For Generating Anki Decks

[![Hatch project](https://img.shields.io/badge/%F0%9F%A5%9A-Hatch-4051b5.svg)](https://github.com/pypa/hatch)

Hanky is an extendable command line application for adding anki flash cards from files.

While Hanky lets you load cards from files out of the box, its main feature is that it allows you to easily write your own python code which enriches or transforms your flash card data before adding them to Anki. 

For example by:
- Enriching a language vocab card by generating audio using a [text to speech service](https://en.wikipedia.org/wiki/Speech_synthesis) such as [AWS Polly](https://docs.aws.amazon.com/polly/latest/dg/what-is.html)
- Enriching a language vocab card by querying an API for a translation of the field of a card, perhaps with [Chat GPT](https://openai.com/api/) or [DeepL](https://developers.deepl.com/docs)
- Normalising the fields of a card by ensuring all text is lower case
- Generating images or html from latex snippets or other intermediate formats, for example with [SymPy](https://docs.sympy.org/latest/index.html)


This application was inspired by [genanki](https://github.com/kerrickstaley/genanki). Key differences:
- Hanky only adds new notes/cards and media, genanki can also create models and modify existing cards/models
- Hanky will add your cards for you automatically, genanki writes them to an anki package file which you have to manually upload to anki


*Hanky is not affliated or associated with the [anki application/org](https://apps.ankiweb.net/).*

## Table of Contents

- [Installation](#installation)
- [Quickstart](#quickstart)
    - [Load Cards From a File](#load-cards-from-a-file)
    - [Recursively Load Cards From A Directory](#recursively-load-cards-from-files-in-a-directory)
    - [Example Hanky Script](#example-script)
- [Configuration](#configuration)
    - [Default Configuration](#default-configuration)
- [Usage](#usage)
    - [Command Line Usage](#command-line-application-usage)
    - [Defining Your Own Hanky Script](#defining-your-own-hanky-script)


## Installation

Install via pip:

`pip install hanky`

## Quickstart

For most users, no configuration will be neccessary. If you use a non standard anki user, i.e not 'User 1', please see the [configuration section](#configuration).

Below are some quick examples of how Hanky can be used. For more details, see the [usage section](#usage)

### Load Cards From a File

- Load cards from a csv called *animals.csv*, which has two columns *Front* and *Back*, into a deck called *french::animals*
- Cards are of type or model *basic*

`hanky load basic animals.csv -d "french::animals"`

### Recursively Load Cards From Files in a Directory

- Load cards from any csv files inside directory *french*. The csv files have columns *Front* and *Back*
- Cards are of type or model *basic*

`hanky load-dir "basic" "french/" "*.csv" -r`

For example, given the following folder structure:
```
french
├── animals.csv
├── bodies.csv
├── clothing.csv
└── grammar
    └── passe_compose.csv
```

The following decks will be created:
- `french`: top level deck
- `french::animals`: nested deck
- `french::bodies`: nested deck
- `french::clothing`: nested deck
- `french::grammar`: nested container deck 
- `french::grammar::passe_compose`: doubly nested deck

### Example Script

Create your hanky script. For more details, see the [Hanky Script Walkthrough](#defining-your-own-hanky-script)

```python
from hanky import Hanky
import boto3

def french_tts(text):
    """Generate french speech audio from text using aws polly"""
    client = boto3.client("polly")
    res = client.synthesize_speech(
        Engine="neural", OutputFormat="mp3", Text=utf_8_str, VoiceId="Lea"
    )

    return res["AudioStream"].read()

hanky = Hanky()

@hanky.card_processor(
    "french-vocab-model", expected_args=[], card_fields=["native-lang", "target-lang"]
)
def lang_model(card: dict):
    """Add french speech to cards of type/model 'french-vocab-model'. We assume that 
    the model/note type has already been created in anki with the following fields
        - native-lang
        - target-lang
        - target-lang-speech
    """

    # generate the speech 
    speech = french_tts(card["target-lang"])

    # add the mp3 data to anki
    speech_ref = hanky.add_media(speech, file_ext=".mp3")

    # put the reference to that media inside a field in the lang-vocab model
    # in this case there is a specific field, 'target-lang-speech'
    card["target-lang-speech"] = speech_ref
    return card

hanky.run()
```

Use your script to load french vocab from 'animals.csv' into a deck 'animals'

`python3 my_script.py load french-vocab-model animals.csv`

<!-- > **:information_source: Note:**
> This project is currently in alpha and is not stable. -->


## Configuration

See below an overview of hanky's configuration options or jump to the [default configuration](#default-configuration) section. 

### Configuration Locations

- `~/.config/hanky/hanki.toml`: Default location which Hanky automatically checks for a configuration file. 
- Alternatively, provide a path to another config file with the `--config` option

### Configuration Options
- `anki_database`: tells hanky where to find the anki collection (an sqlite database where anki stores flash cards and other data). Defaults to the following locations:
    - Mac OS: `~/Library/Application Support/Anki2/User 1/collection.anki2`
    - Linux: `~/.local/share/Anki2/User 1/collection.anki2`

- `database_safety_check`: a boolean which when set to `true` will check for any running processes using the anki collection. Defaults to `true`.
    > **:warning: Caution:** 
    > Setting this option to false may result in database corruption. Always ensure your anki is backed up.

- `allow_duplicates`: a boolean which when set to `true` allows duplicate cards to be added. A duplicate card is a card whose field values match another cards field values already in anki. Defaults to `false`.

### Default configuration:

```toml
# specifies where to find the anki collection (sqlite db where anki stores data)
# If you are not using the default anki user, 'User 1', this option must be specified
# DEFAULTS:
# Mac OS: ~/Library/Application Support/Anki2/User 1/collection.anki2
# Linux: ~/.local/share/Anki2/User 1/collection.anki2
anki_database = "~/.local/share/Anki2/User 1/collection.anki2"

# whether or not to check for other processes using the anki database
# DEFAULTS: true
database_safety_check = true

# whether or not to allow duplicate cards to be added
# DEFAULTS: false
allow_duplicates = false
```

## Usage 

Hanky can be used out of the box as a command line application, as well as extended with your own custom script.
<!-- 
## Basic Concepts

### Model

A model in this context refers to an *anki model* or *anki note type*. An *anki model* is essentially the data model for our cards, and defines the **fields** which all cards using that model will have. For example, a model which anki has out of the box is the *basic* model. The *basic* model has two fields, *Front*, and *Back*. When the user creates a new card of type *basic*, they set the values of *Front* and *Back* which are then placed in a template and displayed to the user.

Hanky allows you to write your own code to process cards which belong to a particular model. For example,  -->
### Command Line Application Usage

Both the out of the box hanky command line application and any of your custom scripts will have the same interface.


`[hanky script] [operation] [model] [file|directory]`

- `[hanky script]`: Either the `hanky` executable OR your own script, `python3 my_script.py`
- `[operation]`: The operation to perform, one of `load` which reads cards in from a file and `load-dir` which reads cards from potentially many files inside a directory
- `[model]`: The name of the **anki model**, also known as card type which the cards being read in belong to. Anki comes pre installed with several models, such as the *basic* model which comes with two **fields**, *Front* and *Back*. Each model or card type has potentially several *card templates*, which reference the anki fields and tell anki what to display. You can create your own custom models/note types through the UI.
- `[file|directory]`: The file or the directory to read the cards from

### Loading Cards from a File

```
$ hanky load -h                                                                                                                                             
usage: hanky load [-h] [-d DECK] model file

positional arguments:
  model                 Name of the anki model to create cards with.
  file                  Path of the file to load from

options:
  -h, --help            show this help message and exit
  -d DECK, --deck DECK  Name of the deck to load cards into. If not specified, defaults to the filename without the extension.
```
#### Load cards of model *lang-vocab* from a csv file called *countries.csv*, using the filemame without the extension as the deckname. Creates or updates a deck called *countries*.
- `hanky load "basic" ~/my-folder/countries.csv`

#### Load cards of model *lang-vocab* from a json file called *countries.json*, specifying a deckname of *african-countries*. Creates or updates a deck called *african-countries*.
- `hanky load "basic" ~/my-folder/countries.json -d african-countries`

### Loading Cards From Files in a Directory
```
usage: hanky load-dir [-h] [-r] model dir pattern

positional arguments:
  model            Name of the anki model to create cards with.
  dir              Path of the file to load from
  pattern          Glob pattern used to decide which files to load. For example, '*.csv'

options:
  -h, --help       show this help message and exit
  -r, --recursive  If loading files from a directory, recursively load from files in sub directories as well.
```

#### Load all csv files in a folder as decks of cards using the *basic* anki model/note type. The relative path of the files from the specified folder will be used as the deck name. 
- `hanky load-dir "basic" "~/french/" "*.csv"`

Given the following file structure:
```
french
├── animals.csv
├── bodies.csv
├── clothing.csv
└── grammar
    └── passe_compose.csv
```

The following decks will be created:
- **french**
- **french::animals**
- **french::bodies**
- **french::clothing**

#### Recursively load all json files as decks of cards using the *lang-vocab* anki model/note type. The relative path of the files from the specified folder will be used as the deck name. 

`hanky load-dir "lang-vocab" "~/french/" "*.json" -r`

For example, given the following folder structure:
```
french
├── animals.csv
├── bodies.csv
├── clothing.csv
└── grammar
    └── passe_compose.csv
```

The following decks will be created:
- **french**
- **french::animals**
- **french::bodies**
- **french::clothing**
- **french::grammar**
- **french::grammar::passe_compose**

The created anki decks will have the following structure:
```
french
├── animals
├── bodies
├── clothing
└── grammar
    └── passe_compose
```

### Defining Your Own Hanky Script

