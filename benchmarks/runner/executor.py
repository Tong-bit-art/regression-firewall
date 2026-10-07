"""Benchmark isolation executors.

DockerExecutor is the REQUIRED isolation for untrusted code; this machine has
no Docker, so the benchmark runs on LocalExecutor with a scrubbed environment
and hard timeouts, and every result records the weaker isolation honestly.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

STEP_TIMEOUTS = {
    "clone": 300,
    "setup": 900,
    "command": 300,
    "case": 600,
}

# Environment passed to untrusted child processes: allowlisted essentials
# plus network configuration (dependency installation needs the proxy on
# this host). Everything that could carry credentials is dropped.
_ENV_ALLOWLIST = (
    "PATH", "TEMP", "TMP", "SYSTEMROOT", "COMSPEC", "PATHEXT",
    "SYSTEMDRIVE", "HOMEDRIVE", "HOMEPATH", "APPDATA", "LOCALAPPDATA",
    "PROGRAMFILES", "WINDIR",
    "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "http_proxy", "https_proxy",
    "no_proxy", "ALL_PROXY", "all_proxy",
)


def scrubbed_env() -> dict:
    env = {k: v for k, v in os.environ.items() if k in _ENV_ALLOWLIST}
    env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    # Belt and braces: drop anything that still smells like a credential.
    for key in list(env):
        upper = key.upper()
        if any(marker in upper for marker in
               ("TOKEN", "SECRET", "PASSWORD", "PASSWD", "CREDENTIAL", "API_KEY")):
            env.pop(key)
    return env


@dataclass
class StepResult:
    ok: bool
    exit_code: int
    stdout: str
    stderr: str
    timeout: bool = False


def run_step(argv: list, cwd: Path, phase: str = "command",
             env: dict | None = None) -> StepResult:
    """Run one command with the benchmark's scrubbed env and hard timeout."""
    try:
        proc = subprocess.run(
            argv, cwd=str(cwd), env=env or scrubbed_env(),
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=STEP_TIMEOUTS[phase],
        )
        return StepResult(proc.returncode == 0, proc.returncode,
                          proc.stdout, proc.stderr)
    except subprocess.TimeoutExpired as exc:
        return StepResult(False, -1, (exc.stdout or b"").decode("utf-8", "replace")
                          if isinstance(exc.stdout, bytes) else (exc.stdout or ""),
                          (exc.stderr or b"").decode("utf-8", "replace")
                          if isinstance(exc.stderr, bytes) else (exc.stderr or ""),
                          timeout=True)
    except OSError as exc:
        return StepResult(False, -1, "", f"{type(exc).__name__}: {exc}")


class LocalExecutor:
    """Direct execution on this machine with a scrubbed environment.

    SECURITY LIMITATION: no filesystem, process, or network isolation from
    the host. Only suitable for well-known, well-audited repositories on a
    disposable machine. Results record this honestly.
    """

    name = "local-scrubbed-env"

    def run(self, argv: list, cwd: Path, phase: str = "command") -> StepResult:
        return run_step(argv, cwd, phase)

    def run_with_env(self, argv: list, cwd: Path, phase: str = "command",
                     env: dict | None = None) -> StepResult:
        # env must already be a scrubbed allowlist; the runner merges
        # repo-level variables (e.g. ALLOWED_HOSTS) into it.
        return run_step(argv, cwd, phase, env=env)


class DockerExecutor:
    """Container isolation — interface reserved; NOT implemented because
    Docker is unavailable on this machine. The runner refuses to pretend."""

    name = "docker"

    def __init__(self, image: str, mem_limit: str = "2g", cpus: str = "2",
                 network_enabled: bool = False):
        raise NotImplementedError(
            "DockerExecutor is not available in this environment; "
            "SECURITY LIMITATION recorded in docs/BENCHMARK_DESIGN.md"
        )


def get_executor() -> LocalExecutor:
    return LocalExecutor()
