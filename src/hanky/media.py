from pathlib import Path


def is_audio_ext(filename: str) -> bool:
    """Check if a filename has an audi extension"""
    AUDIO_EXT = set([".mp3", ".oga", ".opus", ".wav", ".weba", ".aac"])

    if Path(filename).suffix in AUDIO_EXT:
        return True

    return False


def make_anki_sound_ref(media_ref: str) -> str:
    return f"[sound:{media_ref}]"
