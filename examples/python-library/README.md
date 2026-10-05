# Python library example

Watches a library's public API surface: importable symbols, signatures,
`__all__`, and submodules.

```bash
pip install "regression-firewall"
cd examples/python-library

regression-firewall baseline
# ... refactor samplelib (or have an agent do it) ...
regression-firewall check
```

Removing `RetryPolicy` yields a CRITICAL `symbol_removed` and a BLOCK
verdict; adding a new function is informational and passes. Changing
`connect(host, port=5432)` to require `port` is a MEDIUM
`signature_changed` that needs review.

The full-featured `regression-firewall.yml` here shows every normalization
switch and threshold explicitly — most projects can omit them and use the
defaults.
