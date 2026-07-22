from pathlib import Path
from typing import Any
from anki.collection import Collection
from anki.notes import NoteFieldsCheckResult


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


def add_card(
    col: Collection,
    deck_name: str,
    model_name: str,
    allow_duplicates=False,
    **fields,
) -> bool:
    """Adds a card of a given model type to a deck.

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

    for k, v in fields.items():
        new_card[k] = str(v).strip()

    # use anki builtin duplicate detection to check for duplicates
    if not allow_duplicates:
        card_state = new_card.duplicate_or_empty()
        if card_state == NoteFieldsCheckResult.DUPLICATE:
            return False

    col.add_note(new_card, deck_id)
    return True


def add_deck(col: Collection, deck_name: str):
    """Adds a deck to anki. If the deck already exists nothing will happen

    Args:
        col: The anki collection to add the deck to
        deck_name: the full name of the deck to be added
    """
    col.decks.id(deck_name)
