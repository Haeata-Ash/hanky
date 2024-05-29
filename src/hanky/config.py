import platform
from pathlib import Path
from typing import Callable, Union

def _get_default_anki_db_path() -> str:
    """Choose a default path for the anki sqlite collection database based on
    the OS.

    Defaults:
        Linux: "~/.local/share/Anki2/User 1/collection.anki2"
        MacOS: "~/Library/Application Support/Anki2/User 1/collection.anki2"
    """
    if platform.system() == "Linux":
        return "~/.local/share/Anki2/User 1/collection.anki2"
    elif platform.system() == "Darwin":
        return "~/Library/Application Support/Anki2/User 1/collection.anki2"
    else:
        return ""


ANKI_DB_PATH = "anki_database"
DO_SAFET_CHECK = "database_safety_check"
ALLOW_DUPLICATES = "allow_duplicates"

DEFAULT_CONFIG = {
    ANKI_DB_PATH: _get_default_anki_db_path(),
    DO_SAFET_CHECK: True,
    ALLOW_DUPLICATES: False
}

class Config(dict):
    """Configuration object"""


    def __init__(self, **kwargs):
        self._config = None
        self.default_path = Path("~/.config/hanky/hanky.toml").expanduser()
        super().__init__(kwargs)

    def from_file(
        self,
        file: Union[Path, str],
        loader: Callable[[Union[str, Path], dict], dict],
        text=False,
        **kwargs,
    ):
        with open(file, "r" if text else "rb") as f:
            cfg = loader(f, **kwargs)
            if not isinstance(cfg, dict):
                raise TypeError(
                    f"Received type '{type(cfg)}' but expected '{type(dict)}' from loader function."
                )

            for k, v in cfg.items():
                self[k] = v

