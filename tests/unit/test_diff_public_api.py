from _helpers import change_of

from regression_firewall.diff.engine import make_change
from regression_firewall.diff.public_api import diff_public_api
from regression_firewall.models.snapshot import ProbeCapture


def capture(probe_id, data, ok=True, error=None):
    return ProbeCapture(probe_id=probe_id, target=probe_id, ok=ok, error=error, data=data)


def api_data(symbols, submodules=None, exports=None, module="samplelib"):
    return {"module": module, "symbols": symbols, "submodules": submodules or [],
            "exports": exports}



def test_symbol_removed_is_critical(cfg, norm):
    before = capture("samplelib", api_data({"Client": {"kind": "class", "signature": "(self)"}}))
    after = capture("samplelib", api_data({}))
    changes = diff_public_api(before, after, cfg, make_change)
    change = change_of(changes, "symbol_removed")
    assert change.severity == "critical"
    assert change.target == "samplelib.Client"


def test_symbol_added_is_info(cfg, norm):
    before = capture("samplelib", api_data({}))
    after = capture("samplelib", api_data({"retry": {"kind": "function", "signature": "(f)"}}))
    changes = diff_public_api(before, after, cfg, make_change)
    assert change_of(changes, "symbol_added").severity == "info"


def test_signature_changed_is_medium(cfg, norm):
    before = capture("samplelib", api_data({"connect": {"kind": "function", "signature": "(host, port=5432)"}}))
    after = capture("samplelib", api_data({"connect": {"kind": "function", "signature": "(host, port, timeout=30)"}}))
    changes = diff_public_api(before, after, cfg, make_change)
    change = change_of(changes, "signature_changed")
    assert change.severity == "medium"
    assert change.before == "(host, port=5432)"
    assert change.after == "(host, port, timeout=30)"


def test_submodule_removed(cfg, norm):
    before = capture("samplelib", api_data({}, submodules=["samplelib.core", "samplelib.util"]))
    after = capture("samplelib", api_data({}, submodules=["samplelib.core"]))
    changes = diff_public_api(before, after, cfg, make_change)
    change = change_of(changes, "symbol_removed")
    assert change.target == "samplelib.util"


def test_export_changed(cfg, norm):
    before = capture("samplelib", api_data({"Client": {"kind": "class", "signature": "(self)"}},
                                           exports=["Client"]))
    after = capture("samplelib", api_data({"Client": {"kind": "class", "signature": "(self)"}},
                                          exports=[]))
    changes = diff_public_api(before, after, cfg, make_change)
    assert change_of(changes, "export_changed")


def test_export_change_ignored_when_no_all(cfg, norm):
    # exports=None on both sides means the module does not define __all__;
    # dir()-derived symbol changes are reported individually instead.
    before = capture("samplelib", api_data({"a": {"kind": "str", "signature": None}}))
    after = capture("samplelib", api_data({"a": {"kind": "str", "signature": None}}))
    assert diff_public_api(before, after, cfg, make_change) == []


def test_capture_error(cfg, norm):
    before = capture("samplelib", api_data({}))
    after = capture("samplelib", {}, ok=False, error="import failed: SyntaxError: bad")
    changes = diff_public_api(before, after, cfg, make_change)
    assert change_of(changes, "capture_error").severity == "high"
