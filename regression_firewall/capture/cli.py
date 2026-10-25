from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from ..config.schema import CliSurfaceConfig
from ..models.snapshot import ProbeCapture
from ..sqlshape import sql_shape, write_targets

# Injected via PYTHONPATH so every Python process in the probe tree records
# its filesystem writes and (optionally) environment-variable READS (names
# only — values are never written to the trace). Records are appended as
# JSON lines; each record flushes immediately so even a crashing probe
# leaves its trace behind.
SITECUSTOMIZE_SOURCE = '''\\
import atexit, builtins, json, os, threading

_OUT = os.environ.get("REGFW_TRACE_OUT") or ""
_TRACE_FS = os.environ.get("REGFW_TRACE_FS") == "1"
_TRACE_ENV = os.environ.get("REGFW_TRACE_ENV") == "1"
_TRACE_SQLITE = os.environ.get("REGFW_TRACE_SQLITE") == "1"

if _OUT:
    _lock = threading.Lock()

    def _record(obj):
        try:
            with _lock, open(_OUT, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(obj) + "\\n")
        except Exception:
            pass

    if _TRACE_FS:
        _orig_open = builtins.open

        def _open(file, mode="r", *a, **k):
            try:
                text = os.fspath(file)
                if os.path.abspath(text) != os.path.abspath(_OUT) and any(
                    m in mode for m in ("w", "a", "x", "+")
                ):
                    _record({"op": "write", "path": os.path.abspath(text)})
            except Exception:
                pass
            return _orig_open(file, mode, *a, **k)

        # io.open and builtins.open are the same object but two separate
        # namespace bindings; pathlib (and much of the stdlib) resolves the
        # io module's name at call time, so both must point at the wrapper.
        import io as _io

        builtins.open = _open
        _io.open = _open

        _orig_remove = os.remove

        def _remove(path, *a, **k):
            _record({"op": "remove", "path": os.path.abspath(os.fspath(path))})
            return _orig_remove(path, *a, **k)

        os.remove = _remove
        os.unlink = _remove

        for _name in ("rename", "replace"):
            _orig = getattr(os, _name)

            def _two(src, dst, *a, __orig=_orig, **k):
                try:
                    _record({"op": "write", "path": os.path.abspath(os.fspath(dst))})
                except Exception:
                    pass
                return __orig(src, dst, *a, **k)

            setattr(os, _name, _two)

        for _name in ("mkdir", "makedirs"):
            _orig = getattr(os, _name)

            def _one(path, *a, __orig=_orig, **k):
                try:
                    _record({"op": "write", "path": os.path.abspath(os.fspath(path))})
                except Exception:
                    pass
                return __orig(path, *a, **k)

            setattr(os, _name, _one)

    if _TRACE_ENV:
        _Env = type(os.environ)
        _orig_get = _Env.get

        def _env_get(self, key, *a, **k):
            _record({"op": "env", "name": str(key)})
            return _orig_get(self, key, *a, **k)

        _Env.get = _env_get
        _orig_getitem = _Env.__getitem__

        def _env_getitem(self, key):
            _record({"op": "env", "name": str(key)})
            return _orig_getitem(self, key)

        _Env.__getitem__ = _env_getitem

    if _TRACE_SQLITE:
        # sqlite3's Cursor/Connection are C extension types — their methods
        # cannot be monkeypatched, but the documented `factory` hook allows
        # subclassing. Only stdlib sqlite3.connect() calls made AFTER this
        # injection are traced; other drivers/ORMs are invisible (documented).
        import sqlite3 as _sq

        _orig_connect = _sq.connect

        class _TracedCursor(_sq.Cursor):
            def execute(self, sql, *a, **k):
                _record({"op": "sql", "sql": sql})
                return super().execute(sql, *a, **k)

            def executemany(self, sql, *a, **k):
                _record({"op": "sql", "sql": sql})
                return super().executemany(sql, *a, **k)

        class _TracedConnection(_sq.Connection):
            def cursor(self, *a, **k):
                k.setdefault("factory", _TracedCursor)
                return super().cursor(*a, **k)

            def execute(self, sql, *a, **k):
                _record({"op": "sql", "sql": sql})
                return super().execute(sql, *a, **k)

            def executemany(self, sql, *a, **k):
                _record({"op": "sql", "sql": sql})
                return super().executemany(sql, *a, **k)

            def executescript(self, sql, *a, **k):
                _record({"op": "sql", "sql": sql})
                return super().executescript(sql, *a, **k)

        def _connect(*a, **k):
            k.setdefault("factory", _TracedConnection)
            return _orig_connect(*a, **k)

        _sq.connect = _connect
'''

