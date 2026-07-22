class HankyError(Exception):
    """Base class for errors Hanky raises for expected, user-facing conditions."""


class ConfigError(HankyError):
    """Raised when hanky configuration cannot be loaded or is invalid."""


class CollectionInUseError(HankyError):
    """Raised when another process holds a handle to the anki collection."""


class CollectionNotFoundError(HankyError):
    """Raised when the configured anki collection path is missing or not a file."""


class ModelNotFoundError(HankyError):
    """Raised when the requested anki model does not exist in the collection."""


class UnsupportedFileTypeError(HankyError):
    """Raised when no loader is registered for a file's extension."""
