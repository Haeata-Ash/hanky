from unittest.mock import MagicMock, patch

import pytest

from hanky.config import Config, _get_default_anki_db_path


@pytest.fixture(autouse=True, params=["Linux", "Darwin"])
def mock_get_system(request):
    with patch("hanky.config._get_system", MagicMock(return_value=request.param)):
        yield


def test_update_changes_only_given_fields():
    cfg = Config(ANKI_DB_PATH="/a", DO_SAFETY_CHECK=True, ALLOW_DUPLICATES=False)

    updated = cfg.update(DO_SAFETY_CHECK=False)

    assert updated.DO_SAFETY_CHECK is False
    assert updated.ANKI_DB_PATH == "/a"
    assert updated.ALLOW_DUPLICATES is False


def test_from_toml_reads_all_fields(tmp_path):
    toml = tmp_path / "hanky.toml"
    toml.write_text(
        'ANKI_DB_PATH = "/data/collection.anki2"\n'
        "DO_SAFETY_CHECK = false\n"
        "ALLOW_DUPLICATES = true\n"
    )

    cfg = Config.from_toml(str(toml))

    assert cfg == Config(
        ANKI_DB_PATH="/data/collection.anki2",
        DO_SAFETY_CHECK=False,
        ALLOW_DUPLICATES=True,
    )


def test_from_toml_partial_file_keeps_defaults_for_missing_fields(tmp_path):
    toml = tmp_path / "hanky.toml"
    toml.write_text("ALLOW_DUPLICATES = true\n")

    cfg = Config.from_toml(str(toml))

    assert cfg.ALLOW_DUPLICATES is True
    assert cfg.DO_SAFETY_CHECK is True


def test_from_toml_empty_file_equals_default_config(tmp_path):
    toml = tmp_path / "hanky.toml"
    toml.write_text("")

    assert Config.from_toml(str(toml)) == Config()


def test_defaults_when_nothing_supplied():
    cfg = Config()

    assert cfg.DO_SAFETY_CHECK is True
    assert cfg.ALLOW_DUPLICATES is False


def test_explicit_db_path_overrides_platform_default():
    cfg = Config(ANKI_DB_PATH="/custom/collection.anki2")

    assert cfg.ANKI_DB_PATH == "/custom/collection.anki2"


def test_explicit_flags_override_defaults():
    cfg = Config(DO_SAFETY_CHECK=False, ALLOW_DUPLICATES=True)

    assert cfg.DO_SAFETY_CHECK is False
    assert cfg.ALLOW_DUPLICATES is True


def test_default_db_path_unsupported_platform_raises():
    with pytest.raises(ValueError):
        _get_default_anki_db_path("Windows")


def test_explicit_backup_folder_overrides_default():
    cfg = Config(BACKUP_FOLDER="/custom/backups")

    assert cfg.BACKUP_FOLDER == "/custom/backups"
