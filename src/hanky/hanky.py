import functools
import hashlib
from pathlib import Path
from typing import Callable, Generator, Iterator, List, Union

from anki.collection import Collection, SearchNode
from tomllib import load as toml_load

from hanky.cli import make_parser
from hanky.config import (
    ALLOW_DUPLICATES,
    ANKI_DB_PATH,
    DEFAULT_CONFIG,
    DO_SAFET_CHECK,
    Config,
)
from hanky.fs import DEFAULT_LOADERS, has_handle, read_file
from hanky.media import is_audio_ext, make_anki_sound_ref


class ModelProcessor:
    def __init__(self, model_name: str, func, expected_args, required_fields):
        self.f = func
        self.model = model_name
        self.expected_args = expected_args
        self.required_fields = required_fields

        if not isinstance(self.expected_args, list):
            raise TypeError("'expected_args' must be a list of strings")
        if not isinstance(self.required_fields, list):
            raise TypeError("'required_fields' must be a list of strings")

    def __call__(self, card: dict, **kwargs) -> dict:
        for k in self.required_fields:
            if k not in card:
                raise KeyError(
                    f"Processor requires '{k}' to be present in card. \n {str(card)}"
                )

        for k in self.expected_args:
            if k not in kwargs:
                raise KeyError(
                    f"Processor for {self.model} expects key word argument '{k}'. Ensure it is passed in via the --model-args option"
                )

        ret = self.f(card, **kwargs)
        if not isinstance(ret, dict):
            raise TypeError(
                f"Processor function did not return a dictionary like object, returned type {type(ret)}"
            )

        return ret


class Hanky:
    def __init__(self, **kwargs):
        # set default config and then overwrite with config object provided via constructor
        # ensures default keys are present
        self.config: Config = Config(**DEFAULT_CONFIG)
        if kwargs:
            self.config.update(kwargs)

        self._col: Collection = None

        self.processors = dict()
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

        elif args.operation == "load":
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
            if not self.config[ANKI_DB_PATH]:
                raise RuntimeError(
                    """Path to anki sqlite collection database was 
                    not provided in config and no suitable default known."""
                )
            db_path = Path(self.config[ANKI_DB_PATH]).expanduser().absolute()

            if not db_path.exists() or not db_path.is_file():
                raise FileNotFoundError(
                    f"'{db_path}' either does not exist or is not a file. Please check the provided path to the anki collection."
                )

            if self.config[DO_SAFET_CHECK]:
                if has_handle(self.config[ANKI_DB_PATH]):
                    raise RuntimeError(
                        """At least one other process is using the anki database. Ensure the Anki application is closed before using Hanky to avoid possible corruption."""
                    )

            self._col = Collection(db_path)
        return self._col

    def add_card(
        self,
        deck_name,
        model_name,
        filter_query: str = None,
        allow_duplicates=False,
        **fields,
    ) -> bool:
        model = self.col.models.by_name(model_name)
        if not model:
            raise ValueError(
                f"Model '{model_name}' does not exist in your anki collection. Ensure it has been added before using it with hanky."
            )
        deck_id = self.col.decks.id(deck_name, create=False)
        if not deck_id:
            ValueError(
                f"Deck '{deck_name}' does not exist in your anki collection. Ensure it has been created before using it with hanky."
            )
        expected_fields = self.col.models.field_names(model)
        for k in expected_fields:
            if k not in fields:
                raise KeyError(f"Expected field '{k}' is missing.")

        new_card = self.col.new_note(model)

        for k, v in fields.items():
            new_card[k] = str(v)

        if filter_query:
            matches = self.col.find_cards(filter_query)
            if len(matches):
                return False

        allow_duplicates = allow_duplicates if allow_duplicates else self.config[ALLOW_DUPLICATES]

        if not allow_duplicates:
            rets = [True]

            for field in fields:
                if self.col.find_notes(
                    self.col.build_search_string(
                        new_card[field], SearchNode(field_name=field)
                    )
                ):
                    rets.append(True)
                else:
                    rets.append(False)

            is_dupe = functools.reduce(lambda x, y: x and y, rets)

            if is_dupe:
                return False

        self.col.add_note(new_card, deck_id)

        return True

    def add_deck(self, deck_name) -> bool:
        self.col.decks.id(deck_name)
        return True

    def register_loader(
        self, file_ext: str, loader: Callable[[str], Union[Iterator, Generator]]
    ):
        self.loaders[file_ext] = loader

    def register_card_processor(
        self,
        model_name: str,
        handler: Callable[[dict], dict],
        expected_args: List[str] = [],
        expected_fields: List[str] = [],
    ):
        if model_name not in self.processors:
            self.processors[model_name] = []
        self.processors[model_name].append(
            ModelProcessor(model_name, handler, expected_args, expected_fields)
        )

    def card_processor(
        self, model: str, expected_args: List[str], expected_fields: List[str]
    ):
        def decorator(func):
            self.register_card_processor(model, func, expected_args, expected_fields)
            return func

        return decorator

    def get_model_processors(self, model_name: str) -> List[ModelProcessor]:
        if model_name in self.processors:
            return self.processors[model_name]

        return []

    def get_loader(self, suffix) -> Callable:
        return self.loaders[suffix]

    def load_deck(
        self,
        fpath: str,
        model_name: str,
        deck_name: str = None,
        loader=None,
        parent_deck="",
        **model_args,
    ):
        print(f"Loading into deck {deck_name}")
        fpath = Path(fpath).absolute()

        transformers = self.get_model_processors(model_name)
        loader = loader if loader else self.get_loader(fpath.suffix)

        model = self.col.models.by_name(model_name)
        if not model:
            raise KeyError(
                f"Model '{model_name}' does not exist in your anki collection. Ensure it has been added before using it with hanky."
            )

        # deck is the specified name or filename without extension
        deck_name = deck_name if deck_name else fpath.stem

        self.add_deck(deck_name)

        count = 0
        total = 0
        for item in read_file(fpath, loader):
            card = dict(item)
            for t in transformers:
                card = t(card, **model_args)

            ret = self.add_card(
                deck_name,
                model_name,
                **card,
            )
            total += 1
            if ret:
                count += 1
        
        print(f"Added {count} out of {total} cards.")

    def add_media(
        self, data, anki_media_filename: str = None, file_ext: str = None
    ) -> str:
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

        desired_name = anki_media_filename

        # no filename given, use hash of the data plus file_ext
        if not desired_name:
            m = hashlib.sha256()
            m.update(data)
            desired_name = m.hexdigest() + ext

        # write media to anki database
        actual_name = self.col.media.write_data(
            desired_name,
            data,
        )

        anki_ref = self.col.media.escape_media_filenames(actual_name)

        if is_audio_ext(actual_name):
            anki_ref = make_anki_sound_ref(anki_ref)

        return anki_ref

    def add_media_file(self, local_path) -> str:
        anki_ref = self.col.media.escape_media_filenames(
            self.col.media.add_file(local_path)
        )
        if is_audio_ext(anki_ref):
            anki_ref = make_anki_sound_ref(anki_ref)

        return anki_ref

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
                abs_path = root.joinpath(path)
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
                    abs_path,
                    model,
                    deck_name=full_deck,
                    loader=loader,
                    **model_args,
                )
