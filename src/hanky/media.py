import hashlib
from pathlib import Path


class CardMedia:
    """Media that should be added to the anki database at the same time as a card.

    The reference it exposes is the sha256 of the media's content (bytes). It **should**
    be unique so **should** be the name anki will store the media under. Use :meth:`replace_refs`
    to sanity check the case where anki uses a different name.
    """

    def __init__(self, data: bytes, ext: str) -> None:
        self.data = data
        self._ext = ext
        self.desired_name = self._make_desired_media_name()
        self._media_ref = self._make_anki_ref()

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
        return f"[sound:{self.desired_name}]"

    def _make_desired_media_name(self) -> str:
        m = hashlib.sha256()
        m.update(self.data)
        return m.hexdigest() + self._ext

    def replace_refs(self, actual_name: str, card: dict[str, str]) -> None:
        """Point any references to this media in a card at the name anki
        actually stored it under.

        Normally does nothing since the desired name is a hash of the media's
        content, but it is possible that two cards will try to add the same media
        file resulting in the same hash.

        Params:
            actual_name: The actual media name returned by anki when it was added to
                the collection.
            card: the dictionary representing the anki card
        """
        if actual_name == self.desired_name:
            return
        for field in card:
            card[field] = card[field].replace(self.desired_name, actual_name)
