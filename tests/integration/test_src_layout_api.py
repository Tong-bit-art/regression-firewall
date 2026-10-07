"""P0 src-layout coverage regression tests.

A standard src-layout project (``pyproject.toml`` + ``src/<package>/``) must
be introspectable through the project's own import root — no install, no
hardcoded repository names. The checked-in fixture declares ``__all__``
because the real-world miss (urllib3) only manifests when a module has a
declared export list:

1. a name listed in ``__all__`` that can no longer be resolved was
   misreported as a signature change instead of ``symbol_removed``;
2. a new top-level name that is importable but not listed in ``__all__``
   was never captured at all.
"""

import json
import shutil
from pathlib import Path

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "src_layout_package"

API_CONFIG = """\
version: 1
surfaces:
  http:
    enabled: false
  cli:
    enabled: false
  public_api:
    enabled: true
    probes:
      - id: layoutpkg
        module: layoutpkg
"""


def _copy_fixture(project: Path) -> Path:
    root = project / "app"
    shutil.copytree(FIXTURE, root)
    return root


def _read_report(root: Path) -> dict:
    return json.loads(
        (root / ".regression-firewall" / "report.json").read_text(encoding="utf-8")
    )


def _categories(report: dict) -> set:
    return {(c["category"], c["classification"]) for c in report["changes"]}


def _rewrite(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text, f"fixture drifted: {old!r} not found in {path.name}"
    path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


def _init_module(root: Path) -> Path:
    return root / "src" / "layoutpkg" / "__init__.py"


def test_src_layout_discover_reports_package(project, run_rf, write):
    root = _copy_fixture(project)
    write(root / ".regression-firewall.yml", API_CONFIG)
    proc = run_rf(["discover"], root, expect_exit=0)
    assert "layoutpkg" in proc.stdout


def test_removed_symbol_still_declared_in_all_blocks(project, run_rf, write):
    """urllib3-style removal: the import is gone, __all__ still lists it."""
    root = _copy_fixture(project)
    write(root / ".regression-firewall.yml", API_CONFIG)
    run_rf(["baseline"], root, expect_exit=0)

    _rewrite(_init_module(root),
             "from .core import VERSION, add, greet",
             "from .core import VERSION, add")

    proc = run_rf(["check"], root)
    assert proc.returncode == 3, proc.stdout  # BLOCK: critical removal
    report = _read_report(root)
    assert ("symbol_removed", "unexpected") in _categories(report)
    removed = [c for c in report["changes"] if c["category"] == "symbol_removed"]
    assert removed[0]["target"] == "layoutpkg.greet"
    assert removed[0]["severity"] == "critical"


def test_clean_removed_symbol_blocks(project, run_rf, write):
    """Removal from both the import and __all__ is detected as well."""
    root = _copy_fixture(project)
    write(root / ".regression-firewall.yml", API_CONFIG)
    run_rf(["baseline"], root, expect_exit=0)

    _rewrite(_init_module(root),
             "from .core import VERSION, add, greet",
             "from .core import VERSION, add")
    _rewrite(_init_module(root),
             '__all__ = ["VERSION", "add", "greet"]',
             '__all__ = ["VERSION", "add"]')

    proc = run_rf(["check"], root)
    assert proc.returncode == 3, proc.stdout
    report = _read_report(root)
    assert ("symbol_removed", "unexpected") in _categories(report)
    assert any(c["target"] == "layoutpkg.greet" for c in report["changes"])


def test_added_symbol_not_in_all_is_detected(project, run_rf, write):
    """A new importable top-level function must be captured even when the
    module's __all__ was not updated."""
    root = _copy_fixture(project)
    write(root / ".regression-firewall.yml", API_CONFIG)
    run_rf(["baseline"], root, expect_exit=0)

    module = _init_module(root)
    module.write_text(
        module.read_text(encoding="utf-8") + '\n\ndef health() -> str:\n    return "ok"\n',
        encoding="utf-8", newline="\n",
    )

    proc = run_rf(["check"], root)
    assert proc.returncode == 0, proc.stdout  # additive info -> PASS
    report = _read_report(root)
    assert ("symbol_added", "uncertain") in _categories(report)
    added = [c for c in report["changes"] if c["category"] == "symbol_added"]
    assert added[0]["target"] == "layoutpkg.health"


def test_signature_changed_reviews(project, run_rf, write):
    root = _copy_fixture(project)
    write(root / ".regression-firewall.yml", API_CONFIG)
    run_rf(["baseline"], root, expect_exit=0)

    _rewrite(root / "src" / "layoutpkg" / "core.py",
             "def add(a: int, b: int) -> int:",
             "def add(a: int, b: int, c: int = 0) -> int:")

    proc = run_rf(["check"], root)
    assert proc.returncode == 1, proc.stdout  # REVIEW
    report = _read_report(root)
    assert ("signature_changed", "unexpected") in _categories(report)


def test_implementation_only_change_is_clean(project, run_rf, write):
    root = _copy_fixture(project)
    write(root / ".regression-firewall.yml", API_CONFIG)
    run_rf(["baseline"], root, expect_exit=0)

    _rewrite(root / "src" / "layoutpkg" / "core.py",
             "    return a + b",
             "    total = a + b\n    return total")

    proc = run_rf(["check"], root)
    assert proc.returncode == 0, proc.stdout
    assert _read_report(root)["changes"] == []


def test_repeated_capture_is_stable(project, run_rf, write):
    root = _copy_fixture(project)
    write(root / ".regression-firewall.yml", API_CONFIG)
    run_rf(["baseline"], root, expect_exit=0)

    first = run_rf(["check"], root)
    second = run_rf(["check"], root)
    assert first.returncode == 0 and second.returncode == 0, first.stdout + second.stdout
    assert _read_report(root)["changes"] == []
