from dataclasses import dataclass
import dataclasses
import platform
from pathlib import Path
import tomllib


def _get_system():
    return platform.system()


def _get_default_anki_db_path(system: str) -> str:
    """Choose a default path for the anki sqlite collection database based on
    the OS.

    Params:
        system: The operating system as given by stdlib platform.system()
    Defaults:
        Linux: "~/.local/share/Anki2/User 1/collection.anki2"

        MacOS: "~/Library/Application Support/Anki2/User 1/collection.anki2"
    """
    if system == "Linux":
        return "~/.local/share/Anki2/User 1/collection.anki2"
    elif system == "Darwin":
        return "~/Library/Application Support/Anki2/User 1/collection.anki2"
    else:
        raise ValueError(
            """Only linux and MacOS systems have a default anki database/collection path. 
            Please specify path to anki db."""
        )


DEFAULT_CONFIG_PATH = Path("~/.config/hanky/hanky.toml").expanduser()


@dataclass
class Config:
    """Configuration object"""

    ANKI_DB_PATH: str = ""
    DO_SAFETY_CHECK: bool = True
    ALLOW_DUPLICATES: bool = False

    @classmethod
    def from_toml(
        cls,
        fpath: str,
    ) -> "Config":
        """Load configuration data from a file

        Args:
            fpath: path to a file

        Returns:
            Config object
        """

        with open(fpath, "rb") as f:
            return Config(**tomllib.load(f))

    def update(self, **kwargs) -> "Config":
        return dataclasses.replace(self, **kwargs)

    def __post_init__(self):
        if self.ANKI_DB_PATH == "":
            print("here lolol")
            print(_get_system())
            self.ANKI_DB_PATH = _get_default_anki_db_path(_get_system())
