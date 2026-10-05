# CLI tool example

Watches a command-line tool's stdout, stderr, exit code, and generated files.

```bash
pip install "regression-firewall"
cd examples/cli

regression-firewall baseline
# ... change deploy.py (or have an agent do it) ...
regression-firewall check
```

Try asking an agent to *"make deploy fail fast when the environment is
unknown"* — then check whether the success path still exits 0, still prints
what scripts expect, and still writes `out/deploy_receipt.json`.

Note: run `regression-firewall baseline` from this directory so the
`out/` relative path matches.
