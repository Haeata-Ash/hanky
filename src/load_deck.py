from anki.collection import Collection
from Crypto.Hash import SHA256
import pandas

from src.LanguageModel import (
    SOURCE_LANG,
    TARGET_LANG,
    TARGET_SPEECH,
    conjugation_model,
    get_language_model,
)
from src.NoteBuilder import NoteBuilder
from src.text_to_speech import generate_neural_speech


def load_lang_deck(in_csv: str, collection: Collection, deck_name: str, voice: str):
    deck = collection.decks.add_normal_deck_with_name(deck_name)
    collection.save()
    lang_model = get_language_model(collection)
    df = pandas.read_excel(in_csv)
    last_card_was_added = True
    for index, row in df.iterrows():
        if TARGET_LANG not in row:
            raise Exception(
                f"Invalid row in csv: {index}:{row}\nExpected field '{TARGET_LANG}' at column {0}"
            )
        if SOURCE_LANG not in row:
            raise Exception(
                f"Invalid row in csv: {index}:{row}\nExpected field '{SOURCE_LANG}' at column {1}"
            )

        search = collection.find_cards(f'{SOURCE_LANG}:"{row[SOURCE_LANG]}"')
        search = [collection.get_card(c) for c in search]
        existing_in_deck = []
        for card in search:
            if card.did == deck.id:
                existing_in_deck.append(card)
        if len(existing_in_deck) >= 1:
            last_card_was_added = False
            print(
                f"Skipping: {row[SOURCE_LANG]}, card with matching target lang already exists"
            )
        else:
            if not last_card_was_added:
                check = input(
                    f"Are you sure you want '{row[SOURCE_LANG]}' to be added (y/n):\n"
                )
                if check != "y":
                    continue
            last_card_was_added = True
            print(f"Adding new note: {row[SOURCE_LANG]}")
            nbuilder = NoteBuilder(SOURCE_LANG, lang_model, deck_name, collection)
            nbuilder.set_field(TARGET_LANG, row[TARGET_LANG].replace(",", "<br>"))
            nbuilder.set_field(SOURCE_LANG, row[SOURCE_LANG])

            audio_stream = generate_neural_speech(row[TARGET_LANG], voice)
            fname = collection.media.write_data(
                SHA256.new(row[TARGET_LANG].encode()).hexdigest() + ".mp3",
                audio_stream.read(),
            )
            nbuilder.set_sound_field(TARGET_SPEECH, fname)
            nbuilder.make_note(deck.id)

    collection.save()


def load_conj_deck(in_csv: str, collection: Collection, deck_name: str, voice: str):
    deck = collection.decks.add_normal_deck_with_name(deck_name)
    collection.save()
    conj_model = conjugation_model(collection)
    df = pandas.read_excel(in_csv)
    last_card_was_added = True
    csv_to_delete = []
    for index, row in df.iterrows():
        if TARGET_LANG not in row:
            raise Exception(
                f"Invalid row in csv: {index}:{row}\nExpected field '{TARGET_LANG}' at column {0}"
            )
        if SOURCE_LANG not in row:
            raise Exception(
                f"Invalid row in csv: {index}:{row}\nExpected field '{SOURCE_LANG}' at column {1}"
            )

        search = collection.find_cards(f'{SOURCE_LANG}:"{row[SOURCE_LANG]}"')
        search = [collection.get_card(c) for c in search]
        existing_in_deck = []
        for card in search:
            if card.did == deck.id:
                existing_in_deck.append(card)
        if len(existing_in_deck) >= 1:
            last_card_was_added = False
            print(
                f"Skipping: {row[SOURCE_LANG]}, card with matching target lang already exists"
            )
        else:
            if not last_card_was_added:
                check = input(
                    f"\nNew Card: What would you like to do with '{row[SOURCE_LANG]}'?\n\n(a): Add the card and the cards immediately afterwards.\n(s): Skip the card.\n(d): Delete the card from csv (d).\n\n(a/s/d): "
                )
                if check == "a":
                    pass
                elif check == "d":
                    csv_to_delete.append(index)
                    continue
                else:
                    continue

            last_card_was_added = True
            print(f"Adding new note: {row[TARGET_LANG]}")
            nbuilder = NoteBuilder(SOURCE_LANG, conj_model, deck_name, collection)
            nbuilder.set_field(TARGET_LANG, row[TARGET_LANG].replace(",", "<br>"))
            nbuilder.set_field(SOURCE_LANG, row[SOURCE_LANG])

            audio_stream = generate_neural_speech(row[TARGET_LANG], voice)
            fname = collection.media.write_data(
                SHA256.new(row[TARGET_LANG].encode()).hexdigest() + ".mp3",
                audio_stream.read(),
            )
            nbuilder.set_sound_field(TARGET_SPEECH, fname)
            nbuilder.make_note(deck.id)

    collection.save()

    if len(csv_to_delete):
        df = df.drop(csv_to_delete)

    df.to_excel(in_csv, columns=[SOURCE_LANG, TARGET_LANG], index=False)
