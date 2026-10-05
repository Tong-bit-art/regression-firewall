# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| 0.1.x | ✅ |

## Reporting a vulnerability

Open a [GitHub Security Advisory](https://github.com/security/advisories/new)
(private) rather than a public issue. Include a minimal reproduction and the
affected versions. You can expect a response within 7 days.

## Scope and design assumptions

Regression Firewall is a developer tool that **runs your project's code**:

- HTTP probes send real requests to the configured server (which the tool
  may start via `server.command`).
- CLI probes execute configured commands.
- Public-API probes import your Python package in a subprocess.

These are features, not vulnerabilities. Assumptions worth knowing:

1. **The tool does not sandbox your code.** Baseline/check run with your
   user's privileges. Never point it at untrusted code or production
   systems; use disposable environments for untrusted projects.
2. **Servers bound by probes accept local connections** when the tool
   manages them (`127.0.0.1` and a free ephemeral port via
   `REGFW_SERVER_PORT`).
3. **Snapshots are redacted, not encrypted.** With the default
   `redaction.secrets: true`, auth-related headers (Authorization,
   Proxy-Authorization, WWW-Authenticate, Cookie, and token-ish names), all
   cookie values, and body fields with secret-ish names
   (token/secret/password/session/api_key/...) are replaced with
   `<REDACTED>` before the capture is stored. Limitations: free-text
   stdout/stderr cannot be reliably scanned, so a CLI probe that prints a
   secret still stores it; and disabling redaction
   (`redaction.secrets: false`) restores raw storage by design. The
   `.regression-firewall/` directory is git-ignored by `init` — keep it
   that way.
4. **The tool trusts its own config files.** `.regression-firewall.yml` is
   executed-against (commands run, requests sent). Treat it like a Makefile:
   don't paste configs from strangers.

## Hardening guidance for integrators

- Run agents and the tool inside a container or devcontainer for untrusted
  work.
- Review `intent.json` and config diffs in PRs like any other code — the
  skill instructions forbid weakening config to pass checks, and review is
  the enforcement layer.
