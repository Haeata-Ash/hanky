from typing import Generator, Iterator, Union, TextIO, Callable
from pathlib import Path
import json
import csv


def read_file(
    path: str, loader: Callable[[TextIO], Union[Iterator, Generator]]
) -> Union[Iterator, Generator]:
    path = Path(path)
    if not path.is_file():
        raise IOError(f"{path} is not a file.")
    with open(path, "r") as f:
        for item in loader(f):
            yield item


DEFAULT_LOADERS = {".json": json.load, ".csv": csv.DictReader}
