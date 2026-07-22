from contextlib import contextmanager
from pathlib import Path
from typing import (
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

from hanky.anki_utils import add_card, add_deck, add_media, backup_collection
from hanky.processors import CardProcessingException, CardProcessor
from hanky.cli import make_parser
from hanky.config import Config
from hanky.errors import (
    CollectionInUseError,
    CollectionNotFoundError,
    ModelNotFoundError,
    UnsupportedFileTypeError,
)
from hanky.fs import DEFAULT_LOADERS, Loader, has_handle, make_file_loader
from hanky.media import CardMedia
from hanky.report import CardError, LoadReport

_DEFAULT_CONFIG_PATH = Path("~/.config/hanky/hanky.toml").expanduser()


class HankyPipeline:
    """An ETL style pipeline for adding flash cards to anki. The class manages
    interactions with the anki collection and exposes a simplified interface
    for adding transformation logic. Optionally runnable as a CLI application.

    Cards are added using the anki model/note type the pipeline was constructed
    with (a single CLI run can override it via --model).

    Keeps track of 'card processor' functions/callables which enrich or
    transform their data before adding the card to the database.

    Keeps track of 'loader' functions which read possibly incomplete card data from files.

    Attributes:
        config: the pipeline's Config object, lazy loaded if not provided
        processors: list of user defined card processor callables, in registration order
        loaders: dictionary of file extensions mapped to a function which reads card data
    """

    def __init__(self, model: str, *, config: Optional[Config] = None):
        """Initializes a HankyPipeline application object

        Note: if no config object is provided, hanky will try load from the default config location,
        before finally using the default configuration values if the file does not exist.

        Args:
            model: the name of the anki model/note type to create cards with
            config: custom config object
        """
        if not isinstance(model, str):
            raise TypeError(
                "'model' must be the name of an anki model/note type (a string)"
            )

        self._config = config

        self._col: Optional[Collection] = None
        self._model = model
        self.processors: List[CardProcessor] = list()
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

    def _open_collection(self) -> Collection:
        """Open the anki collection object if its not already open.

        **The collection must be closed** with :meth:`_close_collection`, since
        it opens an sqlite db conn under the hood

        First access will raise an error if another processes has a handle for the
        collection AND the hanky process has the neccessary permissions to see the handle.
        """
        if not self._col:
            db_path = Path(self.config.ANKI_DB_PATH).expanduser().absolute()

            if not db_path.exists() or not db_path.is_file():
                raise CollectionNotFoundError(
                    f"'{db_path}' either does not exist or is not a file. Please check the provided path to the anki collection."
                )

            if self.config.DO_SAFETY_CHECK:
                if has_handle(self.config.ANKI_DB_PATH):
                    raise CollectionInUseError(
                        "At least one other process is using the anki database. "
                        "Ensure the Anki application is closed before using Hanky "
                        "to avoid possible database corruption."
                    )

            self._col = Collection(str(db_path))

        return self._col

    def _close_collection(self):
        """Close the anki collection and its underlying sqlite conn."""
        if self._col is not None:
            self._col.close()
        # drop the reference so a closed collection is never handed back out
        # and a later session can re-open cleanly
        self._col = None

    @contextmanager
    def session(self) -> Iterator[Collection]:
        """Opens the anki collection if it isn't already open, and closes it on exit
        including when the body raises. Any exception from the body propagates unchanged.

        Only the scope that opened the collection closes it, so sessions may
        be nested safely.

        Yields:
            The open anki :class:`~anki.collection.Collection`.
        """
        # duplicated boolean because mypy wasn't
        # seeing was_opened_here
        was_opened_here = self._col is None
        if self._col is None:
            self._col = self._open_collection()
        try:
            yield self._col
        finally:
            if was_opened_here:
                self._close_collection()

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
        processor: Callable[[dict], dict],
        expected_args: List[str] = [],
        card_fields: List[str] = [],
    ) -> None:
        """Adds a python callable to be called as a processor during a pipeline run.

        The callable will be called with the first argument being the card
        data (a dictionary mapping field names to values) BEFORE the card
        is added to the anki database. A registered function could be used
        to alter existing card data (transform), add data (enrich) or anything else.

        If multiple callables are registered, they will be called in the same
        order in which they were registered.

        Args:
            processor: the callable to apply to each card
            expected_args: list of arguments expected by the callable
            card_fields: list of fields expected to be present in the card
                when the callable is applied

        Returns:
            None
        """
        self.processors.append(CardProcessor(processor, expected_args, card_fields))

    def card_processor(self, expected_args: List[str], card_fields: List[str]):
        """Decorator which automatically registers a card processor function

        A card processor takes a card (dictionary of field, value pairs) and any
        defined arguments and then performs some action based on its fields or
        values. For example it could be used to:
            - generate media, such as audio based on the field of a card
            - query an api for a translation, based on the field of a card
            - ensure all fields are lower case
            - perform a mathmatical operation then write back the answer as a string
            - set a field of a card which is currently missing

        The decorated function will be called on every card each time the pipeline
        is run, whether via the CLI or the import_from_* methods. The first argument
        to the decorated function will always be the card data as a dictionary of
        fields, value pairs.

        The decorated function must return a dictionary.

        Args:
            expected_args: list of named arguments expected by the card processor.
                They will be passed in as key word arguments.
            card_fields: list of fields expected to be present in the card
                when the card processor is called.

        Returns:
            Decorated card processor function
        """

        def decorator(func):
            self.register_card_processor(func, expected_args, card_fields)
            return func

        return decorator

    def get_loader(self, suffix) -> Callable:
        """Get the loader function for a particular file extension"""
        suffix = suffix.lower()
        if suffix not in self.loaders:
            supported = ", ".join(sorted(self.loaders)) or "none"
            raise UnsupportedFileTypeError(
                f"No loader is registered for the file extension '{suffix}'. "
                f"Supported extensions: {supported}. Register a loader for "
                f"this extension with register_loader()."
            )
        return self.loaders[suffix]

    def import_from_source(
        self,
        source: Iterable[Mapping],
        deck_name: str,
        fail_fast: bool = False,
        dry_run: bool = False,
        **model_args,
    ) -> LoadReport:
        """Load cards from any iterable of dictionaries into a deck.

        By default a card that cannot be added is recorded then skipped and loading
        continues with the next card. Pass ``fail_fast=True`` to instead raise
        on the first such card.

        Args:
            source: any iterable yielding dictionaries (mappings) of card
                field names to values
            deck_name: the name of the destination deck
            fail_fast: raise on the first bad card instead of collecting it
            dry_run: run card processors and build the report as normal, but
                don't create the deck, write media, or add any cards. Duplicate
                cards will not be found.
            **model_args: arguments to provide to the card processor functions

        Returns:
            A :class:`LoadReport` describing what was added, skipped and failed.

        Raises:
            ModelNotFoundError: the pipeline's model does not exist in the collection
            Exception: if ``fail_fast`` is set, whatever a bad card raised
        """

        with self.session() as col:
            model = col.models.by_name(self._model)
            if not model:
                raise ModelNotFoundError(
                    f"Model '{self._model}' does not exist in your anki collection. Ensure it has been added before using it with hanky."
                )

            if not dry_run:
                add_deck(col, deck_name)

            added = 0
            skipped = 0
            errors: List[CardError] = []
            for item in source:
                try:
                    if not isinstance(item, Mapping):
                        raise ValueError(
                            f"Card source for model '{self._model}' yielded a "
                            f"{type(item).__name__}, expected a dictionary (mapping)."
                        )
                    card = dict(item)
                    media: List[CardMedia] = []
                    for t in self.processors:
                        card, new_media = t(card, **model_args)
                        media += new_media

                    if dry_run:
                        for m in media:
                            m.replace_temp_refs(m.desired_name, card)
                        added += 1
                    else:
                        # TODO: we are leaving the media in the db even if the card
                        # isn't added
                        for m in media:
                            actual_fname = add_media(col, m.data, m.desired_name)
                            m.replace_temp_refs(actual_fname, card)

                        if add_card(
                            col,
                            deck_name,
                            self._model,
                            allow_duplicates=self.config.ALLOW_DUPLICATES,
                            **card,
                        ):
                            added += 1
                        else:
                            skipped += 1
                except Exception as e:
                    # inject model info into exception which processor doesn't know
                    if isinstance(e, CardProcessingException):
                        e.model = self._model
                    if fail_fast:
                        raise
                    errors.append(CardError(card=item, error=str(e)))

            return LoadReport(added=added, skipped=skipped, errors=errors)

    def import_from_file(
        self,
        fpath: str,
        deck_name: Optional[str] = None,
        fail_fast: bool = False,
        dry_run: bool = False,
        **model_args,
    ) -> LoadReport:
        """Load cards from a file into a deck.

        Reads the file using the loader registered for its extension and feeds
        the resulting dictionaries into :meth:`import_from_source`.

        Args:
            fpath: the path to the file
            deck_name: Optionally the name of the deck. Defaults to the
                filename without its extension.
            fail_fast: raise on the first bad card instead of collecting it
            dry_run: see :meth:`import_from_source`
            **model_args: arguments to provide to the card processor functions

        Returns:
            A :class:`LoadReport`, with the file path recorded against any
            errors.
        """
        path = Path(fpath).absolute()

        # deck is the specified name or filename without extension
        deck_name = deck_name if deck_name else path.stem

        source = self.get_loader(path.suffix)(str(path))
        report = self.import_from_source(
            source, deck_name, fail_fast=fail_fast, dry_run=dry_run, **model_args
        )
        return report.with_source(str(path))

    def import_from_dir(
        self,
        root_dir: str,
        glob_pattern: str,
        recursive=False,
        fail_fast: bool = False,
        dry_run: bool = False,
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
            root_dir: The root directory in which to find the files
            glob_pattern: A glob pattern such as '*.csv' to match the desired files
            recursive: whether or not to descend into sub directories, defaults to false
            fail_fast: raise on the first bad card instead of collecting it
            dry_run: see :meth:`import_from_source`
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

        # open collection session once, nested calls in import_from_file
        # will reuse the session
        with self.session() as _:
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

                    report += self.import_from_file(
                        str(abs_path),
                        deck_name=full_deck,
                        fail_fast=fail_fast,
                        dry_run=dry_run,
                        **model_args,
                    )

        return report

    def run(self) -> None:
        """Run the HankyPipeline object as a CLI application. This method
        performs a backup of the current anki collection, unless run with
        ``--dry-run``.

        """
        _run_app(self)


def _run_app(app: HankyPipeline, args: Optional[Sequence[str]] = None):
    """Run a HankyPipeline object as a CLI application"""

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

    # TODO: shouldn't really mutate _model like this
    if parsed_args.model is not None:
        app._model = parsed_args.model

    dry_run = parsed_args.dry_run
    if dry_run:
        print("Dry run: no changes will be made to your anki collection.")
    else:
        with app.session() as col:
            backup_collection(col, app.config.BACKUP_FOLDER)

    report = LoadReport()
    if parsed_args.operation == "pipe":
        print(f"Loading into deck {parsed_args.deck} from file {parsed_args.file}")
        report = app.import_from_file(
            parsed_args.file,
            deck_name=parsed_args.deck,
            fail_fast=parsed_args.fail_fast,
            dry_run=dry_run,
            **model_args,
        )

    elif parsed_args.operation == "pipe-dir":
        print(f"Loading from dirrectory {parsed_args.dir}")
        report = app.import_from_dir(
            parsed_args.dir,
            parsed_args.pattern,
            parsed_args.is_rec,
            fail_fast=parsed_args.fail_fast,
            dry_run=dry_run,
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
