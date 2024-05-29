# hanky

[![Hatch project](https://img.shields.io/badge/%F0%9F%A5%9A-Hatch-4051b5.svg)](https://github.com/pypa/hatch)

Library and command line application for loading flash cards into anki.

> **:information_source: Note:**
> This project is currently in alpha and is not stable.

## Installation

Install via pip:

`pip install hanky`

Optionally install text to speech code seen in tutorial:

` pip install hanky[toc]`

## Configuration

Currently two configuration options are exposed:

- `anki_database`: tells hanky where to find the anki collection (an sqlite database where anki stores flash cards and other data). The normal locations at the time of writing are as follows:
    - MAC OS
        - `~/Library/Application Support/Anki2/User 1/collection.anki2`
    - Linux
        - `~/.local/share/Anki2/User 1/collection.anki2`

- `database_safety_check`: a boolean which when set to `true` will check for any running processes using the anki collection.
    > **:warning: Caution:** 
    > Setting this option to false may result in database corruption. Always ensure your anki is backed up.

- `allow_duplicates`: a boolean which when set to `true` allows duplicate cards (all field values match another cards field values) to be added.
s
Example configuration:

```toml
# where to find the anki collection (sqlite db where anki stores data)
# Usual system lo
anki_database = "~/.local/share/Anki2/User 1/collection.anki2"

# whether or not to check for other processes using the anki database
database_safety_check = true

# whether or not to allow duplicate cards to be added
allow_duplicates = false
```

## Usage 

Hanky can be used as both a command line application and a library. 

- If you want to do something more complex than simply adding cards directly from files, such as generating speech, querying an api or performing other operations at runtime, see the [Library Tutorial](#library-tutorial)

- If you just want to load flash cards from files, jump to the [command line usage](#command-line-usage)

## Library Tutorial


## Command Line Usage

Hanky can be used out of the box as a command line application. If running your own hanky script, omit the `-m` seen in the below examples.

### Recursively load decks from files in a folder

Recursively load all csv files as decks of cards using the 'basic' anki model/note type. The relative path from the specified folder will be used as the deck name.

`python3 -m hanky load "basic" "~/french/" "*.csv" -r`

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
- `french::animals`: nested animal vocab deck
- `french::bodies`: nested bodies vocab deck
- `french::clothing`: nested clothing vocab deck
- `french::grammar`: nested container deck for grammar
- `french::grammar::passe_compose`: doubly nested deck for passe compose rules

The created anki decks will have the following structure:
```
french
├── animals
├── bodies
├── clothing
└── grammar
    └── passe_compose
```

### Load decks from files from a folder

Load all csv files in a folder as decks of cards using the 'basic' anki model/note type. The relative path from the specified folder will be used as the deck name.

`python3 -m hanky load "basic" "~/french/" "*.csv"`

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
- `french::animals`: nested animal vocab deck
- `french::bodies`: nested bodies vocab deck
- `french::clothing`: nested clothing vocab deck

The created anki decks will have the following structure:
```
french
├── animals
├── bodies
├── clothing
```

### Load a deck from a file

Load a single deck using the 'basic' anki model/note type from a file

`python3 -m hanky load-deck "basic" ~/my-folder/countries.csv`

The following deck will be created:
- `countries`
