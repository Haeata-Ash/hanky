from pathlib import Path

from hanky.cli import make_parser
from hanky.hanky import _run_app


def _backup_files(folder) -> list[Path]:
    return list(Path(folder).glob("*.colpkg"))


def _write_csv(path: Path, rows):
    """Write a Basic-model CSV (Front,Back header) at path, creating parents."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["Front,Back"]
    lines += [f"{front},{back}" for front, back in rows]
    path.write_text("\n".join(lines) + "\n", newline="")


def test_pipe_takes_a_positional_file_and_flags():
    ns = make_parser().parse_args(
        ["pipe", "words.csv", "--model", "Basic", "--into", "english::vocab"]
    )
    assert ns.operation == "pipe"
    assert ns.file == "words.csv"
    assert ns.model == "Basic"
    assert ns.deck == "english::vocab"


def test_pipe_into_is_optional():
    ns = make_parser().parse_args(["pipe", "words.csv", "--model", "Basic"])
    assert ns.deck is None


def test_pipe_model_override_is_optional():
    ns = make_parser().parse_args(["pipe", "words.csv"])
    assert ns.model is None


def test_pipe_dir_takes_positional_dir_and_pattern():
    ns = make_parser().parse_args(
        ["pipe-dir", "./french", "*.csv", "--model", "Basic", "-r"]
    )
    assert ns.operation == "pipe-dir"
    assert ns.dir == "./french"
    assert ns.pattern == "*.csv"
    assert ns.model == "Basic"
    assert ns.is_rec is True


def test_pipe_dir_model_override_is_optional():
    ns = make_parser().parse_args(["pipe-dir", "./french", "*.csv"])
    assert ns.model is None


def test_pipe_dry_run_flag_parses():
    ns = make_parser().parse_args(["pipe", "words.csv", "--dry-run"])
    assert ns.dry_run is True


def test_pipe_dir_dry_run_flag_parses():
    ns = make_parser().parse_args(["pipe-dir", "./french", "*.csv", "--dry-run"])
    assert ns.dry_run is True


def test_pipe_defaults_the_deck_to_the_filename(app, tmp_path):
    fpath = tmp_path / "French.csv"
    _write_csv(fpath, [("chien", "dog")])

    _run_app(app, ["pipe", str(fpath), "--model", "Basic"])

    assert app._open_collection().decks.id("French", create=False) is not None


def test_pipe_dry_run_skips_backup_and_leaves_the_collection_untouched(app, tmp_path):
    fpath = tmp_path / "French.csv"
    _write_csv(fpath, [("chien", "dog")])

    _run_app(app, ["pipe", str(fpath), "--model", "Basic", "--dry-run"])

    assert app._open_collection().decks.id("French", create=False) is None
    assert app._open_collection().note_count() == 0
    assert _backup_files(app.config.BACKUP_FOLDER) == []
