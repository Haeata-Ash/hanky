from pathlib import Path

import pytest


def _backup_files(folder) -> list[Path]:
    return list(Path(folder).glob("*.colpkg"))


def test_backup_collection_writes_a_backup_file(app):
    col = app._open_collection()

    app.backup_collection(col, app.config.BACKUP_FOLDER)

    assert len(_backup_files(app.config.BACKUP_FOLDER)) == 1


def test_backup_collection_writes_to_the_given_folder(app, tmp_path):
    col = app._open_collection()
    backup_folder = tmp_path / "my_backups"

    app.backup_collection(col, str(backup_folder))

    assert len(_backup_files(backup_folder)) == 1
    # nothing leaks into the configured default folder
    assert _backup_files(app.config.BACKUP_FOLDER) == []


def test_backup_collection_creates_the_folder_if_missing(app, tmp_path):
    col = app._open_collection()
    backup_folder = tmp_path / "does" / "not" / "exist"
    assert not backup_folder.exists()

    app.backup_collection(col, str(backup_folder))

    assert backup_folder.is_dir()
    assert len(_backup_files(backup_folder)) == 1


def test_backup_collection_raises_when_backup_fails(app, monkeypatch):
    col = app._open_collection()
    monkeypatch.setattr(col, "create_backup", lambda **kwargs: False)

    with pytest.raises(RuntimeError):
        app.backup_collection(col, app.config.BACKUP_FOLDER)
