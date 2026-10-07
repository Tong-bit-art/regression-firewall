import json


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
      - id: samplelib
        module: samplelib
"""

LIB_V1 = """\
class Client:
    def __init__(self, retries=3):
        self.retries = retries


class RetryPolicy:
    def __init__(self, attempts=5):
        self.attempts = attempts


def connect(host, port=5432):
    return (host, port)
"""


def read_report(project):
    return json.loads(
        (project / ".regression-firewall" / "report.json").read_text(encoding="utf-8")
    )


def categories(report):
    return {(c["category"], c["classification"]) for c in report["changes"]}


def test_symbol_removed_blocks(project, run_rf, write):
    write(project / "samplelib" / "__init__.py", LIB_V1)
    write(project / ".regression-firewall.yml", API_CONFIG)
    run_rf(["baseline"], project, expect_exit=0)
    mutated = LIB_V1.replace('''class RetryPolicy:
    def __init__(self, attempts=5):
        self.attempts = attempts


''', "")
    write(project / "samplelib" / "__init__.py", mutated)
    proc = run_rf(["check"], project)
    assert proc.returncode == 3, proc.stdout  # BLOCK
    report = read_report(project)
    assert ("symbol_removed", "unexpected") in categories(report)


def test_signature_change_reviews(project, run_rf, write):
    write(project / "samplelib" / "__init__.py", LIB_V1)
    write(project / ".regression-firewall.yml", API_CONFIG)
    run_rf(["baseline"], project, expect_exit=0)
    mutated = LIB_V1.replace("def connect(host, port=5432):", "def connect(host, port, timeout=30):")
    write(project / "samplelib" / "__init__.py", mutated)
    proc = run_rf(["check"], project)
    assert proc.returncode == 1, proc.stdout  # REVIEW
    report = read_report(project)
    assert ("signature_changed", "unexpected") in categories(report)


def test_symbol_addition_passes(project, run_rf, write):
    write(project / "samplelib" / "__init__.py", LIB_V1)
    write(project / ".regression-firewall.yml", API_CONFIG)
    run_rf(["baseline"], project, expect_exit=0)
    mutated = LIB_V1 + """

def ping():
    return "pong"
"""
    write(project / "samplelib" / "__init__.py", mutated)
    proc = run_rf(["check"], project)
    assert proc.returncode == 0, proc.stdout  # additive INFO -> PASS
    report = read_report(project)
    assert ("symbol_added", "uncertain") in categories(report)


def test_expected_removal_with_intent_passes(project, run_rf, write):
    write(project / "samplelib" / "__init__.py", LIB_V1)
    write(project / ".regression-firewall.yml", API_CONFIG)
    run_rf(["baseline"], project, expect_exit=0)
    mutated = LIB_V1.replace('''class RetryPolicy:
    def __init__(self, attempts=5):
        self.attempts = attempts


''', "")
    write(project / "samplelib" / "__init__.py", mutated)
    intent = {
        "schema_version": 1,
        "task": "Drop RetryPolicy; users should use Client-level retries.",
        "expected_changes": [
            {"surface": "public_api", "target": "samplelib.RetryPolicy",
             "category": "symbol_removed", "note": "intentional removal"},
        ],
    }
    write(project / ".regression-firewall" / "intent.json", json.dumps(intent, indent=2))
    proc = run_rf(["check"], project)
    assert proc.returncode == 0, proc.stdout
    report = read_report(project)
    assert report["verdict"] == "PASS"


BROKEN_MODULE_CONFIG = """\
version: 1
surfaces:
  http:
    enabled: false
  cli:
    enabled: false
  public_api:
    enabled: true
    probes:
      - id: ghost
        module: ghost_module_9f3a_does_not_exist
"""


def test_unverifiable_probe_cannot_pass(project, run_rf, write):
    """A probe that fails at baseline *and* check has verified nothing; the
    verdict must not silently read as a clean PASS (real-world: build-generated
    files deleted between captures, e.g. urllib3's src/urllib3/_version.py)."""
    write(project / ".regression-firewall.yml", BROKEN_MODULE_CONFIG)
    baseline = run_rf(["baseline"], project, expect_exit=0)
    assert "failed to capture" in baseline.stdout

    proc = run_rf(["check"], project)
    assert proc.returncode == 1, proc.stdout  # REVIEW, not PASS
    report = read_report(project)
    assert report["verdict"] == "REVIEW"
    assert any("NOT verified" in w for w in report["warnings"]), report["warnings"]
