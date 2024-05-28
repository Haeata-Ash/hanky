# hanki

[![Hatch project](https://img.shields.io/badge/%F0%9F%A5%9A-Hatch-4051b5.svg)](https://github.com/pypa/hatch)

Library and command line application for loading flash cards into anki.

> **Note**
> This project is currently in alpha and is not stable.

## Installation

Install via pip:

`pip install hanki`

Optionally install text to speech code seen in tutorial:

` pip install hanki[toc]`

## Configuration

Currently two configuration options are exposed:

- `ANKI_DATABASE`: tells hanki where to find the anki collection (an sqlite where anki stores flash cards and other data). The normal system locations at the time of writing are as follows:
    - MAC OS
        - `~/Library/Application Support/Anki2/User 1/collection.anki2`
    - Linux
        - `~/.local/share/Anki2/User 1/collection.anki2`

- `DATABASE_SAFETY_CHECK`: a boolean which when set to `true` will check for any running processes using the anki collection.
    - > **Warning**  Setting this option to false will disable checks for other processes using the anki collection database, which may result in database corruption. Always ensure your anki is backed up.

Example configuration:

```toml
# where to find the anki collection (sqlite db where anki stores data)
# Usual system lo
ANKI_DATABASE = "~/.local/share/Anki2/User 1/collection.anki2"

# whether or not to check for other processes using the anki database
DATABASE_SAFETY_CHECK = true
```


