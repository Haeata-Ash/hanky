from os import path
import yaml
from anki.collection import Collection
from src.cml import make_parser
from src.load_deck import load_conj_deck, load_lang_deck
from src.text_to_speech import FrenchNeuralVoices, GermanNeuralVoices


if __name__ == "__main__":
    parser = make_parser()
    args = parser.parse_args()

    conf = {}
    with open(args.config, "r") as f:
        conf = yaml.safe_load(f)
        conf["database"] = path.expanduser(conf["database"])

    collection = Collection(conf["database"])
    cont = input(
        f"Loading deck '{args.deck_name}'. This will update any deck with the same name. Continue [y/n]: "
    )
    if cont == "y":
        if args.infile:
            lang = args.lang
            if lang == "German":
                voice = GermanNeuralVoices.VICKI
            elif lang == "French":
                voice = FrenchNeuralVoices.LEA
            if args.model == "lang-understand":
                load_lang_deck(args.infile, collection, args.deck_name, voice)
            elif args.model == "lang-recall":
                load_conj_deck(args.infile, collection, args.deck_name, voice)

        else:
            collection.decks.add_normal_deck_with_name(args.deck_name)
            collection.save()
        print("\nSuccess")
    else:
        print("Aborting...")
    exit()
