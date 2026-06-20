from pathlib import Path

from anki.collection import Collection

from hanky.hanky import Hanky


def _backup_files(folder) -> list[Path]:
    return list(Path(folder).glob("*.colpkg"))


def test_backup_written_on_first_collection_access(app):
    _ = app.col

    backups = _backup_files(app.config.BACKUP_FOLDER)
    assert len(backups) == 1


def test_backup_written_to_configured_folder(tmp_path):
    db_path = tmp_path / "collection.anki2"
    Collection(str(db_path)).close()
    backup_folder = tmp_path / "my_backups"

    app = Hanky(
        ANKI_DB_PATH=str(db_path),
        DO_SAFETY_CHECK=False,
        BACKUP_FOLDER=str(backup_folder),
    )
    try:
        _ = app.col
        assert len(_backup_files(backup_folder)) == 1
        assert _backup_files(tmp_path / "default_backups") == []
    finally:
        if app._col:
            app.col.close()
