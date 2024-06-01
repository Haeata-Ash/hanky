from hanky import Hanky
import boto3

# constants which represent aws polly voices
# See https://docs.aws.amazon.com/polly/latest/dg/available-voices.html
# for more details
GERMAN = "Vicki"
FRENCH = "Lea"


# our function to generate speech using aws polly service
# we use their boto3 sdk for this
# see https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html
# for setup and documentation
def generate_neural_speech(
    utf_8_str: str,
    voice: str,
):
    client = boto3.client("polly")
    res = client.synthesize_speech(
        Engine="neural", OutputFormat="mp3", Text=utf_8_str, VoiceId=voice
    )

    return res["AudioStream"].read()


hanky = Hanky()


# Process each card of type/model 'lang-vocab' with this function
# Expect 'native-lang' and 'target-lang' fields to be present in the
# card data read in from the file
# Expect 'lang' to be provided as a cml argument, i.e '--args lang=french'
@hanky.card_processor(
    "lang-vocab", expected_args=["lang"], card_fields=["native-lang", "target-lang"]
)
def lang_model(card: dict, lang):

    # generate the speech for a particular language
    # based on cml argument 'lang'
    speech = None
    if lang.upper() == "FRENCH":
        speech = generate_neural_speech(card["target-lang"], FRENCH)
    elif lang.upper() == "GERMAN":
        speech = generate_neural_speech(card["target-lang"], GERMAN)
    else:
        raise Exception("Unkown language.")

    # add the mp3 data to anki
    speech_ref = hanky.add_media(speech, file_ext=".mp3")

    # put the reference to that media inside a field in the lang-vocab model
    # in this case there is a specific field, 'target-lang-speech'
    card["target-lang-speech"] = speech_ref
    return card


# run the hanky cml application by running this python file
# For example, to load a deck of cards from file 'foods.csv'
# python3 demo.py load lang-vocab foods.csv --args lang=french
hanky.run()
