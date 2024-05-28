from pathlib import Path
from typing import Callable, Union

# class ConfigurationError(Exception):
#     pass


# class MissingMandatoryConfigKey(ConfigurationError):
#     def __init__(self, key, extra=""):
#         self.key = key
#         super().__init__(f"'{key}' must be defined. {extra}")


# class Config(dict):
#     """Configuration object"""

#     DEFAULT_PATH = "~/.config/hanki/hanki.json"

#     def __init__(self):
#         self._config = None
#         self.default_path = Path(Config.DEFAULT_PATH).expanduser()

#     @property
#     def config(self):
#         # configuration not loaded, try load from default path
#         if not self._config:
#             try:
#                 self.from_json_file(Config.DEFAULT_PATH)
#             except IOError:
#                 raise IOError(
#                     f"""Attempt to read default configuration file at '{Config.DEFAULT_PATH}' failed.
#                     Either load configuration explicitly or ensure configuration file is present at default location."""
#                 )
#         return self._config


#     @property
#     def anki_database(self) -> Path:
#         """Absolute Path to anki sqlite database (the collection). Tilda/home expansion allowed.

#         Defaults:
#             Linux: "~/.local/share/Anki2/User 1/collection.anki2"
#         """

#         key = "anki_database"
#         if key in self.config:
#             return Path(self.config["anki_database"]).expanduser()
#         else:
#             if sys.platform.startswith("linux"):
#                 return Path("~/.local/share/Anki2/User 1/collection.anki2").expanduser()

#         raise MissingMandatoryConfigKey(
#             key,
#             "No suitable default known for this platform and no location provided in configuration.",
#         )

#     @property
#     def database_safety_check(self) -> bool:
#         """Whether or not to check for other processes using the anki sqlitedb.
#         When 'True', program will terminate if any other processes are using the file.
#         Set to 'False' for no safety check.

#         Defaults:
#             'True'
#         """
#         if "database_safety_check" in self.config:
#             return False if self.config["database_safety_check"] == "False" else True

#     def from_json_file(self, file_path: str) -> None:
#         """Load configuration from json file. If no file_path is provided,
#         attempt to read from file in default location"""
#         if file_path:
#             path = Path(file_path).expanduser()

#         with open(path, mode="r") as f:
#             self.config = json.load(f)

#     def load(self, loader: Callable[[Any], dict], **loader_params: Any) -> None:
#         """Load the configuration using a custom loader function and params. The
#         loader function must return a dictionary"""
#         self._config = loader(loader_params)
#         if not isinstance(self.config, dict):
#             # Not a configuration error as this is a only a problem with the
#             # loader function.
#             raise ValueError("loader must return a dictionary.")


# # share same config throughout application
# # must ensure to load the configuration before accessing

# _DEFAULT_CONFIG = Config()


class Config(dict):
    """Configuration object"""

    def __init__(self, **kwargs):
        self._config = None
        self.default_path = Path("~/.config/hanki/hanki.toml").expanduser()
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
