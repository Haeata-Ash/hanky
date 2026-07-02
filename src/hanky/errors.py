class HankyError(Exception):
    """Base class for errors Hanky raises for expected, user-facing conditions."""


class CollectionInUseError(HankyError):
    """Raised when another process holds a handle to the anki collection."""
