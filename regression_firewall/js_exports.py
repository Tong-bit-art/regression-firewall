"""Static extraction of JavaScript/TypeScript public exports.

Pure text analysis — no execution, no dependencies, fully deterministic.

Honest scope (V0.3):
- ESM: named exports (function / class / const / let / var / interface /
  type / enum), ``export default``, aliased ``export {a as b}`` lists, and
  one-hop re-export resolution (``export {x} from``, ``export * from``,
  ``export * as ns from``) with a depth cap and cycle guard.
- CommonJS: ``exports.NAME =`` and ``module.exports.NAME =``.
- NOT supported (never guessed at): minified code, dynamic exports,
  destructured ``export const {a} = ...``, path aliases in re-export
  specifiers, object-literal ``module.exports = {...}``, class members,
  regex literals containing comment-like sequences.
"""

from __future__ import annotations

import re
from pathlib import Path

MAX_RESOLVE_DEPTH = 3

RESOLVE_SUFFIXES = ("", ".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs")

_DEFAULT_RE = re.compile(r"\bexport\s+default\b")
_FN_RE = re.compile(
    r"\bexport\s+(?:declare\s+)?(?:async\s+)?function\s*\*?\s*(\w+)\s*\(([^)]*)\)"
)
_CLASS_RE = re.compile(
    r"\bexport\s+(?:declare\s+)?(?:abstract\s+)?class\s+(\w+)"
)
_VAR_RE = re.compile(r"\bexport\s+(?:declare\s+)?(const|let|var)\s+(\w+)\s*=")
_ARROW_CALL_RE = re.compile(r"\s*(?:async\s+)?\(([^()]*)\)\s*(?::[^=]*)?=>")
_ARROW_IDENT_RE = re.compile(r"\s*(?:async\s+)?(\w+)\s*=>")
_INTERFACE_RE = re.compile(r"\bexport\s+(?:declare\s+)?interface\s+(\w+)")
_TYPE_RE = re.compile(r"\bexport\s+(?:declare\s+)?type\s+(\w+)\s*=")
_ENUM_RE = re.compile(r"\bexport\s+(?:declare\s+)?(?:const\s+)?enum\s+(\w+)")
_NAMED_LIST_RE = re.compile(r"\bexport\s*\{([^}]*)\}(?:\s*from\s*['\"]([^'\"]+)['\"])?")
_STAR_RE = re.compile(r"\bexport\s*\*\s*(?:as\s+(\w+)\s*)?from\s*['\"]([^'\"]+)['\"]")
_CJS_RE = re.compile(r"\b(?:module\.)?exports\.(\w+)\s*=")


# -- text preparation ----------------------------------------------------------


def strip_comments_and_strings(text: str) -> str:
    """Blank out comment bodies and string/template-literal contents, keeping
    every character position (newlines preserved) so match offsets stay valid
    line numbers. Regex literals are not specially handled (documented)."""
    out = []
    i, n = 0, len(text)
    state = "code"  # code | line | block | single | double | template
    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if state == "code":
            if ch == "/" and nxt == "/":
                state = "line"
                out.append("  ")
                i += 2
                continue
            if ch == "/" and nxt == "*":
                state = "block"
                out.append("  ")
                i += 2
                continue
            if ch == "'":
                state = "single"
                out.append(" ")
                i += 1
                continue
            if ch == '"':
                state = "double"
                out.append(" ")
                i += 1
                continue
            if ch == "`":
                state = "template"
                out.append(" ")
                i += 1
                continue
            out.append(ch)
            i += 1
        elif state == "line":
            if ch == "\n":
                state = "code"
                out.append("\n")
            else:
                out.append(" ")
            i += 1
        elif state == "block":
            if ch == "*" and nxt == "/":
                state = "code"
                out.append("  ")
                i += 2
                continue
            out.append(" ")
            i += 1
        else:  # inside a string/template literal
            if ch == "\\" and i + 1 < n:
                out.append("  ")
                i += 2
                continue
            if (state == "single" and ch == "'") or \
               (state == "double" and ch == '"') or \
               (state == "template" and ch == "`"):
                state = "code"
                out.append(" ")
                i += 1
                continue
            out.append(" ")
            i += 1
    return "".join(out)