_PYTHON_NAMES = ("python", "python3", "python.exe", "python3.exe")


def capture_cli_probes(cfg: CliSurfaceConfig, project_root: Path) -> tuple:
    captures, warnings = [], []
    for probe in cfg.probes:
        capture, probe_warnings = _run_probe(probe, project_root)
        captures.append(capture)
        warnings.extend(probe_warnings)
    return captures, warnings


def _run_probe(probe, project_root: Path) -> tuple:
    command = [_resolve_interpreter(part) for part in probe.command]
    cwd = (project_root / probe.cwd).resolve()
    env = os.environ.copy()
    env.update({k: str(v) for k, v in (probe.env or {}).items()})
    # Probe scripts may import modules; stale bytecode must never be captured.
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    warnings = []
    trace_dir = None
    trace = getattr(probe, "trace", None)
    if trace and (trace.fs_writes or trace.env_reads or trace.sqlite):
        if Path(command[0] if command else "").name.lower() not in _PYTHON_NAMES:
            warnings.append(
                f"probe {probe.id!r}: trace requested but the command does not "
                "look like a Python interpreter; tracing skipped"
            )
        else:
            trace_dir = Path(tempfile.mkdtemp(prefix="regfw-trace-"))
            (trace_dir / "sitecustomize.py").write_text(
                SITECUSTOMIZE_SOURCE, encoding="utf-8", newline="\n")
            trace_out = trace_dir / "trace.jsonl"
            env["PYTHONPATH"] = os.pathsep.join(
                [str(trace_dir)] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
            env["REGFW_TRACE_OUT"] = str(trace_out)
            if trace.fs_writes:
                env["REGFW_TRACE_FS"] = "1"
            if trace.env_reads:
                env["REGFW_TRACE_ENV"] = "1"
            if trace.sqlite:
                env["REGFW_TRACE_SQLITE"] = "1"

    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            env=env,
            capture_output=True,
            timeout=probe.timeout,
        )
    except subprocess.TimeoutExpired:
        if trace_dir:
            shutil.rmtree(trace_dir, ignore_errors=True)
        return ProbeCapture(probe_id=probe.id, target=probe.id, ok=False,
                            error=f"command timed out after {probe.timeout:g}s"), warnings
    except FileNotFoundError:
        if trace_dir:
            shutil.rmtree(trace_dir, ignore_errors=True)
        return ProbeCapture(probe_id=probe.id, target=probe.id, ok=False,
                            error=f"command not found: {command[0]}"), warnings
    except PermissionError:
        if trace_dir:
            shutil.rmtree(trace_dir, ignore_errors=True)
        return ProbeCapture(probe_id=probe.id, target=probe.id, ok=False,
                            error=f"command is not executable: {command[0]}"), warnings

    fs_writes, env_reads, db_queries, db_tables = [], [], {}, []
    if trace_dir is not None:
        fs_writes, env_reads, db_queries, db_tables = _read_trace(
            trace_dir / "trace.jsonl", project_root
        )
        shutil.rmtree(trace_dir, ignore_errors=True)

    files = {}
    for rel_path in probe.files:
        files[rel_path] = _file_entry(project_root / rel_path)
    for watch in probe.dirs:
        entries, truncated = _watch_dir_entries(watch, project_root)
        files.update(entries)
        if truncated:
            warnings.append(
                f"probe {probe.id!r}: directory watch {watch.path!r} stopped at "
                f"max_files={watch.max_files}; files beyond the cap are NOT watched"
            )

    data = {
        "exit_code": completed.returncode,
        "stdout": _relativize_text(
            completed.stdout.decode("utf-8", errors="replace"), cwd
        ),
        "stderr": _relativize_text(
            completed.stderr.decode("utf-8", errors="replace"), cwd
        ),
        "files": files,
    }
    if trace_dir is not None or (trace and (trace.fs_writes or trace.env_reads or trace.sqlite)):
        # always present when tracing is configured, so an empty trace is
        # meaningful (the command wrote/read nothing Python-visible)
        data["fs_writes"] = fs_writes
        data["env_reads"] = env_reads
        data["db_queries"] = db_queries
        data["db_tables_written"] = db_tables

    return ProbeCapture(
        probe_id=probe.id,
        target=probe.id,
        ok=True,
        data=data,
    ), warnings


