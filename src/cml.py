import argparse


def make_parser():
    parser = argparse.ArgumentParser(
        "genanki", description="Program to assist generation of language anki cards."
    )
    parser.add_argument(
        "--config",
        dest="config",
        nargs="?",
        help="Path to yaml config file.",
        default="config.toml",
    )
    parser.add_argument(
        "--deck-name",
        required=True,
        dest="deck_name",
        help="Name of the deck to generate",
    )
    parser.add_argument(
        "--model",
        dest="model",
        choices=["lang-understand", "lang-recall"],
        # required=True,
        help="Type of model to load each note in the csv with.",
    )
    parser.add_argument(
        "--lang",
        dest="lang",
        choices=["German", "French", "Italian"],
        help="The language for which to generate speech.",
    )
    parser.add_argument("-i", dest="infile", help="Path to the question csv")

    return parser
