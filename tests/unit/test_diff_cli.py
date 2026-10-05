from _helpers import change_of

from regression_firewall.diff.cli import diff_cli
from regression_firewall.diff.engine import make_change
from regression_firewall.models.snapshot import ProbeCapture


def capture(probe_id, data, ok=True, error=None):
    return ProbeCapture(probe_id=probe_id, target=probe_id, ok=ok, error=error, data=data)


def cli_data(exit_code=0, stdout="", stderr="", files=None):
    return {"exit_code": exit_code, "stdout": stdout, "stderr": stderr, "files": files or {}}



def test_exit_0_to_nonzero_is_high(cfg, norm):
    before = capture("deploy", cli_data(0, "ok"))
    after = capture("deploy", cli_data(1, "failed"))
    changes = diff_cli(before, after, norm, cfg, make_change)
    assert change_of(changes, "exit_code_changed").severity == "high"


def test_nonzero_to_zero_is_medium(cfg, norm):
    before = capture("deploy", cli_data(1, "failed"))
    after = capture("deploy", cli_data(0, "ok"))
    changes = diff_cli(before, after, norm, cfg, make_change)
    assert change_of(changes, "exit_code_changed").severity == "medium"


def test_stdout_change_is_uncertain_category_low(cfg, norm):
    before = capture("deploy", cli_data(0, "all good"))
    after = capture("deploy", cli_data(0, "all good!"))
    changes = diff_cli(before, after, norm, cfg, make_change)
    change = change_of(changes, "stdout_changed")
    assert change.severity == "low"
    assert change.confidence < 1.0


def test_stderr_change(cfg, norm):
    before = capture("run", cli_data(0, "", ""))
    after = capture("run", cli_data(0, "", "deprecation warning"))
    changes = diff_cli(before, after, norm, cfg, make_change)
    assert change_of(changes, "stderr_changed")


def test_ansi_noise_ignored(cfg, norm):
    before = capture("run", cli_data(0, "\x1b[32mDone\x1b[0m\n"))
    after = capture("run", cli_data(0, "Done\n"))
    assert diff_cli(before, after, norm, cfg, make_change) == []


def test_file_created(cfg, norm):
    before = capture("gen", cli_data(0, "", "", files={"out.json": {"exists": False, "sha256": None, "size": None}}))
    after = capture("gen", cli_data(0, "", "", files={"out.json": {"exists": True, "sha256": "abc", "size": 10}}))
    changes = diff_cli(before, after, norm, cfg, make_change)
    assert change_of(changes, "file_created", path="out.json").severity == "medium"


def test_file_deleted_is_high(cfg, norm):
    before = capture("gen", cli_data(0, "", "", files={"out.json": {"exists": True, "sha256": "abc", "size": 10}}))
    after = capture("gen", cli_data(0, "", "", files={"out.json": {"exists": False, "sha256": None, "size": None}}))
    changes = diff_cli(before, after, norm, cfg, make_change)
    assert change_of(changes, "file_deleted", path="out.json").severity == "high"


def test_file_modified(cfg, norm):
    before = capture("gen", cli_data(0, "", "", files={"out.json": {"exists": True, "sha256": "abc", "size": 10}}))
    after = capture("gen", cli_data(0, "", "", files={"out.json": {"exists": True, "sha256": "def", "size": 12}}))
    changes = diff_cli(before, after, norm, cfg, make_change)
    assert change_of(changes, "file_modified", path="out.json")


def test_no_change_when_identical(cfg, norm):
    data = cli_data(0, "same\n", "", files={"out.json": {"exists": True, "sha256": "abc", "size": 10}})
    assert diff_cli(capture("run", data), capture("run", data), norm, cfg, make_change) == []
