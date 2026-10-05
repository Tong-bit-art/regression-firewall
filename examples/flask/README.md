# Flask example

Same idea as the FastAPI example, with Flask.

```bash
pip install "regression-firewall" flask
cd examples/flask

regression-firewall baseline
# ... change app.py (or have an agent do it) ...
regression-firewall check
```

Files:

- `app.py` — the example app (JSON API with a deliberate 404 case)
- `serve.py` — launcher honoring `REGFW_SERVER_PORT`
- `regression-firewall.yml` — HTTP probes
