import json

from hanky.report import CardRecord, LoadReport


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
