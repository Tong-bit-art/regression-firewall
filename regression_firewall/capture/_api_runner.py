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



def _canonical_signature(obj) -> str | None:
    """Produce a stable, canonical fingerprint of a callable's signature.

    Raw ``str(inspect.signature(obj))`` is nondeterministic for framework
    callables whose default values contain objects with volatile reprs
    (e.g. ``Doc()`` instances). This function captures only the structural
    aspects: parameter names, kinds, and presence of defaults/annotations.

    Returns ``"<signature unavailable>"`` if the signature cannot be
    deterministically captured.
    """
    try:
        sig = inspect.signature(obj)
    except (ValueError, TypeError):
        return "<signature unavailable>"

    parts = []
    for param in sig.parameters.values():
        piece = param.name
        if param.kind is not inspect.Parameter.POSITIONAL_ONLY:
            pass  # name alone distinguishes
        elif param.name.startswith("/"):
            piece = f"/{param.name}"
        if param.kind is inspect.Parameter.VAR_POSITIONAL:
            piece = f"*{param.name}"
        elif param.kind is inspect.Parameter.VAR_KEYWORD:
            piece = f"**{param.name}"
        elif param.kind is inspect.Parameter.KEYWORD_ONLY:
            piece = f" {param.name}"

        # Default presence (not the value — values may be nondeterministic)
        if param.default is not inspect.Parameter.empty:
            piece += "="

        # Annotation presence (not the annotation text — may be volatile)
        if param.annotation is not inspect.Parameter.empty:
            piece += ":"

        parts.append(piece)

    ret = ""
    if sig.return_annotation is not inspect.Parameter.empty:
        ret = "->"

    return "(" + ", ".join(parts) + ")" + ret


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

    public_namespace = {str(n) for n in vars(module) if not str(n).startswith("_")}
    dunder_all = getattr(module, "__all__", None)
    if dunder_all is not None:
        exported = [str(n) for n in dunder_all]
        result["exports"] = list(exported)
        # __all__ is a declaration, not the namespace: it can be stale (a
        # name listed there may no longer resolve) and it can omit names
        # that are still importable (a new top-level function, or a module
        # with a restrictive __dir__ such as packaging.version). Capture the
        # union of declared exports and importable public names.
        names = sorted(set(exported) | public_namespace)
    else:
        names = sorted(public_namespace)
    if args.include_private:
        names += [
            str(n) for n in vars(module)
            if str(n).startswith("_") and not str(n).startswith("__")
        ]

    symbols = {}
    for name in sorted(set(names)):
        try:
            obj = getattr(module, name)
        except BaseException as exc:
            # A declared name that cannot be resolved (stale __all__ entry,
            # broken export) is recorded as unresolvable; the diff classifies
            # it as a removal when the other side resolves it.
            symbols[name] = {
                "kind": "error",
                "signature": None,
                "error": f"{type(exc).__name__}: {exc}",
            }
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
            signature = _canonical_signature(obj)
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
