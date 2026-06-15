import hashlib
from pathlib import Path
from uuid import uuid4


class CardMedia:
    """Media that should be added to the anki database at the same time as a card.

    It exposes a temporary reference which can be used as a stand in for the real one
    eventually created by anki. Any usages of the temporary reference in a cards fields
    will be replaced with the real one when it is added to the database.
    """

    def __init__(self, data, ext: str) -> None:
        self.data = data
        self._ext = ext
        self._ref = None
        self._temp_ref_uuid = f"{uuid4().hex}{ext}"
        self._media_ref = self._make_anki_ref()
        self.desired_name = self._make_desired_media_name()

    @classmethod
    def from_file(cls, filename: str):
        fname = Path(filename).expanduser()
        with open(fname.as_posix(), "rb") as f:
            return cls(f.read(), fname.suffix)

    @property
    def media_ref(self) -> str:
        """The reference to be used in the card. The format differs based on the media
        type (aka the extension)."""
        return self._media_ref

    def _make_anki_ref(self) -> str:
        if self._is_audio_ext():
            return self._make_anki_sound_ref()
        else:
            raise ValueError(f"{self._ext} is currently not a supported media type.")

    def _is_audio_ext(self):
        """Check if the extension is an audio extension"""
        AUDIO_EXT = set([".mp3", ".oga", ".opus", ".wav", ".weba", ".aac"])

        if self._ext in AUDIO_EXT:
            return True

        return False

    def _make_anki_sound_ref(self) -> str:
        return f"[sound:{self._ext}]"

    def _make_desired_media_name(self):
        m = hashlib.sha256()
        m.update(self.data)
        return m.hexdigest() + self._ext

    def replace_temp_refs(self, actual_name: str, card: dict[str, str]):
        """Replace any occurences of the temporary media reference in a card
        with the actual name.

        Params:
            actual_name: The actual media name returned by anki when it was added to
                the collection.
            card: the dictionary representing the anki card
        """
        for field in card:
            card[field] = card[field].replace(self._temp_ref_uuid, actual_name)
