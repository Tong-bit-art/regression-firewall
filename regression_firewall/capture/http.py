from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from ..config.schema import HttpSurfaceConfig
from ..models.snapshot import ProbeCapture
from .base import CaptureError


def capture_http_probes(cfg: HttpSurfaceConfig, project_root: Path,
                        artifacts_dir: Path, redaction=None) -> tuple:
    """Run HTTP probes. Optionally manages the configured server lifecycle.

    ``redaction`` is a config.RedactionConfig; secrets are masked in stored
    captures when enabled (the default).
    """
    redact_secrets = getattr(redaction, "secrets", True)
    warnings: list = []
    base_url = cfg.base_url
    server = None
    if cfg.server and cfg.server.command:
        server = ManagedServer(cfg, project_root, artifacts_dir)
        try:
            base_url = server.start()
        except CaptureError as exc:
            warnings.append(f"HTTP server could not be started: {exc}")
            return (
                [
                    ProbeCapture(
                        probe_id=probe.id,
                        target=probe.id,
                        ok=False,
                        error=f"server not reachable: {exc}",
                    )
                    for probe in cfg.probes
                ],
                warnings,
            )
    try:
        captures = [_run_probe(probe, base_url, redact_secrets) for probe in cfg.probes]
    finally:
        if server is not None:
            server.stop()
    return captures, warnings


def _run_probe(probe, base_url: str, redact_secrets: bool = True) -> ProbeCapture:
    url = base_url.rstrip("/") + probe.path
    body = _encode_body(probe)
    headers = {str(k): str(v) for k, v in (probe.headers or {}).items()}
    if body is not None and not any(k.lower() == "content-type" for k in headers):
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=body, headers=headers, method=probe.method)
    try:
        response = _opener(probe.follow_redirects).open(request, timeout=probe.timeout)
    except urllib.error.HTTPError as exc:
        response = exc  # a 4xx/5xx is a captured response, not a transport failure
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        reason = getattr(exc, "reason", None) or exc
        return ProbeCapture(probe_id=probe.id, target=probe.id, ok=False,
                            error=f"{type(reason).__name__}: {reason}")

    return _collect_response(probe, response, redact_secrets)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # makes the opener surface 3xx as HTTPError instead of following


def _opener(follow_redirects: bool):
    """Opener for probing local servers: proxies disabled (a macOS system
    proxy config would otherwise route 127.0.0.1 requests through it and
    break probes and readiness checks); redirects optionally surfaced as
    HTTPError so redirect behavior stays observable."""
    handlers = [urllib.request.ProxyHandler({})]
    if not follow_redirects:
        handlers.append(_NoRedirect)
    return urllib.request.build_opener(*handlers)


def _encode_body(probe):
    if probe.body is None:
        return None
    if isinstance(probe.body, (dict, list)):
        return json.dumps(probe.body, ensure_ascii=False).encode("utf-8")
    if isinstance(probe.body, (bytes, bytearray)):
        return bytes(probe.body)
    return str(probe.body).encode("utf-8")


def _collect_response(probe, response, redact_secrets: bool = True) -> ProbeCapture:
    try:
        status = int(getattr(response, "status", None) or getattr(response, "code"))
    except (TypeError, ValueError):
        status = 0
    raw_headers = response.headers

    headers: dict = {}
    cookies: dict = {}
    if raw_headers is not None:
        for name, value in raw_headers.items():
            low = name.lower()
            if low == "set-cookie":
                cookie_name, _, cookie_value = value.strip().partition("=")
                if cookie_name:
                    cookies[cookie_name.strip()] = cookie_value.split(";", 1)[0].strip()
                continue
            headers[low] = value if low not in headers else f"{headers[low]}, {value}"

    body_bytes = response.read() if hasattr(response, "read") else b""
    content_type = (headers.get("content-type") or "").lower()
    body, body_kind = _decode_body(body_bytes, content_type)

    from .. import redact

    return ProbeCapture(
        probe_id=probe.id,
        target=probe.id,
        ok=True,
        data={
            "status": status,
            "headers": redact.redact_headers(headers, redact_secrets),
            "cookies": redact.redact_cookies(cookies, redact_secrets),
            "body": redact.redact_json(body, enabled=redact_secrets),
            "body_kind": body_kind,
        },
    )


def _decode_body(body_bytes: bytes, content_type: str) -> tuple:
    if not body_bytes:
        return None, "none"
    if "octet-stream" in content_type or content_type.startswith("image/"):
        # Keep the size so content growth/shrink stays observable; the bytes
        # themselves are not stored.
        return {"size": len(body_bytes)}, "binary"
    text = body_bytes.decode("utf-8", errors="replace")
    if "json" in content_type:
        try:
            return json.loads(text), "json"
        except json.JSONDecodeError:
            return text, "text"
    return text, "text"


