import argparse


class KeyValueArg(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, dict())

        for v in values:
            print(v)
            key, value = v.split("=")
            getattr(namespace, self.dest)[key] = value


def make_parser(has_card_processors=False):
    parser = argparse.ArgumentParser(
        "hanky",
        description="Simple program to allow programatic management of anki cards",
    )
    parser.add_argument(
        "--config",
        dest="config",
        help="Path to hanky toml configuration file",
    )

    op_parser = parser.add_subparsers(
        dest="operation", help="Type of operation to perform", required=True
    )
    load_file = op_parser.add_parser(
        "load", help="Load card(s) into an anki deck from a file."
    )
    load_file.add_argument("model", help="Name of the anki model to create cards with.")
    load_file.add_argument("file", help="Path of the file to load from")

    load_file.add_argument(
        "-d",
        "--deck",
        dest="deck",
        default=None,
        help="Name of the deck to load cards into. If not specified, defaults to the filename without the extension.",
    )
    if has_card_processors:
        load_file.add_argument(
            "--args",
            dest="args",
            default={},
            nargs="*",
            action=KeyValueArg,
            help="Key value arguments to pass to your card processor functions.",
        )

    load_dir = op_parser.add_parser(
        "load-dir",
        help="Load card(s) into anki deck(s) from files in a directory, using the path to build deck names.",
    )
    load_dir.add_argument(
        "-r",
        "--recursive",
        dest="is_rec",
        action="store_true",
        default=False,
        help="If loading files from a directory, recursively load from files in sub directories as well.",
    )
    load_dir.add_argument("model", help="Name of the anki model to create cards with.")
    load_dir.add_argument("dir", help="Path of the file to load from")
    load_dir.add_argument(
        "pattern",
        help="Glob pattern used to decide which files to load. For example, '*.csv'",
    )

    if has_card_processors:
        load_dir.add_argument(
            "--args",
            dest="args",
            default={},
            nargs="*",
            action=KeyValueArg,
            help="Key value arguments to pass to your card processor functions.",
        )
    return parser
