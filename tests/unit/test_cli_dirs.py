import sys

from regression_firewall.capture.cli import capture_cli_probes
from regression_firewall.config.schema import (
    Config,
    CliProbeConfig,
    CliSurfaceConfig,
    DirWatchConfig,
    IgnoreConfig,
    NormalizationConfig,
)
from regression_firewall.diff.cli import diff_cli
from regression_firewall.diff.engine import make_change
from regression_firewall.normalize.engine import Normalizer


def _probe(dirs):
    return CliProbeConfig(
        id="gen", command=[sys.executable, "-c", "print('ok')"], dirs=dirs
    )


def _capture(tmp_path, probe):
    captures, warnings = capture_cli_probes(CliSurfaceConfig(probes=[probe]), tmp_path)
    return captures[0], warnings


def _norm():
    return Normalizer(NormalizationConfig(), IgnoreConfig())


def test_dir_watch_keys_are_stable_posix(tmp_path):
    (tmp_path / "out" / "nested").mkdir(parents=True)
    (tmp_path / "out" / "a.txt").write_text("A")
    (tmp_path / "out" / "nested" / "b.txt").write_text("B")
    cap, warnings = _capture(tmp_path, _probe([DirWatchConfig(path="out")]))
    assert sorted(cap.data["files"]) == ["out/a.txt", "out/nested/b.txt"]
    entry = cap.data["files"]["out/a.txt"]
    assert entry["exists"] is True and entry["sha256"] and entry["size"] == 1
    assert warnings == []


def test_dir_watch_ignore_prunes_subtrees_and_files(tmp_path):
    out = tmp_path / "out"
    (out / "__pycache__").mkdir(parents=True)
    (out / "__pycache__" / "x.pyc").write_text("x")
    (out / "sub").mkdir()
    (out / "sub" / "keep.txt").write_text("k")
    (out / "noise.log").write_text("n")
    cap, _ = _capture(tmp_path, _probe([
        DirWatchConfig(path="out", ignore=["__pycache__", "*.log"]),
    ]))
    assert sorted(cap.data["files"]) == ["out/sub/keep.txt"]


def test_dir_watch_max_files_truncates_with_warning(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    for i in range(5):
        (out / f"f{i}.txt").write_text(str(i))
    cap, warnings = _capture(tmp_path, _probe([
        DirWatchConfig(path="out", max_files=3),
    ]))
    assert len(cap.data["files"]) == 3
    assert any("max_files" in w for w in warnings)


def test_dir_watch_missing_dir_contributes_nothing(tmp_path):
    cap, warnings = _capture(tmp_path, _probe([DirWatchConfig(path="does-not-exist")]))
    assert cap.data["files"] == {}
    assert warnings == []


def test_dir_watch_detects_create_modify_delete(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "a.txt").write_text("1")
    probe = _probe([DirWatchConfig(path="out")])

    before, _ = _capture(tmp_path, probe)
    (out / "b.txt").write_text("new")
    (out / "a.txt").write_text("2")
    after, _ = _capture(tmp_path, probe)

    changes = diff_cli(before, after, _norm(), Config(), make_change)
    found = {(c.category, c.path) for c in changes}
    assert ("file_created", "out/b.txt") in found
    assert ("file_modified", "out/a.txt") in found

    (out / "b.txt").unlink()
    after2, _ = _capture(tmp_path, probe)
    changes2 = diff_cli(after, after2, _norm(), Config(), make_change)
    assert ("file_deleted", "out/b.txt") in {(c.category, c.path) for c in changes2}


def test_dir_watch_identical_captures_diff_clean(tmp_path):
    out = tmp_path / "out"
    (out / "x").mkdir(parents=True)
    (out / "x" / "f.txt").write_text("stable")
    probe = _probe([DirWatchConfig(path="out")])
    before, _ = _capture(tmp_path, probe)
    after, _ = _capture(tmp_path, probe)
    assert diff_cli(before, after, _norm(), Config(), make_change) == []
