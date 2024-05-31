import hashlib
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Iterator

from anki.collection import Collection
from tomllib import load as toml_load

from hanky.cli import make_parser
from hanky.config import (
    ALLOW_DUPLICATES,
    ANKI_DB_PATH,
    DEFAULT_CONFIG,
    DEFAULT_CONFIG_PATH,
    DO_SAFET_CHECK,
    Config,
)
from hanky.fs import DEFAULT_LOADERS, Loader, has_handle
from hanky.media import is_audio_ext, make_anki_sound_ref


class ModelProcessor:
    """The wrapper for user defined functions which process cards of a certain model.

    Wraps a python callable which takes a dictionary representing an anki card,
    the key word arguments the callable expects and the fields (keys) it
    assumes to be already present in the card.

    Attributes:
        f: the user defined callable which processes each card
        model: The type of card (anki model) which the callable processes
        expected_args: Expected key word arguments of the callable
        card_fields: Anki fields expected to be already present in any cards processed"""

    def __init__(
        self,
        model_name: str,
        func: Callable[[dict], dict],
        expected_args: List[str],
        card_fields: List[str],
    ):
        """Initializes a model processor

        Args:
            func: the user defined callable which processes each card
            model_name: The name of the anki model whose cards the callable processes
            expected_args: Expected key word arguments of the callable
            card_fields: Anki fields expected to be already present in any cards processed
        """

        self.f = func
        self.model = model_name
        self.expected_args = expected_args
        self.card_fields = card_fields

        if not isinstance(self.expected_args, list):
            raise TypeError("'expected_args' must be a list of strings")
        if not isinstance(self.card_fields, list):
            raise TypeError("'required_fields' must be a list of strings")

    def __call__(self, card: dict, **kwargs) -> dict:
        """Check expected fields are present in card and expected key word arguments
        were provided, call the callable on the card and validate output is a dictionary.

        Args:
            card: dictionary representing field, value pairs of an anki card
            **kwargs: key word arguments for the callable

        Returns:
            card dictionary with possibly new fields added by user defined callable

        """
        for k in self.card_fields:
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
    """Manages interactions with the anki collection and exposes a simplified interface for adding cards.
    Optionally runnable as a CLI application.

    Keeps track of 'card processor' functions/callables which enrich or
    transform their data before adding the card to the database.

    Keeps track of 'loader' functions which read possibly incomplete card data from files.

    Attributes:
        config: dictionary representing configuration and kwargs arguments
        processors: dictionary of anki model names mapped to user defined callables
        loaders: dictionary of file extensions mapped to a function which reads card data
    """

    def __init__(self, **options):
        """Initializes a Hanky application object

        Args:
            **options: key values to override/add to configuration data
        """
        # set default config to ensure needed fields are present
        self.config: Config = Config(**DEFAULT_CONFIG)

        # read in config from default location if it exists, overwriting default config
        if DEFAULT_CONFIG_PATH.exists() and DEFAULT_CONFIG_PATH.is_file():
            self.config.from_file(
                DEFAULT_CONFIG_PATH,
                toml_load,
            )

        # overwrite config with any runtime kwargs
        if options:
            self.config.update(options)

        self._col: Collection = None

        self.processors: Dict[str, List[ModelProcessor]] = dict()
        self.loaders: Dict[str, Callable[[str], Iterator[dict]]] = dict()
        for k, v in DEFAULT_LOADERS.items():
            self.register_loader(k, v)

    def run(self) -> None:
        """Run the Hanky object as a CLI application"""

        # check if we should show --args option
        # no need if there are no defined card processors
        parser = make_parser(bool(self.processors))

        args = parser.parse_args()

        # read in configuration from user specified location,
        # overwriting any existing config
        if args.config:
            self.config.from_file(args.config, toml_load)

        # model arguments we handle seperately
        # since can't check if they are present in
        # the namespace
        model_args = {}
        try:
            model_args = args.args
        except AttributeError:
            pass

        if args.operation == "load":
            self.load_deck(
                args.file,
                args.model,
                deck_name=args.deck,
                **model_args,
            )

        elif args.operation == "load-dir":
            self.load_dir(
                args.model,
                args.dir,
                args.pattern,
                args.is_rec,
                **model_args,
            )

    @property
    def col(self) -> Collection:
        """Anki collection. Access will raise an error if another processes is
        using the anki database"""
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
                        """At least one other process is using the anki database. Ensure the Anki application is closed before using Hanky to avoid possible database corruption."""
                    )

            self._col = Collection(str(db_path))
        return self._col

    def add_card(
        self,
        deck_name: str,
        model_name: str,
        # filter_query: Optional[str] = None,
        allow_duplicates=False,
        **fields,
    ) -> bool:
        """Adds a card of a given model type to a deck.

        Args:
            deck_name: the full destination deck name as a seen in anki.
            model_name: the name of the flash card model as seen in anki.
            allow_duplicates: Whether or not to add the card if a matching one already exists.

        Returns:
            A bool, true if the card was successfully added, false otherwise

        Raises:
            ValueError: The deck or model don't exist
            KeyError: The card does not have the required fields for the model
        """
        model = self.col.models.by_name(model_name)
        if model is None:
            raise ValueError(
                f"Model '{model_name}' does not exist in your anki collection. Ensure it has been added before using it with hanky."
            )
        deck_id = self.col.decks.id(deck_name, create=False)
        if deck_id is None:
            raise ValueError(
                f"Deck '{deck_name}' does not exist in your anki collection. Ensure it has been created before using it with hanky."
            )

        expected_fields = self.col.models.field_names(model)
        for k in expected_fields:
            if k not in fields:
                raise KeyError(f"Expected field '{k}' is missing. {fields}")

        new_card = self.col.new_note(model)

        for k, v in fields.items():
            new_card[k] = str(v).strip()

        allow_duplicates = (
            allow_duplicates if allow_duplicates else self.config[ALLOW_DUPLICATES]
        )

        # check for duplicates based off of the sort field
        if not allow_duplicates:
            # rets = [True]

            # get the models sort index
            sort_idx = self.col.models.sort_idx(model)

            # models fields in the form
            # {name: (order_idx, field object) for f in notetype["flds"]}
            field_map = self.col.models.field_map(model)

            # search fields for index field. Index field always 0
            res = list(filter(lambda x: field_map[x][0] == sort_idx, field_map))

            # should only ever be one matching field
            assert len(res) == 1
            idx_field = res[0]

            # for field in fields:
            #     notes = self.col.find_cards(f"{field}:{fields[field]}")
            #     print(len(notes), f"{field}:{fields[field].strip()}")
            #     if notes:
            #         rets.append(True)
            #     else:
            #         rets.append(False)
            # is_dupe = functools.reduce(lambda x, y: x and y, rets)
            # if is_dupe:
            #     return False
            # print(f"######## {is_dupe}")

            # at least one other card has a matching index field
            # encase field value in double quotes for multi word field values
            if len(self.col.find_cards(f'{idx_field}:"{fields[idx_field]}"')):
                return False
        self.col.add_note(new_card, deck_id)

        return True

    def add_deck(self, deck_name: str) -> bool:
        """Adds a deck to anki

        Args:
            deck_name: the full name of the deck to be added

        Returns:
            A bool, true if the deck was successfully added, false otherwise
        """
        deck_id = self.col.decks.id(deck_name)
        if deck_id is None:
            return False
        return True

    def register_loader(
        self, file_ext: str, loader: Loader, is_text=True, **loader_kwargs
    ) -> None:
        """Register a function to use to load card data from files with a certain extension.

        Args:
            file_ext:
                the file ext, including the dot, for example '.csv'
            loader: the callable which takes an IO object and returns
                dictionaries of card data
            is_text: If the loader reads the file as text (rather than binary),
                true if it does

        Returns:
            None
        """

        # wraps the loader in a generator function
        # if the file is not found we handle and print to the user
        # validates that the loader returns dictionaries when iterated on
        def loader_wrapper(fpath: str) -> Iterator[dict]:
            try:
                with open(fpath, "r" if is_text else "rb") as f:
                    for item in loader(f, **loader_kwargs):
                        if not isinstance(item, dict):
                            raise ValueError(
                                f"Item returned by loader for file extension '{file_ext}' did not return a dictionary."
                            )
                        yield item
            except FileNotFoundError:
                print(f"File {fpath} could not be found.")
                print("Exiting...")

        self.loaders[file_ext] = loader_wrapper

    def register_card_processor(
        self,
        model_name: str,
        processor: Callable[[dict], dict],
        expected_args: List[str] = [],
        card_fields: List[str] = [],
    ) -> None:
        """Adds a python callable to be called when adding a card of type model.

        The callable will be called with the first argument being the card
        data (a dictionary mapping field names to values) BEFORE the card
        is added to the anki database. A registered function could be used
        to alter existing card data (transform), add data (enrich) or anything else.

        If multiple callables are registered, they will be called in the same
        order in which they were registered.

        Args:
            model_name: the name of the card model
            processor: the callable to apply to the cards of the given model type
            expected_args: list of arguments expected by the callable
            card_fields: list of fields expected to be present in the card
                when the callable is applied

        Returns:
            None
        """
        if model_name not in self.processors:
            self.processors[model_name] = []
        self.processors[model_name].append(
            ModelProcessor(model_name, processor, expected_args, card_fields)
        )

    def card_processor(
        self, model: str, expected_args: List[str], card_fields: List[str]
    ):
        """Decorator which automatically registers a card processor function

        A card processor takes a card (dictionary of field, value pairs) and any
        defined arguments and then performs some action based on its fields or
        values. For example it could be used to:
            - generate media, such as audio based on the field of a card
            - query an api for a translation, based on the field of a card
            - ensure all fields are lower case
            - perform a mathmatical operation then write back the answer as a string
            - set a field of a card which is currently missing

        The decoracted function will be called every time a card of type model
        is added. The first argument to the decorated function will always be
        the card data as a dictionary of fields, value pairs.

        The decorated function must return a dictionary.

        Args:
            model_name: the name of the card model
            expected_args: list of named arguments expected by the card processor.
                They will be passed in as key word arguments.
            card_fields: list of fields expected to be present in the card
                when the card processor is called.

        Returns:
            Decorated card processor function
        """

        def decorator(func):
            self.register_card_processor(model, func, expected_args, card_fields)
            return func

        return decorator

    def get_model_processors(self, model_name: str) -> List[ModelProcessor]:
        """Get all card processors for a particular model"""
        if model_name in self.processors:
            return self.processors[model_name]

        return []

    def get_loader(self, suffix) -> Callable:
        """Get the loader function for a particular file extension"""
        return self.loaders[suffix]

    def load_deck(
        self,
        fpath: str,
        model_name: str,
        deck_name: Optional[str] = None,
        **model_args,
    ) -> bool:
        """Load cards from a file into a deck.

        Args:
            fpath: the path to the file
            model_name: The anki model/card type of the cards in the file
            deck_name: Optionally the name of the deck. Defaults to the
                filename without its extension.
            **model_args: arguments to provide to the card processor functions

        Returns:
            bool, true if the operation was successful, false otherwise
        """
        path = Path(fpath).absolute()

        transformers = self.get_model_processors(model_name)

        model = self.col.models.by_name(model_name)
        if not model:
            raise KeyError(
                f"Model '{model_name}' does not exist in your anki collection. Ensure it has been added before using it with hanky."
            )

        # deck is the specified name or filename without extension
        deck_name = deck_name if deck_name else path.stem
        print(f"Loading into deck {deck_name}")
        self.add_deck(deck_name)

        count = 0
        total = 0
        for item in self.get_loader(path.suffix)(str(path.absolute())):
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
        return True

    def add_media(
        self,
        data: Any,
        media_fname: Optional[str] = None,
        file_ext: Optional[str] = None,
    ) -> str:
        """Add binary data as an anki media file.

        Args:
            data: the binary media data
            media_fname: The filename including the extension. Defaults to a
                 sha256 hexdigest of the data.
            file_ext: The file extension to use which should match the data type,
                for example, '.mp3'. Must be given if the media_fname is not
                provided

        Returns:
            string which can be placed in an anki card to reference the media.
            The string might be a uri, '[sound:my_audio.mp3]' for example in the
            case of audio, or something else.

        Raises:
            ValueError if media_fname and file_ext are both not provided
        """
        ext = None
        if media_fname:
            path = Path(media_fname)
            ext = path.suffix
        elif file_ext:
            ext = file_ext
        else:
            raise ValueError(
                "If argument 'media_fname' is not provided then 'file_ext' must be present"
            )

        if isinstance(data, str):
            data = data.encode()

        desired_name = media_fname

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

    def add_media_file(self, fpath: str) -> str:
        """Add a file to anki media.

        Args:
            fpath: path to the file being added

        Returns:
            string which can be placed in an anki card to reference the media.
            The string might be a uri, '[sound:my_audio.mp3]' for example in the
            case of audio, or something else.
        """
        anki_ref = self.col.media.escape_media_filenames(self.col.media.add_file(fpath))
        if is_audio_ext(anki_ref):
            anki_ref = make_anki_sound_ref(anki_ref)

        return anki_ref

    def load_dir(
        self,
        model: str,
        root_dir: str,
        glob_pattern: str,
        recursive=False,
        **model_args,
    ) -> bool:
        """Load cards from file(s) inside a directory.

        The deck names are built from the relative paths of each file from the
        root directory. So the following file system structure with root directory
        'french':
        french
        ├── animals.csv
        ├── bodies.csv
        ├── clothing.csv
        └── grammar
            └── passe_compose.csv

        Results in the following decks:
        french
        french::animals
        french::bodies
        french::clothing
        french::grammar
        french::grammar::passe_compose

        Args:
            model_name: The anki model/card type of the cards which will be loaded
            root_dir: The root directory in which to find the files
            glob_pattern: A glob pattern such as '*.csv' to match the desired files
            recursive: whether or not to descend into sub directories, defaults to false
            **model_args: arguments to provide to the card processor functions

        Returns:
            bool, true if the operation was successful, false otherwise
        """
        root = Path(root_dir).expanduser()

        root_deck = root.name

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
                    str(abs_path),
                    model,
                    deck_name=full_deck,
                    **model_args,
                )

        return True
