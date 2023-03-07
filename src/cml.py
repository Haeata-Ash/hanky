import argparse


def make_parser():
    parser = argparse.ArgumentParser(
        "genanki", description="Program to assist generation of language anki cards"
    )
    parser.add_argument(
        "--db", dest="ankidb", required=True, help="Path to ankidb file."
    )
    parser.add_argument(
        "--deck-name",
        required=True,
        dest="deck_name",
        help="Name of the deck to generate",
    )
    parser.add_argument("-i", dest="csv_fpath", help="Path to the question csv")

    return parser
