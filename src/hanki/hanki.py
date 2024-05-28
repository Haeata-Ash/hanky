import platform
import subprocess
from collections import UserDict
from pathlib import Path
from typing import Callable, Generator, Iterator, List, Union

from anki.collection import AddNoteRequest, Collection
from anki.collection import Note as AnkiCard
from Crypto.Hash import SHA256
from tomllib import load as toml_load

from hanki.cli import make_parser
from hanki.config import Config
from hanki.utils import DEFAULT_LOADERS, read_file


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


_DEFAULT_CONFIG = {
    "ANKI_DATABASE": _get_default_anki_db_path(),
    "DATABASE_SAFETY_CHECK": True,
}


class Media:
    def __init__(self, filename, escaped_url):
        self.unsecaped = filename
        self.escaped = escaped_url

    def url(self):
        return self.escaped

    def __str__(self):
        return self.unsecaped


class AudioMedia(Media):
    def url(self):
        return f"[sound:{self.escaped}]"


class Card(UserDict):
    def __init__(self, card, model_name, field_names, **kwargs):
        self._anki_card = card
        self._model_name = model_name
        self._field_names = set(field_names)

        super().__init__(**kwargs)

    def __setitem__(self, key, value):
        if not key or not isinstance(key, str):
            raise TypeError("Field name must be a non empty string.")

        if key not in self.fields:
            raise KeyError(
                f"Field '{key}' does not exist in model {self._model_name}"
            )

        self._anki_card[key] = value
        super().__setitem__(key, value)
    
    @property
    def fields(self):
        return self._field_names


class CardTransformer:
    def __init__(self, model_name: str, func, expected_args, expected_fields):
        self.f = func
        self.model = model_name
        self.expected_args = expected_args
        self.expected_fields = expected_fields

    def __call__(self, card: Card, **kwargs):
        for k in self.expected_fields:
            if k not in card:
                raise KeyError(
                    f"Expected field '{k}' not present in card. \n {str(card)}"
                )

        for k in self.expected_args:
            if k not in kwargs:
                raise KeyError(
                    f"Handler for {self.model} expects key word argument '{k}'. Ensure it is passed in via the --model-args option"
                )

        return self.f(card, **kwargs)


# class ProxyEvent:
#     METHOD_CALL = "METHOD_CALL"
#     ATTR_ACCESS = "ACCESS"

#     def __init__(self, op, v_type, name, *args, **kwargs):
#         self.op = op
#         self.v_type = v_type
#         self.name = name
#         self.args = args
#         self.kwargs = kwargs


# class Proxy:
#     def __init__(self, instance):
#         self._inst = instance
#         self.events = []

#     def __getattr__(self, attr):
#         v = getattr(self.proxied, attr)
#         self.events.append(ProxyEvent(ProxyEvent.ATTR_ACCESS, type(v), attr))
#         return v

#     def record_method_patch(self, method) -> Callable:
#         def record_wrapper(func, *args, **kwargs):
#             self.events.append(
#                 ProxyEvent(ProxyEvent.METHOD_CALL, str(func), args, kwargs)
#             )
#             return func(*args, **kwargs)

#         return record_wrapper

#     def dry_run_patch(self, func):
#         def stub_wrapper(func, *args, **kwargs):
#             return None

#         return self.recorder_monkey_patch(stub_wrapper)


