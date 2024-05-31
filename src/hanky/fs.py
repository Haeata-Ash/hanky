import csv
import json
from pathlib import Path
from typing import Callable, IO, Any, Iterator
import psutil


Loader = Callable[[IO[Any]], Iterator[dict]]


def has_handle(fpath: str) -> bool:
    """Check if another process has a handle for a given file"""
    path: Path = Path(fpath).expanduser().absolute()
    for proc in psutil.process_iter():
        try:
            for item in proc.open_files():
                if str(path) == str(item.path):
                    return True
        except psutil.Error:
            pass

    return False


DEFAULT_LOADERS = {".json": json.load, ".csv": csv.DictReader}
