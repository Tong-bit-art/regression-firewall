# FastAPI example

An example project for exercising Regression Firewall against a FastAPI app.

```bash
pip install "regression-firewall" fastapi uvicorn
cd examples/fastapi

regression-firewall baseline
# ... ask your AI agent to change something (or edit app.py yourself) ...
regression-firewall check
```

Try asking an agent to *"add account lockout to the login endpoint"* and
watch what happens to `GET /users/43` (which intentionally 404s) or the
error payload of `POST /login`.

Files:

- `app.py` — the example app (two routes, one deliberate 404 case)
- `serve.py` — launcher honoring `REGFW_SERVER_PORT` so the tool can manage
  the server lifecycle
- `regression-firewall.yml` — probes for both routes plus a bad-credentials
  login
