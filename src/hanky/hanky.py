from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    Iterator,
    List,
    Mapping,
    Optional,
    Sequence,
)

from anki.collection import Collection

from hanky.processors import CardProcessingException, ModelProcessor
from hanky.cli import make_parser
from hanky.config import Config
from hanky.fs import DEFAULT_LOADERS, Loader, has_handle, make_file_loader
from hanky.media import CardMedia
from hanky.report import CardError, LoadReport

from anki.notes import NoteFieldsCheckResult

_DEFAULT_CONFIG_PATH = Path("~/.config/hanky/hanky.toml").expanduser()


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

    def __init__(self, config: Optional[Config] = None):
        """Initializes a Hanky application object

        Note: if no config object is provided, hanky will try load from the default config location,
        before finally using the default configuration values if the file does not exist.

        Args:
            config: custom config object
        """
        self._config = config

        # TODO: figure out a way to narrow this type so we don't have to ignore
        # It should never be none anyway after run is called
        self._col: Collection = None  # type: ignore

        self.processors: Dict[str, List[ModelProcessor]] = dict()
        self.loaders: Dict[str, Callable[[str], Iterator[dict]]] = dict()
        for ext, spec in DEFAULT_LOADERS.items():
            self.register_loader(
                ext, spec.loader, is_text=spec.is_text, **spec.fopen_kwargs
            )

    @property
    def config(self):
        """Hanky application configuration. Lazy loaded on first use.

        Note that if configuration is not provided, hanky will try to lazy load from
        default config file location. If the file does not exist, hanky will use the
        default configuration.

        """
        if self._config is not None:
            return self._config

        if _DEFAULT_CONFIG_PATH.is_file():
            self._config = Config.from_toml(_DEFAULT_CONFIG_PATH.as_posix())
        else:
            self._config = Config()

        return self._config

    @property
    def col(self) -> Collection:
        """Anki collection. Access will raise an error if another processes is
        using the anki database"""
        if not self._col:
            db_path = Path(self.config.ANKI_DB_PATH).expanduser().absolute()

            if not db_path.exists() or not db_path.is_file():
                raise FileNotFoundError(
                    f"'{db_path}' either does not exist or is not a file. Please check the provided path to the anki collection."
                )

            if self.config.DO_SAFETY_CHECK:
                if has_handle(self.config.ANKI_DB_PATH):
                    raise RuntimeError(
                        """At least one other process is using the anki database. Ensure the Anki application is closed before using Hanky to avoid possible database corruption."""
                    )

            self._col = Collection(str(db_path))
            self.backup_collection(self.config.BACKUP_FOLDER)

        return self._col

    def backup_collection(self, backup_folder: str):
        """Backups the anki collection to the configured backup"""
        folder_path = Path(backup_folder)
        folder_path.mkdir(parents=True, exist_ok=True)
        if not self._col.create_backup(
            backup_folder=backup_folder,
            force=True,
            wait_for_completion=True,
        ):
            raise RuntimeError("Unable to create backup of anki collection.")

    def add_card(
        self,
        deck_name: str,
        model_name: str,
        **fields,
    ) -> bool:
        """Adds a card of a given model type to a deck.

        Args:
            deck_name: the full destination deck name as a seen in anki.
            model_name: the name of the flash card model as seen in anki.

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

        # use anki builtin duplicate detection to check for duplicates
        if not self.config.ALLOW_DUPLICATES:
            card_state = new_card.duplicate_or_empty()
            if card_state == NoteFieldsCheckResult.DUPLICATE:
                return False

        self.col.add_note(new_card, deck_id)

        return True

    def add_deck(self, deck_name: str):
        """Adds a deck to anki. If the deck already exists nothing will happen

        Args:
            deck_name: the full name of the deck to be added
        """
        self.col.decks.id(deck_name)

    def register_loader(
        self, file_ext: str, loader: Loader, is_text=True, **fopen_kwargs
    ) -> None:
        """Register a function to use to load card data from files with a certain extension.

        Args:
            file_ext:
                the file ext, including the dot, for example '.csv'
            loader: the callable which takes an IO object and returns
                dictionaries of card data
            is_text: If the loader reads the file as text (rather than binary),
                true if it does
            fopen_kwargs: Any other keyword args to be passed to open() call

        Returns:
            None
        """
        # extensions are matched case-insensitively
        file_ext = file_ext.lower()
        self.loaders[file_ext] = make_file_loader(loader, is_text, **fopen_kwargs)

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
            ModelProcessor(processor, expected_args, card_fields)
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
        suffix = suffix.lower()
        if suffix not in self.loaders:
            supported = ", ".join(sorted(self.loaders)) or "none"
            raise ValueError(
                f"No loader is registered for the file extension '{suffix}'. "
                f"Supported extensions: {supported}. Register a loader for "
                f"this extension with register_loader()."
            )
        return self.loaders[suffix]

    def load_cards(
        self,
        source: Iterable[Mapping],
        model_name: str,
        deck_name: str,
        fail_fast: bool = False,
        **model_args,
    ) -> LoadReport:
        """Load cards from any iterable of dictionaries into a deck.

        By default a card that cannot be added is recorded then skipped and loading
        continues with the next card. Pass ``fail_fast=True`` to instead raise
        on the first such card.

        Args:
            source: any iterable yielding dictionaries (mappings) of card
                field names to values
            model_name: The anki model/card type of the cards
            deck_name: the name of the destination deck
            fail_fast: raise on the first bad card instead of collecting it
            **model_args: arguments to provide to the card processor functions

        Returns:
            A :class:`LoadReport` describing what was added, skipped and failed.

        Raises:
            KeyError: the model does not exist in the collection
            Exception: if ``fail_fast`` is set, whatever a bad card raised
        """
        transformers = self.get_model_processors(model_name)

        model = self.col.models.by_name(model_name)
        if not model:
            raise KeyError(
                f"Model '{model_name}' does not exist in your anki collection. Ensure it has been added before using it with hanky."
            )

        self.add_deck(deck_name)

        added = 0
        skipped = 0
        errors: List[CardError] = []
        for item in source:
            try:
                if not isinstance(item, Mapping):
                    raise ValueError(
                        f"Card source for model '{model_name}' yielded a "
                        f"{type(item).__name__}, expected a dictionary (mapping)."
                    )
                card = dict(item)
                media: List[CardMedia] = []
                for t in transformers:
                    card, new_media = t(card, **model_args)
                    media += new_media

                # TODO: we are leaving the media in the db even if the card
                # isn't added
                for m in media:
                    actual_fname = self.add_media(m.data, m.desired_name)
                    m.replace_temp_refs(actual_fname, card)

                if self.add_card(deck_name, model_name, **card):
                    added += 1
                else:
                    skipped += 1
            except Exception as e:
                # inject model info into exception which processor doesn't know
                if isinstance(e, CardProcessingException):
                    e.model = model_name
                if fail_fast:
                    raise
                errors.append(CardError(card=item, error=str(e)))

        return LoadReport(added=added, skipped=skipped, errors=errors)

    def load_deck(
        self,
        fpath: str,
        model_name: str,
        deck_name: Optional[str] = None,
        fail_fast: bool = False,
        **model_args,
    ) -> LoadReport:
        """Load cards from a file into a deck.

        Reads the file using the loader registered for its extension and feeds
        the resulting dictionaries into :meth:`load_cards`.

        Args:
            fpath: the path to the file
            model_name: The anki model/card type of the cards in the file
            deck_name: Optionally the name of the deck. Defaults to the
                filename without its extension.
            fail_fast: raise on the first bad card instead of collecting it
            **model_args: arguments to provide to the card processor functions

        Returns:
            A :class:`LoadReport`, with the file path recorded against any
            errors.
        """
        path = Path(fpath).absolute()

        # deck is the specified name or filename without extension
        deck_name = deck_name if deck_name else path.stem

        source = self.get_loader(path.suffix)(str(path))
        report = self.load_cards(
            source, model_name, deck_name, fail_fast=fail_fast, **model_args
        )
        return report.with_source(str(path))

    def add_media(
        self,
        data: Any,
        media_fname: str,
    ) -> str:
        """Add binary data to the anki collection.

        Args:
            data: the binary media data
            media_fname: The filename including the extension

        Returns:
            The media filename after adding it to anki collection
        """
        desired_name = media_fname

        # write media to anki database
        actual_name = self.col.media.write_data(
            desired_name,
            data,
        )

        return actual_name

    def load_dir(
        self,
        model: str,
        root_dir: str,
        glob_pattern: str,
        recursive=False,
        fail_fast: bool = False,
        **model_args,
    ) -> LoadReport:
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
            fail_fast: raise on the first bad card instead of collecting it
            **model_args: arguments to provide to the card processor functions

        Returns:
            A :class:`LoadReport` aggregating the results across every file.
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

        report = LoadReport()
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

                report += self.load_deck(
                    str(abs_path),
                    model,
                    deck_name=full_deck,
                    fail_fast=fail_fast,
                    **model_args,
                )

        return report

    def run(self) -> None:
        """Run the Hanky object as a CLI application. Useful for people extending the
        hanky app or making use of processors or loaders.
        """
        _run_app(self)


def _run_app(app: Hanky, args: Optional[Sequence[str]] = None):
    """Run a Hanky object as a CLI application"""

    # check if we should show --args option
    # no need if there are no defined card processors
    parser = make_parser(bool(app.processors))

    if args is None:
        parsed_args = parser.parse_args()
    else:
        parsed_args = parser.parse_args(args)

    # model arguments we handle seperately
    # since can't check if they are present in
    # the namespace
    model_args = {}
    try:
        model_args = parsed_args.args
    except AttributeError:
        pass

    report = LoadReport()
    if parsed_args.operation == "load":
        print(f"Loading into deck {parsed_args.deck} from file {parsed_args.file}")
        report = app.load_deck(
            parsed_args.file,
            parsed_args.model,
            deck_name=parsed_args.deck,
            fail_fast=parsed_args.fail_fast,
            **model_args,
        )

    elif parsed_args.operation == "load-dir":
        print(f"Loading from dirrectory {parsed_args.dir}")
        report = app.load_dir(
            parsed_args.model,
            parsed_args.dir,
            parsed_args.pattern,
            parsed_args.is_rec,
            fail_fast=parsed_args.fail_fast,
            **model_args,
        )

    _print_report(report)


def _print_report(report: LoadReport) -> None:
    """Print a human readable summary of a load operation to stdout."""
    print(
        f"Added {report.added}, skipped {report.skipped}, "
        f"failed {report.failed} (of {report.total} cards)."
    )
    for err in report.errors:
        where = f" [{err.source}]" if err.source else ""
        print(f"  failed{where}: {err.error}")
