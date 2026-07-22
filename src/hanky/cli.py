import argparse


class KeyValueArg(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, dict())

        for v in values:
            key, value = v.split("=", 1)
            getattr(namespace, self.dest)[key] = value


def _add_fail_fast(subparser):
    subparser.add_argument(
        "--fail-fast",
        dest="fail_fast",
        action="store_true",
        default=False,
        help="Stop and raise on the first card that cannot be added, instead of skipping it and reporting at the end.",
    )


def _add_dry_run(subparser):
    subparser.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        default=False,
        help="Run card processors and report what would happen, without "
        "touching your anki collection (no deck, media, cards, or backup).",
    )


def _add_model_override(subparser):
    subparser.add_argument(
        "-m",
        "--model",
        dest="model",
        required=False,
        default=None,
        help="Override the name of the anki model to create cards with.",
    )


def _add_processor_args(subparser):
    subparser.add_argument(
        "--args",
        dest="args",
        default={},
        nargs="*",
        action=KeyValueArg,
        help="Key value arguments to pass to your card processor functions.",
    )


def make_parser(has_card_processors=False):
    parser = argparse.ArgumentParser(
        "hanky",
        description="Simple program to allow programatic management of anki cards",
    )

    op_parser = parser.add_subparsers(
        dest="operation", help="Type of operation to perform", required=True
    )

    pipe = op_parser.add_parser(
        "pipe", help="Pipe card(s) from a file into an anki deck."
    )
    pipe.add_argument("file", help="Path of the file to load from")
    _add_model_override(pipe)
    pipe.add_argument(
        "--into",
        dest="deck",
        default=None,
        help="Name of the deck to load cards into. If not specified, defaults to the filename without the extension.",
    )
    _add_fail_fast(pipe)
    _add_dry_run(pipe)
    if has_card_processors:
        _add_processor_args(pipe)

    pipe_dir = op_parser.add_parser(
        "pipe-dir",
        help="Pipe card(s) from files in a directory into anki deck(s), using the path to build deck names.",
    )
    pipe_dir.add_argument("dir", help="Path of the directory to load from")
    pipe_dir.add_argument(
        "pattern",
        help="Glob pattern used to decide which files to load. For example, '*.csv'",
    )
    _add_model_override(pipe_dir)
    pipe_dir.add_argument(
        "-r",
        "--recursive",
        dest="is_rec",
        action="store_true",
        default=False,
        help="Recursively load from files in sub directories as well.",
    )
    _add_fail_fast(pipe_dir)
    _add_dry_run(pipe_dir)
    if has_card_processors:
        _add_processor_args(pipe_dir)

    return parser
