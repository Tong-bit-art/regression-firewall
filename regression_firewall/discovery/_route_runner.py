"""Subprocess runner for HTTP route discovery (imports user app code)."""

from __future__ import annotations

import argparse
import importlib
import json
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True, help="module:attr of the app object")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    result = {"ok": False, "error": None, "routes": []}

    def flush(code: int) -> int:
        with open(args.out, "w", encoding="utf-8") as handle:
            json.dump(result, handle, ensure_ascii=False)
        return code

    module_name, _, attr = args.spec.partition(":")
    if not module_name:
        result["error"] = f"invalid spec {args.spec!r}; expected 'module:attr'"
        return flush(1)
    attr = attr or "app"

    try:
        module = importlib.import_module(module_name)
        app = getattr(module, attr)
    except BaseException as exc:
        result["error"] = f"could not load {args.spec!r}: {type(exc).__name__}: {exc}"
        return flush(1)

    routes = []
    try:
        if hasattr(app, "routes"):  # FastAPI / Starlette
            for route in app.routes:
                path = getattr(route, "path", None)
                methods = getattr(route, "methods", None) or []
                methods = sorted(m for m in methods if m not in ("HEAD", "OPTIONS"))
                if path and methods:
                    for method in methods:
                        routes.append({"methods": [method], "path": path})
        elif hasattr(app, "url_map"):  # Flask
            for rule in app.url_map.iter_rules():
                methods = sorted(rule.methods - {"HEAD", "OPTIONS"})
                if methods:
                    for method in methods:
                        routes.append({"methods": [method], "path": rule.rule})
        else:
            result["error"] = (
                "app object exposes neither 'routes' (FastAPI/Starlette) nor "
                "'url_map' (Flask)"
            )
            return flush(1)
    except BaseException as exc:
        result["error"] = f"route extraction failed: {type(exc).__name__}: {exc}"
        return flush(1)

    routes.sort(key=lambda r: (r["path"], r["methods"]))
    result.update(ok=True, routes=routes)
    return flush(0)


if __name__ == "__main__":
    sys.exit(main())
