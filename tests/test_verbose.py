from hanky.report import CardRecord, LoadReport, print_report


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


def test_print_report_prints_added_and_skipped_cards_when_verbose(capsys):
    report = LoadReport(
        added=1,
        skipped=1,
        records=[
            CardRecord(card={"Front": "chien", "Back": "dog"}, status="added"),
            CardRecord(card={"Front": "chat", "Back": "cat"}, status="skipped"),
        ],
    )

    print_report(report, verbose=True)

    out = capsys.readouterr().out
    assert "[added]" in out
    assert "[skipped]" in out
    assert "{'Front': 'chien', 'Back': 'dog'}" in out
    assert "{'Front': 'chat', 'Back': 'cat'}" in out


def test_print_report_includes_card_dicts_alongside_errors_when_verbose(capsys):
    report = LoadReport(
        records=[
            CardRecord(
                card={"Front": "chien", "Back": "dog"}, status="failed", detail="boom"
            )
        ]
    )

    print_report(report, verbose=True)

    out = capsys.readouterr().out
    assert "boom" in out
    assert "{'Front': 'chien', 'Back': 'dog'}" in out


def test_print_report_pretty_prints_a_large_card_across_multiple_lines(capsys):
    big_card = {
        "Front": "bonjour",
        "Back": "hello",
        "Example": "a" * 100,
    }
    report = LoadReport(added=1, records=[CardRecord(card=big_card, status="added")])

    print_report(report, verbose=True)

    lines = capsys.readouterr().out.splitlines()
    card_lines = [line for line in lines if line.startswith("    ")]

    assert len(card_lines) > 1
    for line in card_lines:
        assert line.startswith("    ")


def test_print_report_omits_card_details_by_default(capsys):
    report = LoadReport(
        added=1,
        records=[
            CardRecord(card={"Front": "chien", "Back": "dog"}, status="added"),
            CardRecord(card={"Front": "x"}, status="failed", detail="boom"),
        ],
    )

    print_report(report)

    out = capsys.readouterr().out
    assert "boom" in out
    assert "chien" not in out
