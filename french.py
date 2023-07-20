import os
import re
from pathlib import Path
import subprocess

ANKI_DIR = os.path.expanduser("~/icloud/Documents/French/anki/")


def add_sub_deck(curr, name):
    return curr + "::" + name


for path in Path(ANKI_DIR).rglob("*.xlsx"):
    if not re.match(".*\$.*", path.name) and path.is_file:
        abs_path = path.absolute()
        path = path.relative_to(ANKI_DIR)
        anki_deck = "French"
        for parent in reversed(path.parents):
            if parent.name != "." and parent.name:
                anki_deck = add_sub_deck(anki_deck, parent.name)

        if not path.stem[:2] == "__":
            anki_deck = add_sub_deck(anki_deck, path.stem)
        print(anki_deck)

        proc = subprocess.Popen(
            [
                "python3",
                "ankigen.py",
                "--deck-name",
                anki_deck,
                "--model",
                "lang-recall",
                "--lang",
                "French",
                "-i",
                abs_path,
            ]
        )
        proc.communicate()
