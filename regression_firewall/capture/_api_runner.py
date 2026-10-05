"""Subprocess runner for public-API introspection.

Runs OUTSIDE the CLI process (user code is imported here). Writes a JSON
result to --out and exits 0 on success, 1 on failure. Never imports anything
beyond the stdlib plus the target module.
"""

from __future__ import annotations

import argparse
import importlib
import inspect
import json
import pkgutil
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--module", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--include-private", action="store_true")
    args = parser.parse_args()

    result = {
        "ok": False,
        "error": None,
        "module": args.module,
        "symbols": {},
        "submodules": [],
        "exports": None,
    }

    def flush(code: int) -> int:
        with open(args.out, "w", encoding="utf-8") as handle:
            json.dump(result, handle, ensure_ascii=False)
        return code

    try:
        module = importlib.import_module(args.module)
    except BaseException as exc:  # user code may raise anything, incl. SystemExit
        result["error"] = f"import failed: {type(exc).__name__}: {exc}"
        return flush(1)

    dunder_all = getattr(module, "__all__", None)
    if dunder_all is not None:
        names = [str(n) for n in dunder_all]
        result["exports"] = list(names)
    else:
        names = [n for n in dir(module) if not n.startswith("_")]
        if args.include_private:
            names += [
                n for n in dir(module)
                if n.startswith("_") and not n.startswith("__")
            ]

    symbols = {}
    for name in sorted(set(names)):
        try:
            obj = getattr(module, name)
        except BaseException as exc:
            symbols[name] = {"kind": "error", "signature": f"getattr failed: {type(exc).__name__}"}
            continue
        if inspect.ismodule(obj):
            symbols[name] = {"kind": "module", "signature": None}
            continue
        if inspect.isfunction(obj) or inspect.ismethod(obj):
            kind = "function"
        elif inspect.isclass(obj):
            kind = "class"
        else:
            kind = type(obj).__name__
        signature = None
        if kind in ("function", "class"):
            try:
                signature = str(inspect.signature(obj))
            except (ValueError, TypeError):
                signature = "<signature unavailable>"
        symbols[name] = {"kind": kind, "signature": signature}

    submodules = []
    module_path = getattr(module, "__path__", None)
    if module_path:
        try:
            submodules = sorted(f"{args.module}.{m.name}" for m in pkgutil.iter_modules(module_path))
        except Exception as exc:
            result["submodule_scan_error"] = f"{type(exc).__name__}: {exc}"

    result.update(ok=True, symbols=symbols, submodules=submodules)
    return flush(0)


if __name__ == "__main__":
    sys.exit(main())
