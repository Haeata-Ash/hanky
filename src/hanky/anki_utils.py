from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Sequence
from anki.collection import Collection
from anki.decks import DeckId
from anki.notes import Note, NoteFieldsCheckResult

from hanky.media import CardMedia


def add_media(
    col: Collection,
    data: Any,
    media_fname: str,
) -> str:
    """Add binary data to the anki collection.

    Args:
        col: The anki collection to add the media to
        data: the binary media data
        media_fname: The filename including the extension

    Returns:
        The media filename after adding it to anki collection
    """
    desired_name = media_fname

    # write media to anki database
    actual_name = col.media.write_data(
        desired_name,
        data,
    )

    return actual_name


def backup_collection(col: Collection, backup_folder: str):
    """Backups the anki collection to a folder

    Args:
        col: The anki collection to backup
        backup_folder: the directory/folder to store the backup in
    """
    folder_path = Path(backup_folder)
    folder_path.mkdir(parents=True, exist_ok=True)
    if not col.create_backup(
        backup_folder=backup_folder,
        force=True,
        wait_for_completion=True,
    ):
        raise RuntimeError("Unable to create backup of anki collection.")


@dataclass
class PreparedCard:
    """A note built and checked against the collection, but not yet added.

    Attributes:
        note: the anki note, with its fields already filled in
        deck_id: the id of the deck the note will be added to
        is_duplicate: whether anki considers this a duplicate of a note
            already in the collection. Always false when duplicates are
            allowed, since no check is made in that case.
    """

    note: Note
    deck_id: DeckId
    is_duplicate: bool


def _write_fields(note: Note, fields: dict) -> None:
    """Write card values onto a note, as the strings anki stores."""
    for k, v in fields.items():
        note[k] = str(v).strip()


def prepare_card(
    col: Collection,
    deck_name: str,
    model_name: str,
    allow_duplicates=False,
    **fields,
) -> PreparedCard:
    """Build a note of a given model type and check whether it can be added,
    without adding it or otherwise touching the collection.

    Args:
        col: The anki collection the card is destined for
        deck_name: the full destination deck name as a seen in anki.
        model_name: the name of the flash card model as seen in anki.
        allow_duplicates: skip the duplicate check entirely
        **fields: the card's field values

    Returns:
        A :class:`PreparedCard`

    Raises:
        ValueError: The deck or model don't exist
        KeyError: The card does not have the required fields for the model
    """
    model = col.models.by_name(model_name)
    if model is None:
        raise ValueError(
            f"Model '{model_name}' does not exist in your anki collection. Ensure it has been added before using it with hanky."
        )
    deck_id = col.decks.id(deck_name, create=False)
    if deck_id is None:
        raise ValueError(
            f"Deck '{deck_name}' does not exist in your anki collection. Ensure it has been created before using it with hanky."
        )

    expected_fields = col.models.field_names(model)
    for k in expected_fields:
        if k not in fields:
            raise KeyError(f"Expected field '{k}' is missing.")

    new_card = col.new_note(model)
    _write_fields(new_card, fields)

    # use anki builtin duplicate detection to check for duplicates
    is_duplicate = False
    if not allow_duplicates:
        is_duplicate = new_card.duplicate_or_empty() == NoteFieldsCheckResult.DUPLICATE

    return PreparedCard(note=new_card, deck_id=deck_id, is_duplicate=is_duplicate)


def commit_card(col: Collection, prepared: PreparedCard, **fields) -> None:
    """Add a prepared note to the collection.

    Args:
        col: The anki collection to add the card to
        prepared: the note to add, from :func:`prepare_card`
        **fields: the card's field values, if they have changed since the
            card was prepared. Media references are settled between preparing
            and committing, so the values written then can be stale.
    """
    if fields:
        _write_fields(prepared.note, fields)
    col.add_note(prepared.note, prepared.deck_id)


def commit_card_with_media(
    col: Collection,
    prepared: PreparedCard,
    card: dict,
    media: Sequence[CardMedia],
) -> None:
    """Write a card's media AND add the card, or leave the collection as it
    was found.

    Anki writes media and adds notes independently, so if we fail to write
    the card to the collection here we go back and remove added media.

    Callers should only reach here once :func:`prepare_card` has said the card is
    addable.

    Args:
        col: The anki collection to add the card and its media to
        prepared: the note to add, from :func:`prepare_card`
        card: the card's field values, updated in place so its media
            references point at the names anki stored the media under
        media: the media to write before adding the card
    """
    introduced: List[str] = []
    try:
        for m in media:
            already_had = col.media.have(m.desired_name)
            actual_fname = add_media(col, m.data, m.desired_name)
            if not already_had or actual_fname != m.desired_name:
                introduced.append(actual_fname)
            m.replace_refs(actual_fname, card)

        commit_card(col, prepared, **card)
    except Exception:
        if introduced:
            col.media.trash_files(introduced)
        raise


def add_card(
    col: Collection,
    deck_name: str,
    model_name: str,
    allow_duplicates=False,
    **fields,
) -> bool:
    """Adds a card of a given model type to a deck.

    A convenience wrapper over :func:`prepare_card` and :func:`commit_card`
    for callers with no side effects to sequence in between the two.

    Args:
        col: The anki collection to add the card to
        deck_name: the full destination deck name as a seen in anki.
        model_name: the name of the flash card model as seen in anki.

    Returns:
        A bool, true if the card was successfully added, false otherwise

    Raises:
        ValueError: The deck or model don't exist
        KeyError: The card does not have the required fields for the model
    """
    prepared = prepare_card(
        col, deck_name, model_name, allow_duplicates=allow_duplicates, **fields
    )
    if prepared.is_duplicate:
        return False

    commit_card(col, prepared)
    return True


def add_deck(col: Collection, deck_name: str):
    """Adds a deck to anki. If the deck already exists nothing will happen

    Args:
        col: The anki collection to add the deck to
        deck_name: the full name of the deck to be added
    """
    col.decks.id(deck_name)
