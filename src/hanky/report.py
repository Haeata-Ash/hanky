import pprint
import textwrap
from dataclasses import dataclass, field, replace
from typing import Any, List, Literal, Optional

CardStatus = Literal["added", "skipped", "failed"]


@dataclass(frozen=True)
class CardRecord:
    """A single card processed during a load operation.

    Attributes:
        card: the card data.
        status: one of "added", "skipped" or "failed".
        detail: a human readable description of what went wrong. Only set
            when ``status`` is "failed".
        source: where the card came from, if known.
    """

    card: Any
    status: CardStatus
    detail: Optional[str] = None
    source: Optional[str] = None


@dataclass(frozen=True)
class LoadReport:
    """The outcome of a load operation.

    Attributes:
        added: number of cards added to the collection.
        skipped: number of cards skipped because they were duplicates.
        records: the individual cards that were processed. Failed cards are
            always recorded; added/skipped cards only when verbose reporting
            was requested, since keeping every card's data around is wasted
            work otherwise.
    """

    added: int = 0
    skipped: int = 0
    records: List[CardRecord] = field(default_factory=list)

    @property
    def errors(self) -> List[CardRecord]:
        """The cards that could not be added, with their reasons."""
        return [r for r in self.records if r.status == "failed"]

    @property
    def failed(self) -> int:
        """Number of cards that errored."""
        return len(self.errors)

    @property
    def total(self) -> int:
        """Total number of cards seen"""
        return self.added + self.skipped + self.failed

    def with_source(self, source: str) -> "LoadReport":
        """Return a copy with ``source`` stamped onto any records missing one.

        Lets a file based loader attribute in-memory records to the file they
        came from without the lower level import_from_source needing to know paths.
        """
        return LoadReport(
            self.added,
            self.skipped,
            [replace(r, source=r.source or source) for r in self.records],
        )

    def __add__(self, other: "LoadReport") -> "LoadReport":
        """Aggregates LoadReports"""
        if not isinstance(other, LoadReport):
            return NotImplemented
        return LoadReport(
            self.added + other.added,
            self.skipped + other.skipped,
            self.records + other.records,
        )


def _format_card(card: Any) -> str:
    """Pretty print a card dict, indented as a block under its label line."""
    return textwrap.indent(pprint.pformat(card, sort_dicts=False), "    ")


def print_report(report: LoadReport, verbose: bool = False) -> None:
    """Print a human readable summary of a load operation to stdout.

    Failed cards are always listed with their error. When ``verbose`` is
    set, every card (added, skipped or failed) is also pretty printed.
    """
    print(
        f"Added {report.added}, skipped {report.skipped}, "
        f"failed {report.failed} (of {report.total} cards)."
    )
    for record in report.records:
        if record.status != "failed" and not verbose:
            continue
        where = f" {record.source}" if record.source else ""
        detail = f": {record.detail}" if record.detail else ""
        print(f"  [{record.status}]{where}{detail}")
        if verbose:
            print(_format_card(record.card))
