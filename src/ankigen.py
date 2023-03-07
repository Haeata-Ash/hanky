from anki.collection import Collection
from cml import make_parser
from load_deck import load_lang_deck


if __name__ == "__main__":
    parser = make_parser()
    args = parser.parse_args()
    collection = Collection(args.ankidb)
    cont = input(
        f"Loading deck '{args.deck_name}'. This will update any deck with the same name. Continue [y/n]: "
    )
    if cont == "y":
        if args.csv_fpath:
            load_lang_deck(args.csv_fpath, collection, args.deck_name)
        else:
            collection.decks.add_normal_deck_with_name(args.deck_name)
            collection.save()
        print("\nSuccess")
    else:
        print("Aborting...")
    exit()
