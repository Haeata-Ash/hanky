from hanki import Hanki
import boto3


GERMAN = "Vicki"
FRENCH = "Lea"
def generate_neural_speech(
    utf_8_str: str,
    voice: str,
):
    client = boto3.client("polly")
    res = client.synthesize_speech(
        Engine="neural", OutputFormat="mp3", Text=utf_8_str, VoiceId=voice
    )

    return res["AudioStream"].read()


hanki = Hanki(anki_database="~/.local/share/Anki2/TestUser/collection.anki2")


@hanki.card_processor(
    "lang-vocab", expected_args=["lang"], expected_fields=["Front", "Back"]
)
def lang_model(card: dict, lang):
    front_speech = None
    back_speech = None
    if lang.upper() == "FRENCH":
        front_speech = generate_neural_speech(card["Front"], FRENCH)
        back_speech = generate_neural_speech(card["Back"], FRENCH)
    elif lang.upper() == "GERMAN":
        front_speech = generate_neural_speech(card["Front"], GERMAN)
        back_speech = generate_neural_speech(card["Back"], GERMAN)
    else:
        raise Exception("Unkown language.")
    
    front_speech_ref = hanki.add_media(front_speech, file_ext=".mp3")
    back_speech_ref = hanki.add_media(back_speech, file_ext=".mp3")

    card["front-speech"] = front_speech_ref
    card["back-speech"] = back_speech_ref
    return card


hanki.run()

# Usage: python3 demo.py load-deck "lang-vocab" ~/french/bodies.csv --args lang=french

# expects there to be a model created in anki named 'lang-vocab' 
# with the following fields: Front, Back, front-speech, back-speech