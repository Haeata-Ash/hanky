from enum import Enum
from typing import Literal
import boto3


class FrenchNeuralVoices(Enum):
    REMI = "Remi"
    LEA = "Lea"


class GermanNeuralVoices(Enum):
    VICKI = "Vicki"


def generate_neural_speech(
    utf_8_str: str,
    voice: Enum = GermanNeuralVoices.VICKI,
):
    client = boto3.client("polly")
    res = client.synthesize_speech(
        Engine="neural", OutputFormat="mp3", Text=utf_8_str, VoiceId=voice.value
    )

    return res["AudioStream"]
