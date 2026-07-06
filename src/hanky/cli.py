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
    pipe.add_argument(
        "-m",
        "--model",
        dest="model",
        required=True,
        help="Name of the anki model to create cards with.",
    )
    pipe.add_argument(
        "--into",
        dest="deck",
        default=None,
        help="Name of the deck to load cards into. If not specified, defaults to the filename without the extension.",
    )
    _add_fail_fast(pipe)
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
    pipe_dir.add_argument(
        "-m",
        "--model",
        dest="model",
        required=True,
        help="Name of the anki model to create cards with.",
    )
    pipe_dir.add_argument(
        "-r",
        "--recursive",
        dest="is_rec",
        action="store_true",
        default=False,
        help="Recursively load from files in sub directories as well.",
    )
    _add_fail_fast(pipe_dir)
    if has_card_processors:
        _add_processor_args(pipe_dir)

    return parser