def strip_comments(text: str) -> str:
    """Blank out comments only — string literals stay intact. Used for
    re-export specifiers, which are plain strings a comment-blanking pass
    would erase."""
    out = []
    i, n = 0, len(text)
    state = "code"  # code | line | block | single | double | template
    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if state == "code":
            if ch == "/" and nxt == "/":
                state = "line"
                out.append("  ")
                i += 2
                continue
            if ch == "/" and nxt == "*":
                state = "block"
                out.append("  ")
                i += 2
                continue
            if ch in "'\"`":
                state = {"'": "single", '"': "double", "`": "template"}[ch]
            out.append(ch)
            i += 1
        elif state == "line":
            if ch == "\n":
                state = "code"
                out.append("\n")
            else:
                out.append(" ")
            i += 1
        elif state == "block":
            if ch == "*" and nxt == "/":
                state = "code"
                out.append("  ")
                i += 2
                continue
            out.append(" ")
            i += 1
        else:  # string/template: keep verbatim, watch for the closing quote
            if ch == "\\" and i + 1 < n:
                out.append(text[i:i + 2])
                i += 2
                continue
            if (state == "single" and ch == "'") or \
               (state == "double" and ch == '"') or \
               (state == "template" and ch == "`"):
                state = "code"
            out.append(ch)
            i += 1
    return "".join(out)


# -- signature canonicalization -------------------------------------------------


def canonical_params(params_text: str) -> str:
    """Canonical parameter fingerprint: names plus presence of optionality
    (``?`` / default) and rest. Mirrors the Python ``_canonical_signature``
    philosophy — structure only, no type text or default values (framework
    and environment-dependent reprs must not churn the fingerprint)."""
    params = _split_top_level(params_text)
    tokens = []
    for param in params:
        token = param.strip()
        if not token:
            continue
        rest = token.startswith("...")
        if rest:
            token = token[3:].strip()
        name = re.split(r"[?:\s=:]", token, 1)[0].strip()
        if not name:
            continue
        marker = "..." if rest else ""
        # "=>" must not count as a default value
        probe = token.replace("=>", "")
        optional = ("?" in probe or "=" in probe) and not rest
        tokens.append(f"{marker}{name}{'?' if optional else ''}")
    return "(" + ", ".join(tokens) + ")"


def _split_top_level(text: str) -> list:
    parts, stack, current = [], [], []
    pairs = {"(": ")", "[": "]", "<": ">", "{": "}"}
    for ch in text:
        if ch in pairs:
            stack.append(pairs[ch])
        elif stack and ch == stack[-1]:
            stack.pop()
        if ch == "," and not stack:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    parts.append("".join(current))
    return parts


# -- single-file parsing ---------------------------------------------------------


def parse_exports(text: str) -> dict:
    """Raw exports of one source file (no re-export resolution).

    Returns {symbols: {name: {kind, signature, line}}, default_export: bool,
    reexports: [{"spec", "names"|None, "namespace"|None, "line"}]}.
    """
    stripped = strip_comments_and_strings(text)
    symbols: dict = {}

    def add(name: str, kind: str, pos: int, signature=None) -> None:
        if name and name not in symbols:
            symbols[name] = {
                "kind": kind,
                "signature": signature,
                "line": stripped[:pos].count("\n") + 1,
            }

    for match in _FN_RE.finditer(stripped):
        add(match.group(1), "function", match.start(),
            canonical_params(match.group(2)))
    for match in _CLASS_RE.finditer(stripped):
        add(match.group(1), "class", match.start())
    for match in _INTERFACE_RE.finditer(stripped):
        add(match.group(1), "interface", match.start())
    for match in _TYPE_RE.finditer(stripped):
        add(match.group(1), "type", match.start())
    for match in _ENUM_RE.finditer(stripped):
        add(match.group(1), "enum", match.start())
    for match in _VAR_RE.finditer(stripped):
        tail = stripped[match.end():match.end() + 200]
        arrow = _ARROW_CALL_RE.search(tail)
        signature = None
        if arrow and arrow.start() == 0:
            signature = canonical_params(arrow.group(1))
        else:
            arrow_ident = _ARROW_IDENT_RE.search(tail)
            if arrow_ident and arrow_ident.start() == 0:
                signature = "(" + arrow_ident.group(1) + ")"
        add(match.group(2), match.group(1), match.start(), signature)
    for match in _CJS_RE.finditer(stripped):
        add(match.group(1), "cjs", match.start())

    default_export = bool(_DEFAULT_RE.search(stripped))
    if default_export:
        # export default function name(...)/class Name: the following
        # declaration is NOT importable by name in real JS, so only the
        # "default" symbol is recorded — with its signature when available.
        default_match = _DEFAULT_RE.search(stripped)
        default_sig = None
        tail = stripped[default_match.end():default_match.end() + 200]
        bare_fn = re.match(r"\s*(?:async\s+)?function\s*\*?\s*\w+\s*\(([^)]*)\)", tail)
        if bare_fn:
            default_sig = canonical_params(bare_fn.group(1))
        add("default", "default", default_match.start(), default_sig)

    # Re-export specifiers live inside plain strings, so they are matched on
    # a comments-only pass (string contents stay intact there).
    comments_only = strip_comments(text)
    reexports = []
    for match in _NAMED_LIST_RE.finditer(comments_only):
        spec = match.group(2)
        names = []
        for item in match.group(1).split(","):
            item = item.strip()
            if not item:
                continue
            local, _, exported = item.partition(" as ")
            names.append((local.strip(), exported.strip() or local.strip()))
        line = comments_only[:match.start()].count("\n") + 1
        if not spec:
            # local alias list (export {a, b as c}): the names are public
            for _, exported in names:
                add(exported, "local", match.start())
            continue
        reexports.append({"spec": spec, "names": names, "namespace": None,
                          "line": line})
    for match in _STAR_RE.finditer(comments_only):
        reexports.append({
            "spec": match.group(2),
            "names": None,
            "namespace": match.group(1),
            "line": comments_only[:match.start()].count("\n") + 1,
        })

    return {"symbols": symbols, "default_export": default_export,
            "reexports": reexports}


