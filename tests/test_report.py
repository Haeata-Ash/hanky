import json

from hanky.report import CardError, LoadReport


def test_failed_and_total_are_derived_from_the_buckets():
    report = LoadReport(
        added=3,
        skipped=1,
        errors=[CardError(card={"Front": "x"}, error="boom")],
    )

    assert report.failed == 1
    assert report.total == 5


def test_reports_compose_with_addition():
    a = LoadReport(added=1, skipped=1, errors=[CardError(card={}, error="a")])
    b = LoadReport(added=2, skipped=0, errors=[CardError(card={}, error="b")])

    combined = a + b

    assert combined.added == 3
    assert combined.skipped == 1
    assert [e.error for e in combined.errors] == ["a", "b"]


def test_empty_report_is_an_additive_identity():
    report = LoadReport(added=2, errors=[CardError(card={}, error="x")])

    assert (LoadReport() + report) == report


def test_with_source_stamps_only_errors_that_lack_one():
    report = LoadReport(
        errors=[
            CardError(card={}, error="no source"),
            CardError(card={}, error="keeps its own", source="other.csv"),
        ]
    )

    stamped = report.with_source("french.csv")

    assert stamped.errors[0].source == "french.csv"
    assert stamped.errors[1].source == "other.csv"


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