def _relativize_text(text: str, cwd: Path) -> str:
    """Rewrite the probe's working directory to '.' inside captured output.

    Tracebacks and logs often embed absolute paths. In CI the baseline and
    the check run in two different checkout directories, so identical
    behavior would otherwise diff on the directory name alone. Storing the
    relative form keeps snapshots comparable and portable."""
    try:
        marker = str(cwd)
    except Exception:  # pragma: no cover - cwd is always a Path
        return text
    if not marker or marker not in text:
        return text
    return text.replace(marker + "\\", "./").replace(marker + "/", "./").replace(marker, ".")


def _read_trace(trace_path: Path, project_root: Path) -> tuple:
    """Parse the JSONL trace into (fs_writes, env_reads, db_queries,
    db_tables_written). Write paths under the project root are stored
    project-relative (portable snapshots, stable diffs); anything outside
    keeps its absolute form, where the normalizer's temp-path masking still
    applies at diff time. SQL records become normalized shapes with counts
    (data changes must never look like query-set changes)."""
    writes, envs = set(), set()
    queries: dict = {}
    try:
        text = trace_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return sorted(writes), sorted(envs), {}, []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        op = record.get("op")
        if op == "env":
            name = record.get("name")
            if name:
                envs.add(str(name))
        elif op == "sql":
            shape = sql_shape(str(record.get("sql") or ""))
            if shape:
                queries[shape] = queries.get(shape, 0) + 1
        elif record.get("path"):
            writes.add(_relativize(str(record["path"]), project_root))
    tables = set()
    for shape in queries:
        tables |= write_targets(shape)
    return sorted(writes), sorted(envs), dict(sorted(queries.items())), sorted(tables)


def _relativize(path: str, project_root: Path) -> str:
    try:
        return (Path(path).resolve().relative_to(project_root.resolve())).as_posix()
    except (ValueError, OSError):
        return path


def _watch_dir_entries(watch, project_root: Path) -> tuple:
    """All regular files below the watched directory, keyed by a stable
    relative posix path. A missing directory contributes nothing: if it exists
    at baseline but not at check, every file reports as deleted; if it only
    exists at check, every file reports as created. Walk order is sorted, so
    truncation at max_files is deterministic too."""
    root = (project_root / watch.path).resolve()
    if not root.is_dir():
        return {}, False
    prefix = str(watch.path).replace("\\", "/").strip("/")
    out = {}
    count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            d for d in dirnames
            if not _dir_ignored(d, _rel_posix(dirpath, root, d), watch.ignore)
        )
        for name in sorted(filenames):
            rel = _rel_posix(dirpath, root, name)
            if _dir_ignored(name, rel, watch.ignore):
                continue
            if count >= watch.max_files:
                return out, True
            key = f"{prefix}/{rel}" if prefix else rel
            out[key] = _file_entry(Path(dirpath) / name)
            count += 1
    return out, False


def _rel_posix(dirpath: str, root: Path, name: str) -> str:
    rel = Path(dirpath).joinpath(name).relative_to(root)
    return rel.as_posix()


def _dir_ignored(name: str, rel_path: str, ignore: list) -> bool:
    for glob in ignore:
        if fnmatch.fnmatch(name, glob) or fnmatch.fnmatchcase(rel_path, glob):
            return True
    return False


def _file_entry(path: Path) -> dict:
    if not path.is_file():
        return {"exists": False, "sha256": None, "size": None}
    content = path.read_bytes()
    return {
        "exists": True,
        "sha256": hashlib.sha256(content).hexdigest(),
        "size": len(content),
    }


def _resolve_interpreter(part: str) -> str:
    if part in ("python", "python3", "python.exe"):
        return sys.executable
    return part
