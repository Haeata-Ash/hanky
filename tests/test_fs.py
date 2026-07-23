import psutil
import pytest

from hanky.fs import has_handle


class _FakeOpenFile:
    def __init__(self, path):
        self.path = path


class _FakeProcess:
    """Stands in for a psutil.Process: open_files() either returns a list
    of open files or raises the given error."""

    def __init__(self, files=None, error=None):
        self._files = files or []
        self._error = error

    def open_files(self):
        if self._error is not None:
            raise self._error
        return self._files


def _patch_processes(monkeypatch, procs):
    monkeypatch.setattr(psutil, "process_iter", lambda: iter(procs))


def test_has_handle_finds_a_matching_open_file(tmp_path, monkeypatch):
    target = tmp_path / "collection.anki2"
    target.touch()

    _patch_processes(
        monkeypatch,
        [_FakeProcess(files=[_FakeOpenFile(str(target))])],
    )

    assert has_handle(str(target)) is True


def test_has_handle_returns_false_when_no_process_holds_it(tmp_path, monkeypatch):
    target = tmp_path / "collection.anki2"
    target.touch()

    _patch_processes(
        monkeypatch,
        [_FakeProcess(files=[_FakeOpenFile("/some/other/file")])],
    )

    assert has_handle(str(target)) is False


def test_has_handle_ignores_processes_that_deny_access_if_others_succeed(
    tmp_path, monkeypatch
):
    target = tmp_path / "collection.anki2"
    target.touch()

    _patch_processes(
        monkeypatch,
        [
            _FakeProcess(error=psutil.AccessDenied(pid=1)),
            _FakeProcess(files=[_FakeOpenFile("/some/other/file")]),
        ],
    )

    assert has_handle(str(target)) is False


def test_has_handle_raises_when_no_process_can_be_inspected(tmp_path, monkeypatch):
    target = tmp_path / "collection.anki2"
    target.touch()

    _patch_processes(
        monkeypatch,
        [
            _FakeProcess(error=psutil.AccessDenied(pid=1)),
            _FakeProcess(error=psutil.NoSuchProcess(pid=2)),
        ],
    )

    with pytest.raises(RuntimeError, match="could not be determined"):
        has_handle(str(target))


def test_has_handle_raises_when_there_are_no_processes_at_all(tmp_path, monkeypatch):
    target = tmp_path / "collection.anki2"
    target.touch()

    _patch_processes(monkeypatch, [])

    with pytest.raises(RuntimeError, match="could not be determined"):
        has_handle(str(target))
