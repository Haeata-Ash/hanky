# hanky

[![Hatch project](https://img.shields.io/badge/%F0%9F%A5%9A-Hatch-4051b5.svg)](https://github.com/pypa/hatch)

Hanky is a simple application framework and command line application for loading flash cards into anki. 

Hanky allows you to easily write your own python code which enriches or transforms your flash card data before adding them to Anki, for example by generating text to speech audio or quering an api for extra data at runtime.

> **:information_source: Note:**
> This project is currently in alpha and is not stable.

## Table of Contents

- [Installation](#installation)
- [Configuration](#configuration)
    - [Default Configuration](#default-configuration)
- [Application Usage](#usage)
    - [Load Deck From A File](#load-a-deck-from-a-file)
    - [Load Decks From A Folder](#load-decks-from-files-from-a-folder)
    - [Recursively Load Decks From A Folder](#recursively-load-decks-from-files-in-a-folder)
- [Example Hanky Scripts](#examples)


## Installation

Install via pip:

`pip install hanky`

## Configuration

See below an overview of hanky's configuration options or jump to the [default configuration](#default-configuration) section. 

Hanky automatically looks for a configuration file in `~/.config/hanky/hanki.toml`. Alternatively, provide a path to a config file with the `--config` option. If no configuration file is provided, hanky will attempt to use the [default configuration](#default-configuration).

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

Hanky can be used as both a command line application and a library. 

- If you want to do something more complex than simply adding cards directly from files, such as generating audio using text to speech, querying an api or performing other operations at runtime, see the [examples](#examples)

- If you just want to load flash cards from files, see the examples below

Hanky can be used out of the box as a command line application. If running your own hanky script, omit the `-m` seen in the below examples and replace `hanky` with your python file.

**Overview**

```
usage: hanky [-h] [--config CONFIG] {load,load-dir} ...

Simple program to allow programatic management of anki cards

positional arguments:
  {load,load-dir}  Type of operation to perform
    load           Load cards into an anki deck from a file
    load-dir       Load cards into anki deck(s) from files in a directory, using the filenames as deck names.

options:
  -h, --help       show this help message and exit
  --config CONFIG  Path to hanky toml configuration file
```

### Load a deck from a file

Load a single deck using the 'basic' anki model/note type from a file

`python3 -m hanky load "basic" ~/my-folder/countries.csv`

The following deck will be created:
- `countries`

### Load decks from files from a folder

Load all csv files in a folder as decks of cards using the 'basic' anki model/note type. The relative path from the specified folder will be used as the deck name.

`python3 -m hanky load-dir "basic" "~/french/" "*.csv"`

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

### Recursively load decks from files in a folder

Recursively load all csv files as decks of cards using the 'basic' anki model/note type. The relative path from the specified folder will be used as the deck name.

`python3 -m hanky load-dir "basic" "~/french/" "*.csv" -r`

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

## Examples

