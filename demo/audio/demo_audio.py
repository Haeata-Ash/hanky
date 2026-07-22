"""Example hanky script which utilizes aws polly (text to speech service) to
generate foreign langauge audio for anki flash cards."""

from typing import IO
from hanky import HankyPipeline, CardMedia
import boto3
import pandas

# constants which represent aws polly voices
# See https://docs.aws.amazon.com/polly/latest/dg/available-voices.html
GERMAN = "Vicki"
FRENCH = "Lea"


def generate_neural_speech(
    utf_8_str: str,
    voice: str,
):
    """Generate speech (audio) from text using aws polly. Requires a free aws account
    and boto credentials to be configured on this machine.

    AWS Polly: https://aws.amazon.com/polly/pricing/
    Boto3 Credentials: https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html
    """
    client = boto3.client("polly")
    res = client.synthesize_speech(
        Engine="neural", OutputFormat="mp3", Text=utf_8_str, VoiceId=voice
    )

    return res["AudioStream"].read()


# instantiate the hanky app, creating cards with the "lang-vocab" model
hanky = HankyPipeline("lang-vocab")


# define our own excel card loader using the pandas library
def excel_loader(f_obj: IO):
    """Load cards fields and values from an excel file.

    Args:
        f_obj: file object to read from
    Yields:
        dictionary of fields mapped to their values.
    """
    df = pandas.read_excel(f_obj)
    for _, row in df.iterrows():
        yield row.to_dict()


# register the loader against ".xlsx" extension
hanky.register_loader(".xlsx", excel_loader, is_text=False)


# 1. Register the 'lang_model' function as a card processor on the pipeline
#
# 2. Define the cml arguments neccessary to be passed to hanky. 'lang' is used to
# choose the language, i.e '--args lang=french'
#
# 3. Define the fields that this card processor depends on. In this case 'native-lang'
# and 'target-lang' fields are assumed to be in the card. They could already be present
# in the file or set by a previous card processor
@hanky.card_processor(
    expected_args=["lang"], required_fields=["native-lang", "target-lang"]
)
def lang_model(card: dict, lang):
    """Generate the speech from the 'target-lang' field, add it as anki media then
    referenece it in 'target-lang-speech' field.
    """

    # generate the speech for a particular language based on cml argument 'lang'
    speech = None
    if lang.upper() == "FRENCH":
        speech = generate_neural_speech(card["target-lang"], FRENCH)
    elif lang.upper() == "GERMAN":
        speech = generate_neural_speech(card["target-lang"], GERMAN)
    else:
        raise Exception("Unknown language.")

    # put the reference to that media inside a field in the lang-vocab model
    # in this case there is a specific field, 'target-lang-speech'
    speech_media = CardMedia(speech, ".mp3")

    card["target-lang-speech"] = speech_media.media_ref
    return card, speech_media


# run the hanky cml application by running this python file
# For example, to load a deck of cards from file 'foods.xlsx'
# python3 demo_audio.py pipe foods.xlsx --args lang=french
if __name__ == "__main__":
    hanky.run()
