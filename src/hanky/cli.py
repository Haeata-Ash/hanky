import argparse


# def make_parser():
#     parser = argparse.ArgumentParser(
#         "hanky",
#         description="Simple program to allow programatic management of anki cards",
#     )
#     parser.add_argument(
#         "--config",
#         dest="config",
#         nargs=1,
#         help="Path to hanky json configuration file",
#     )


#     object_subparsers = parser.add_subparsers(
#         dest = "object",
#         help="Type of anki object to manage",
#         required = True
#     )


#     card_obj = object_subparsers.add_parser(
#         "card", help="Perform an operation on anki cards."
#     )

#     card_cmds = card_obj.add_subparsers(
#         dest="action",
#         required=True,
#         help="Action to perform against anki cards."
#     )

#     # add anki cards to a deck using model
#     add_card = card_cmds.add_parser("add", help="Add card(s) to an anki deck.")
#     add_card.add_argument("-i", "--input-file", required=True, help="Source file to add the cards from.")
#     add_card.add_argument("-m", "--model", required=True, help="Anki model to create the card from.")
#     add_card.add_argument("-d", "--deck", required=True, help="Anki deck add the card to")
#     add_card.add_argument("--model-args", help="Arguments to pass to the model.")
#     # list anki cards in a deck
#     list_card = card_cmds.add_parser("list", help="List card(s) in an anki deck.")
#     list_card.add_argument("-d", "--deck", required=True, help="List anki cards from deck")


#     deck_obj = object_subparsers.add_parser(
#         "deck", help="Perform an operation on an anki deck."
#     )


#     deck_cmds = deck_obj.add_subparsers(
#         dest="action",
#         required=True,
#         help="Action to perform against an anki deck."
#     )


#     add_deck = deck_cmds.add_parser("add", help="Add deck to the anki collection.")

#     # add anki deck
#     add_deck.add_argument("name", help="Full name of the anki deck, including '::' for nesting.")
#     add_deck.add_argument("-p", "--parent", help="Optionally specify parent deck to avoid manually adding '::' for nesting.")
    
#     # list anki decks
#     add_deck = deck_cmds.add_parser("list", help="Add deck to the anki collection.")


#     model_obj = object_subparsers.add_parser(
#         "model", help="Perform an operation on an anki model."
#     )

#     model_cmds = model_obj.add_subparsers(
#         dest="action",
#         required=True,
#         help="Action to perform against an anki model."
#     )

#     # list anki cards in a deck
#     add_card = model_cmds.add_parser("list", help="List models in anki collection.")
    
#     return parser


class KeyValueArg(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, dict())

        for v in values:
            print(v)
            key, value = v.split("=")
            getattr(namespace, self.dest)[key] = value

def make_parser():
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
        dest = "operation",
        help="Type of operation to perform",
        required = True
    )
    load_file = op_parser.add_parser(
        "load",
        help="Load cards into an anki deck from a file"
    )
    load_file.add_argument(
        "model",
        help="Name of the anki model to create cards with."
    )
    load_file.add_argument("file", help="Path of the file to load from")


    load_file.add_argument("-d", "--deck", dest="deck", default=None, help="Name of the deck to load cards into. If not specified, defaults to the filename without the extension.")
    load_file.add_argument("--args", dest="args", default={}, nargs="*", action=KeyValueArg, help="Key value arguments to pass to registered transformers.")

    load_dir = op_parser.add_parser(
        "load-dir",
        help="Load cards into anki deck(s) from files in a directory, using the filenames as deck names."
    )
    load_dir.add_argument("-r", "--recursive", dest="is_rec", action="store_true", default=False, help="If loading files from a directory, recursively load from files in sub directories as well.")
    load_dir.add_argument(
        "model",
        help="Name of the anki model to create cards with."
    )
    load_dir.add_argument("dir", help="Path of the file to load from")
    load_dir.add_argument("pattern", help="Glob pattern used to decide which files to load. For example, '*.csv'")

    load_dir.add_argument("--args", dest="args", default={}, nargs="*", action=KeyValueArg, help="Key value arguments to pass to registered transformers.")
    return parser
