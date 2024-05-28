from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Literal, Optional

import boto3


@dataclass
class Language:
    def __init__(self, name: str, lang_code: str, standard="ISO639-3"):
        self.name = name
        self.code = lang_code
        self.standard = standard


class Voice(ABC):
    def __init__(self, languages: List[Language], voice_id: str):
        self._voice_id = voice_id
        self._langs = languages

    @property
    def voice_id(self) -> str:
        """Return the service  providers (i.e AWS Polly) identifier for this voice"""
        return self._voice_id

    @property
    def languages(self) -> List[Language]:
        """Return the list of available langauges for this voice"""
        return self._langs

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the human readable name for the voice. May be different to the voice id"""
        ...

    @abstractmethod
    def generate_speech(self, text: str, **kwargs): ...


class AWSPollyVoice(Voice):
    def __init__(
        self,
        voice_id: str,
        languages: List[Language],
        name: str,
        gender: str,
        engines: List[str],
        default_lang: Optional[Language] = None,
    ):
        self._gender = gender
        self._name = name
        self._engines = engines

        if not default_lang and len(languages) > 1:
            raise ValueError(
                "Default language must be given if the voice is multilingual."
            )
        self._default_lang = default_lang if default_lang else languages[0]

        super().__init__(languages, voice_id)

    def from_boto_voice_response(boto_response: dict) -> AWSPollyVoice:
        """Create a AWSPollyVoice from the response of the boto3 polly clients describe_voices method.
        See https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/polly/client/describe_voices.html
        for more info"""
        pass

    @property
    def default_lang(self) -> Language:
        return self._default_lang

    @property
    def engines(self) -> List[str]:
        """Return a list of available engines for this voice. An engine can be one of
        'standard'|'neural'|'long-form'
        """
        return self._engines

    def generate_speech(
        self,
        text: str,
        output_format: Literal["json", "mp3", "ogg_vorbis", "pcm"],
        lang_code: Optional[str] = None,
    ):
        polly = boto3.client("polly")
        res = polly.synthesize_speech(
            OutputFormat=output_format,
            Text=text,
            VoiceId=self.voice_id,
            LanguageCode=lang_code if lang_code else self.default_lang,
        )

        return res["AudioStream"].read()
