from pathlib import Path


def _write_csv(path: Path, rows):
    """Write a Basic-model CSV (Front,Back header) at path, creating parents."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["Front,Back"]
    lines += [f"{front},{back}" for front, back in rows]
    path.write_text("\n".join(lines) + "\n", newline="")


def test_load_dir_builds_deck_names_from_the_directory_hierarchy(app, tmp_path):
    root = tmp_path / "french"
    _write_csv(root / "animals.csv", [("chat", "cat")])
    _write_csv(root / "grammar" / "passe_compose.csv", [("mange", "ate")])

    report = app.load_dir("Basic", str(root), "*.csv", recursive=True)

    col = app._open_collection()
    assert col.decks.id("french::animals", create=False) is not None
    assert col.decks.id("french::grammar::passe_compose", create=False) is not None
    assert report.added == 2
    assert col.note_count() == 2


def test_load_dir_recursive_flag_and_glob_control_which_files_load(app, tmp_path):
    root = tmp_path / "french"
    _write_csv(root / "top.csv", [("bonjour", "hello")])
    _write_csv(root / "sub" / "deep.csv", [("merci", "thanks")])

    (root / "notes.txt").write_text("not a card file\n")

    shallow = app.load_dir("Basic", str(root), "*.csv", recursive=False)

    col = app._open_collection()
    assert shallow.added == 1
    assert col.decks.id("french::top", create=False) is not None
    assert col.decks.id("french::sub::deep", create=False) is None
    assert col.note_count() == 1

    # the same call with recursive=True descends into the subdirectory
    deep = app.load_dir("Basic", str(root), "*.csv", recursive=True)

    assert deep.added == 1
    assert deep.skipped == 1
    assert col.decks.id("french::sub::deep", create=False) is not None
    assert col.note_count() == 2