# -- re-export resolution ---------------------------------------------------------


def resolve_specifier(spec: str, from_file: Path) -> Path | None:
    """Resolve a relative re-export specifier to a file the way TypeScript
    does: exact, then with known extensions, then as a directory index.
    Non-relative specifiers (packages, aliases) resolve to None."""
    if not spec.startswith("./") and not spec.startswith("../"):
        return None
    base = (from_file.parent / spec).resolve()
    for suffix in RESOLVE_SUFFIXES:
        candidate = Path(str(base) + suffix) if suffix else base
        if candidate.is_file():
            return candidate
    for suffix in RESOLVE_SUFFIXES:
        candidate = base / ("index" + suffix)
        if candidate.is_file():
            return candidate
    return None


def collect_public_symbols(file_path: Path, depth: int = MAX_RESOLVE_DEPTH,
                           _visited=None) -> dict:
    """Public symbols of a file, resolving re-exports up to `depth` hops.

    Returns {symbols: {name: {kind, signature, line, origin}},
    unresolved: [specifier]} — line refers to the ORIGIN file; origin is the
    posix path relative to the probed file's project (best effort: relative
    to the probed file's parent when resolution started there).
    """
    if _visited is None:
        _visited = set()
    key = str(file_path.resolve())
    if key in _visited or depth < 0:
        return {"symbols": {}, "unresolved": []}
    _visited.add(key)

    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {"symbols": {}, "unresolved": []}
    parsed = parse_exports(text)
    symbols = {}
    for name, entry in parsed["symbols"].items():
        symbols[name] = {**entry, "origin": file_path.as_posix()}

    unresolved = []
    if depth > 0:
        for reexport in parsed["reexports"]:
            spec = reexport["spec"]
            target = resolve_specifier(spec, file_path)
            if target is None:
                unresolved.append(spec)
                continue
            nested = collect_public_symbols(target, depth - 1, _visited)
            unresolved.extend(nested["unresolved"])
            if reexport["namespace"]:
                ns_name = reexport["namespace"]
                if ns_name not in symbols:
                    symbols[ns_name] = {"kind": "namespace", "signature": None,
                                        "line": reexport["line"],
                                        "origin": target.as_posix()}
            elif reexport["names"] is None:  # export * from
                for name, entry in nested["symbols"].items():
                    if name == "default":
                        continue
                    symbols.setdefault(name, {**entry, "line": entry.get("line"),
                                              "origin": entry.get("origin")})
            else:  # export {a as b} from
                for local, exported in reexport["names"]:
                    entry = nested["symbols"].get(local)
                    if entry is not None:
                        symbols[exported] = {**entry, "origin": entry.get("origin")}
    return {"symbols": symbols, "unresolved": unresolved}
