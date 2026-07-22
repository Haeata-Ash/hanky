from dataclasses import dataclass
import dataclasses
from pathlib import Path
import platform
import tomllib

from hanky.errors import ConfigError


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
        raise ConfigError(
            """Only linux and MacOS systems have a default anki database/collection path.
            Please specify path to anki db."""
        )


def _get_default_backup_folder():
    return Path("~/.local/share/hanky/backups").expanduser().as_posix()


@dataclass
class Config:
    """Configuration object"""

    ANKI_DB_PATH: str = ""
    DO_SAFETY_CHECK: bool = True
    ALLOW_DUPLICATES: bool = False
    BACKUP_FOLDER: str = ""

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

        Raises:
            ConfigError: the file is not valid TOML, or contains a key that
                is not a recognised configuration option.
        """

        with open(fpath, "rb") as f:
            try:
                data = tomllib.load(f)
            except tomllib.TOMLDecodeError as e:
                raise ConfigError(f"Could not parse config file '{fpath}': {e}") from e

        try:
            return Config(**data)
        except TypeError as e:
            raise ConfigError(f"Invalid config file '{fpath}': {e}") from e

    def update(self, **kwargs) -> "Config":
        return dataclasses.replace(self, **kwargs)

    def __post_init__(self):
        if self.ANKI_DB_PATH == "":
            self.ANKI_DB_PATH = _get_default_anki_db_path(_get_system())
        if self.BACKUP_FOLDER == "":
            self.BACKUP_FOLDER = _get_default_backup_folder()
