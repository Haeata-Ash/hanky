import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, IO, Any, Dict, Iterator, Mapping
import psutil


Loader = Callable[[IO[Any]], Iterator[dict]]


@dataclass
class LoaderSpec:
    """How to register a default loader: the loader plus the open() options
    that format needs."""

    loader: Loader
    is_text: bool = True
    fopen_kwargs: Dict[str, Any] = field(default_factory=dict)


def json_loader(f: IO[Any]) -> Iterator[dict]:
    """Load cards from a JSON file.

    Accepts either a single object (one card) or a list of objects (many
    cards). Any other top-level shape is an error.
    """
    data = json.load(f)
    if isinstance(data, Mapping):
        yield dict(data)
    elif isinstance(data, list):
        yield from data
    else:
        raise ValueError(
            "JSON card file must contain an object or a list of objects, "
            f"not a {type(data).__name__}."
        )


def make_file_loader(
    loader: Loader, is_text: bool = True, **fopen_kwargs
) -> Callable[[str], Iterator[dict]]:
    """Wrap a loader so it opens a file path and yields card data.

    The returned generator opens the file (in text or binary mode) and runs it
    through ``loader``.

    Args:
        loader: the callable which takes an open file object and yields
            dictionaries of card data
        is_text: whether the file should be opened as text (rather than binary)
        fopen_kwargs: any other keyword args to pass to the open() call

    Returns:
        A generator function taking a file path and yielding card data.
    """

    def loader_wrapper(fpath: str) -> Iterator[dict]:
        with open(fpath, "r" if is_text else "rb", **fopen_kwargs) as f:
            yield from loader(f)

    return loader_wrapper


def has_handle(fpath: str) -> bool:
    """Check if another process has a handle for a given file.

    A process whose open files can't be read (e.g. it belongs to
    another user, or exited mid-scan) is silently skipped, since
    that's expected and usually harmless. If no processes are
    readable an error is raised as its likely that the check
    provides no safety at all.

    Raises:
        RuntimeError: *every* process turned out to be unreadable, so the
            scan checked nothing at all.
    """
    path: Path = Path(fpath).expanduser().absolute()
    checked_any = False
    for proc in psutil.process_iter():
        try:
            for item in proc.open_files():
                if str(path) == str(item.path):
                    return True
            checked_any = True
        except psutil.Error:
            pass

    if not checked_any:
        raise RuntimeError(
            "Could not inspect any running process's open files, so it "
            f"could not be determined whether another process has '{path}' "
            "open."
        )

    return False


# csv must be opened with newline="" so the csv module can handle quoted
# fields that contain embedded newlines (see the csv module docs).
DEFAULT_LOADERS: Dict[str, LoaderSpec] = {
    ".json": LoaderSpec(json_loader),
    ".csv": LoaderSpec(csv.DictReader, fopen_kwargs={"newline": ""}),
}