class ManagedServer:
    """Starts the configured server command, waits for readiness, stops it.

    The server receives the chosen port via the REGFW_SERVER_PORT environment
    variable (used when base_url contains ``{port}``). Startup output is
    captured to ``.regression-firewall/server.log``.
    """

    def __init__(self, cfg: HttpSurfaceConfig, project_root: Path, artifacts_dir: Path):
        self.cfg = cfg
        self.project_root = project_root
        self.log_path = artifacts_dir / "server.log"
        self._log = None
        self._proc = None
        self.port = None

    def start(self) -> str:
        base_url = self.cfg.base_url
        env = os.environ.copy()
        if "{port}" in base_url:
            self.port = _free_port()
            base_url = base_url.replace("{port}", str(self.port))
            env["REGFW_SERVER_PORT"] = str(self.port)

        command = [_resolve_interpreter(part) for part in self.cfg.server.command]
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        # Stale bytecode must never be served: a same-size, same-second edit
        # would otherwise pass pyc validation and produce a false PASS.
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        # Unbuffered so startup banners/tracebacks reach the log file even
        # when the process is later killed while still alive.
        env["PYTHONUNBUFFERED"] = "1"
        self._log = open(self.log_path, "w", encoding="utf-8")
        self._proc = subprocess.Popen(
            command,
            cwd=str(self.project_root),
            stdout=self._log,
            stderr=subprocess.STDOUT,
            env=env,
            # Detach from our process group: CI/TTY environments can deliver
            # group-wide signals (e.g. SIGTTIN/SIGTTOU stops a backgrounded
            # child) that leave the server alive but frozen.
            start_new_session=(os.name == "posix"),
        )

        deadline = time.monotonic() + self.cfg.ready_timeout
        ready_url = base_url.rstrip("/") + self.cfg.ready_path
        poll_opener = _opener(follow_redirects=True)
        while time.monotonic() < deadline:
            if self._proc.poll() is not None:
                exit_code = self._proc.returncode
                self.stop()
                raise CaptureError(
                    f"server exited during startup (exit code {exit_code}); "
                    f"log tail: {_log_tail(self.log_path)}"
                )
            try:
                poll_opener.open(ready_url, timeout=2)
                return base_url  # any response means the server is up
            except urllib.error.HTTPError:
                return base_url  # an error status still proves the server is up
            except (urllib.error.URLError, OSError, TimeoutError):
                time.sleep(0.25)

        diagnostics = _startup_diagnostics(base_url, self.port, self.log_path, self._proc.pid)
        self.stop()
        raise CaptureError(
            f"server did not become ready within {self.cfg.ready_timeout:g}s "
            f"(polling {ready_url}); {diagnostics}"
        )

    def stop(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait(timeout=5)
        self._proc = None
        if self._log is not None:
            self._log.close()
            self._log = None


def _resolve_interpreter(part: str) -> str:
    # Users write ["python", ...] in configs; pin it to the running
    # interpreter so probes exercise the same environment as the tool.
    if part in ("python", "python3", "python.exe"):
        return sys.executable
    return part


def _free_port() -> int:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _startup_diagnostics(base_url: str, port: int | None, log_path: Path,
                         pid: int | None) -> str:
    """Facts collected when readiness times out: child process state, raw-TCP
    reachability of the expected port, and the effective proxy config. This
    distinguishes 'child never started/bound' from 'child alive but frozen'
    from 'bound but unreachable above the TCP level'."""
    import socket
    import subprocess as _sp

    parts = [f"log tail: {_log_tail(log_path)}"]
    if pid is not None and os.name == "posix":
        try:
            ps = _sp.run(["ps", "-o", "stat=,command=", "-p", str(pid)],
                         capture_output=True, text=True, timeout=5)
            state = ps.stdout.strip() or "<process gone>"
            parts.append(f"child process: {state[:160]}")
        except (OSError, _sp.TimeoutExpired):
            pass
        if port is not None:
            try:
                lsof = _sp.run(["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"],
                               capture_output=True, text=True, timeout=5)
                listeners = lsof.stdout.strip().replace("\n", " | ") or "<no LISTEN socket on port>"
                parts.append(f"lsof: {listeners[:200]}")
            except (OSError, _sp.TimeoutExpired):
                pass
    if port is None:
        parts.append("port: external (no {port} template)")
        return "; ".join(parts)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2)
    try:
        sock.connect(("127.0.0.1", port))
        parts.append(f"raw TCP connect to 127.0.0.1:{port}: SUCCESS (listening; "
                     "readiness poll failed above the TCP level)")
    except OSError as exc:
        parts.append(f"raw TCP connect to 127.0.0.1:{port}: FAILED ({exc})")
    finally:
        sock.close()
    try:
        import urllib.request as _u

        parts.append(f"effective urllib proxies: {_u.getproxies() or 'none'}")
    except Exception:  # noqa: BLE001 - diagnostics must never break the error path
        pass
    return "; ".join(parts)


def _log_tail(path: Path, limit: int = 40) -> str:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return "<no log>"
    tail = lines[-limit:]
    return " | ".join(tail) if tail else "<empty log>"
