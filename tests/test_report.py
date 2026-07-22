import json

from hanky.report import CardRecord, LoadReport, print_report


def test_failed_and_total_are_derived_from_the_buckets():
    report = LoadReport(
        added=3,
        skipped=1,
        records=[CardRecord(card={"Front": "x"}, status="failed", detail="boom")],
    )

    assert report.failed == 1
    assert report.total == 5


def test_reports_compose_with_addition():
    a = LoadReport(
        added=1,
        skipped=1,
        records=[CardRecord(card={}, status="failed", detail="a")],
    )
    b = LoadReport(
        added=2,
        skipped=0,
        records=[CardRecord(card={}, status="failed", detail="b")],
    )

    combined = a + b

    assert combined.added == 3
    assert combined.skipped == 1
    assert [e.detail for e in combined.errors] == ["a", "b"]


def test_empty_report_is_an_additive_identity():
    report = LoadReport(
        added=2, records=[CardRecord(card={}, status="failed", detail="x")]
    )

    assert (LoadReport() + report) == report


def test_with_source_stamps_only_records_that_lack_one():
    report = LoadReport(
        records=[
            CardRecord(card={}, status="failed", detail="no source"),
            CardRecord(
                card={}, status="failed", detail="keeps its own", source="other.csv"
            ),
        ]
    )

    stamped = report.with_source("french.csv")

    assert stamped.records[0].source == "french.csv"
    assert stamped.records[1].source == "other.csv"


def test_reports_compose_records_with_addition():
    a = LoadReport(records=[CardRecord(card={"Front": "a"}, status="added")])
    b = LoadReport(records=[CardRecord(card={"Front": "b"}, status="skipped")])

    combined = a + b

    assert [r.card["Front"] for r in combined.records] == ["a", "b"]


def test_errors_filters_records_to_only_failed_ones():
    report = LoadReport(
        records=[
            CardRecord(card={"Front": "a"}, status="added"),
            CardRecord(card={"Front": "b"}, status="skipped"),
            CardRecord(card={"Front": "c"}, status="failed", detail="boom"),
        ]
    )

    assert [e.card["Front"] for e in report.errors] == ["c"]


def test_import_from_file_records_the_file_path_against_errors(app, tmp_path):
    fpath = tmp_path / "french.json"
    # second card is missing the required Back field
    fpath.write_text(
        json.dumps([{"Front": "bonjour", "Back": "hello"}, {"Front": "chat"}])
    )

    report = app.import_from_file(str(fpath))

    assert report.added == 1
    assert report.failed == 1
    assert report.errors[0].source == str(fpath)


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
