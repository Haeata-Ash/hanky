from anki.collection import Collection
from Crypto.Hash import SHA256
import pandas
from LanguageModel import SOURCE_LANG, TARGET_LANG, TARGET_SPEECH, get_language_model
from NoteBuilder import NoteBuilder
from text_to_speech import GermanNeuralVoices, generate_neural_speech


def load_lang_deck(in_csv: str, collection: Collection, deck_name: str):
    deck = collection.decks.add_normal_deck_with_name(deck_name)
    collection.save()
    lang_model = get_language_model(collection)
    df = pandas.read_excel(in_csv)
    for index, row in df.iterrows():
        if TARGET_LANG not in row:
            raise Exception(
                f"Invalid row in csv: {index}:{row}\nExpected field '{TARGET_LANG}' at column {0}"
            )
        if SOURCE_LANG not in row:
            raise Exception(
                f"Invalid row in csv: {index}:{row}\nExpected field '{SOURCE_LANG}' at column {1}"
            )

        sch = collection.find_notes(f'{TARGET_LANG}:"{row[TARGET_LANG]}"')
        if len(sch) >= 1:
            print(
                f"Skipping: {row[TARGET_LANG]}, card with matching target lang already exists"
            )
        else:
            print(f"Adding new note: {row[TARGET_LANG]}")
            nbuilder = NoteBuilder(SOURCE_LANG, lang_model, deck_name, collection)
            nbuilder.set_field(TARGET_LANG, row[TARGET_LANG])
            nbuilder.set_field(SOURCE_LANG, row[SOURCE_LANG])

            audio_stream = generate_neural_speech(row[TARGET_LANG], GermanNeuralVoices.VICKI)
            fname = collection.media.write_data(
                SHA256.new(row[TARGET_LANG].encode()).hexdigest() + ".mp3",
                audio_stream.read(),
            )
            nbuilder.set_sound_field(TARGET_SPEECH, fname)
            nbuilder.make_note(deck.id)

    collection.save()