class Hanki:
    def __init__(self, config: Config = None):
        # set default config and then overwrite with config object provided via constructor
        # ensures default keys are present
        self.config: Config = Config(**_DEFAULT_CONFIG)
        if config:
            self.config.update(config)

        self._col: Collection = None

        self.transformers = dict()
        self.loaders = dict(DEFAULT_LOADERS)

    def run(self):
        parser = make_parser()
        args = parser.parse_args()

        if args.config:
            self.config.from_file(args.config, toml_load)

        if args.operation == "load-deck":
            self.load_deck(
                args.file,
                args.model,
                deck_name=args.deck,
                **(args.args) if args.args else {},
            )

        elif parser.operation == "load":
            self.load_dir(
                args.model,
                args.dir,
                args.pattern,
                recursive=args.is_rec,
                *(args.args) if args.args else {},
            )

    @property
    def col(self):
        if not self._col:
            db_path = Path(self.config["ANKI_DATABASE"]).expanduser().absolute()
            if not db_path:
                raise RuntimeError(
                    """Path to anki sqlite collection database was 
                    not provided in config and no suitable default known."""
                )

            if self.config["DATABASE_SAFETY_CHECK"]:
                res = subprocess.run(["fuser", db_path])
                if res.returncode == 0:
                    raise RuntimeError(
                        """At least one other process is using the anki database. Ensure the Anki application is closed before using Hanki to avoid possible corruption."""
                    )
            self._col = Collection(db_path)
        return self._col

    def register_loader(
        self, file_ext: str, loader: Callable[[str], Union[Iterator, Generator]]
    ):
        self.loaders[file_ext] = loader

    def register_card_transformer(
        self,
        model_name: str,
        handler: Callable[[dict], dict],
        expected_args: List[str] = [],
        expected_fields: List[str] = [],
    ):
        if model_name not in self.transformers:
            self.transformers[model_name] = []
        self.transformers[model_name].append(
            CardTransformer(model_name, handler, expected_args, expected_fields)
        )

    def transformer(
        self, model: str, expected_args: List[str], expected_fields: List[str]
    ):
        def decorator(func):
            self.register_card_transformer(model, func, expected_args, expected_fields)
            return func

        return decorator

    def get_card_transformers(self, model_name: str) -> List[CardTransformer]:
        if model_name in self.transformers:
            return self.transformers[model_name]

        return []

    def get_loader(self, suffix):
        return self.loaders[suffix]

    def load_deck(
        self,
        path: str,
        model_name: str,
        deck_name: str = None,
        loader=None,
        parent_deck="",
        **model_args,
    ):
        path = Path(path).absolute()

        transformers = self.get_card_transformers(model_name)
        loader = loader if loader else self.get_loader(path.suffix)

        model = self.col.models.by_name(model_name)
        if not model:
            raise KeyError(f"Model '{model_name}' does not exist in your anki collection. Ensure it has been added before using it with hanki.")
        
        # deck is the specified name or filename without extension
        deck_name = deck_name if deck_name else path.stem
        deck_id = self.col.decks.id(deck_name)

        cards_to_add: List[AddNoteRequest] = []
        for item in read_file(path, loader):
            card = Card(self.col.new_note(model), model_name, self.col.models.field_names(model), **item)
            for t in transformers:
                card = t(card, **model_args)

            cards_to_add.append(card._anki_card)

        for c in cards_to_add:

            self.col.add_note(c, deck_id)


    def add_media(self, data, anki_media_filename: str = None, file_ext: str = None):
        ext = None
        if anki_media_filename:
            path = Path(anki_media_filename)
            ext = path.suffix
        elif file_ext:
            ext = file_ext
        else:
            raise ValueError(
                "If argument 'anki_media_filename' is not provided then 'file_ext' must be present"
            )

        if isinstance(data, str):
            data = data.encode()
        actual = self.col.media.write_data(
            anki_media_filename
            if anki_media_filename
            else (SHA256.new(data).hexdigest() + ext),
            data,
        )

        return Media(actual, self.col.media.escape_media_filenames(actual))

    def add_media_file(self, local_path):
        actual = self.col.media.add_file(local_path)

        return Media(actual, self.col.media.escape_media_filenames(actual))

    def load_dir(
        self,
        model: str,
        root_dir: str,
        glob_pattern: str,
        recursive=False,
        parent_deck: str = "",
        loader=None,
        **model_args,
    ):
        parent_deck = ""

        root = Path(root_dir).expanduser()

        root_deck = parent_deck if parent_deck else root.name

        def _glob(root, pattern, recursive):
            if recursive:
                for path in root.rglob(pattern):
                    yield path
            else:
                for path in root.glob(pattern):
                    yield path

        for path in _glob(root, glob_pattern, recursive):
            if path.is_file():
                path = path.relative_to(root)
                parents = [p.name for p in reversed(path.parents)]

                # don't need the first empty entry for the current directory
                parents.pop(0)
                deck_list = [root_deck]

                i = 0
                while i < len(parents):
                    deck_list.append(parents[i])
                    i += 1
                deck_list.append(path.stem)
                full_deck = "::".join(deck_list)

                self.load_deck(
                    path.absolute(),
                    model=model,
                    deck_name=full_deck,
                    loader=loader,
                    **model_args,
                )
