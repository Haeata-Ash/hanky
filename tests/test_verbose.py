from hanky.report import CardRecord


def test_verbose_records_added_cards_on_the_report(app):
    report = app.import_from_source(
        [{"Front": "chien", "Back": "dog"}], "French", verbose=True
    )

    assert report.records == [
        CardRecord(card={"Front": "chien", "Back": "dog"}, status="added")
    ]


def test_verbose_records_skipped_cards_on_the_report(app):
    source = [
        {"Front": "bonjour", "Back": "hello"},
        {"Front": "bonjour", "Back": "hello"},
    ]

    report = app.import_from_source(source, "French", verbose=True)

    assert [r.status for r in report.records] == ["added", "skipped"]


def test_non_verbose_does_not_record_added_or_skipped_cards(app):
    report = app.import_from_source([{"Front": "chien", "Back": "dog"}], "French")

    assert report.records == []


def test_failed_cards_are_recorded_regardless_of_verbose(app):
    report = app.import_from_source([{"Front": "only the front"}], "French")

    assert [r.status for r in report.records] == ["failed"]


def test_import_from_source_never_prints(app, capsys):
    app.import_from_source([{"Front": "chien", "Back": "dog"}], "French", verbose=True)

    assert capsys.readouterr().out == ""
