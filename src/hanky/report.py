from dataclasses import dataclass, field, replace
from typing import Any, List, Optional


@dataclass(frozen=True)
class CardError:
    """A single card that could not be added during a load operation.

    Attributes:
        card: the card data
        error: a human readable description of what went wrong.
        source: where the card came from, if known
    """

    card: Any
    error: str
    source: Optional[str] = None


@dataclass(frozen=True)
class LoadReport:
    """The outcome of a load operation.

    Attributes:
        added: number of cards added to the collection.
        skipped: number of cards skipped because they were duplicates.
        errors: the cards that could not be added, with their reasons.
    """

    added: int = 0
    skipped: int = 0
    errors: List[CardError] = field(default_factory=list)

    @property
    def failed(self) -> int:
        """Number of cards that errored."""
        return len(self.errors)

    @property
    def total(self) -> int:
        """Total number of cards seen"""
        return self.added + self.skipped + self.failed

    def with_source(self, source: str) -> "LoadReport":
        """Return a copy with ``source`` stamped onto any errors missing one.

        Lets a file based loader attribute in-memory errors to the file they
        came from without the lower level import_from_source needing to know paths.
        """
        return LoadReport(
            self.added,
            self.skipped,
            [replace(e, source=e.source or source) for e in self.errors],
        )

    def __add__(self, other: "LoadReport") -> "LoadReport":
        """Aggregates LoadReports"""
        if not isinstance(other, LoadReport):
            return NotImplemented
        return LoadReport(
            self.added + other.added,
            self.skipped + other.skipped,
            self.errors + other.errors,
        )
