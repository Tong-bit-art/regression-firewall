# Fresh Holdout V0.4 — datasette / pluggy / more-itertools

Status: **executed 2026-10-26** (runs 1–2, Windows 11, Python 3.11.9)
Tool version: main @ `047d786` (V0.5 + V0.6 on top of v0.3.0; version not yet
bumped — this holdout gates the 0.4.0 release) **plus one CORE BUG fix made
between run 1 and run 2** (see ledger). This corpus is now **consumed**.

## Corpus

Frozen in `benchmarks/manifest-holdout-v04.yaml` BEFORE the first run.
Disjoint from all 17 previously used repos.

| Repo | Pinned commit | License | Surfaces | Why |
|---|---|---|---|---|
| datasette | `a8e13cc489b4` | Apache-2.0 | HTTP (managed serve) + CLI + **trace.sqlite** + **performance** + **--select** | real SQLite web platform: JSON API probes on a deterministic database, `inspect` exercises 10 real internal query shapes under the tracer |
| pluggy | `ba2eaa2f76ce` | MIT | public API (src layout) | `__all__` + explicit-import removal semantics |
| more-itertools | `4aeb4338ae14` | MIT | public API | star-import + `__all__` semantics (removal touches namespace only) |

Authoring validation BEFORE freezing (repo-side, no detection runs):
datasette `inspect` output byte-identical across runs; sqlite trace caught
10 real shapes; `/data.json` and `/data/users.json` verified deterministic;
both API repos' `__all__`-removal mutations verified to cleanly remove the
symbol while the import survives.

Benchmark infrastructure gained `check_args` (per-case extra check
arguments, used for `--select`) and `skipped_probes_min` (asserts the
report's selective-skip count), both with evaluator tests.

## Final result (run 2, POST-FIX VALIDATION)

| Metric | Value |
|---|---|
| Cases ran to verdict | 23 / 23 |
| Detection recall | **100%** (10/10 planted regressions) |
| False-positive rate | **0%** (13/13 controls clean) |
| Severity accuracy | 100% |
| Verdict accuracy | 100% |
| Setup / infra / mutation failures | 0 |

Highlights validated on real code: a query injected into datasette's
`inspect` internals detected as `db_query_added` (V0.4); a 2s injected
sleep detected as `runtime_regressed` against the median-ratio budget
(V0.6); with `--select`, a package-internal change still ran both CLI
probes and was detected, while a README-only change skipped all four probes
and was held at REVIEW by the empty-capture guard (V0.5, both directions).

## Run history (honest ledger)

**Run 1 — first execution (2026-10-26).** 16/23 PASS; 6 failures:

| Item | Class | Root cause |
|---|---|---|
| `ds_select_touch_package` / `ds_select_untouched` crashed (no report) | **CORE_BUG** | **V0.5 selection crashed on environment paths**: probe commands rendered with `{venv_python}` put an absolute interpreter path outside the project into the dependency set, and `relative_to(project_root)` raised. Fixed in `selection.py`: the interpreter token (command[0]) and absolute tokens are no longer treated as project dependencies, and out-of-project dependency labels keep their absolute form instead of crashing (+2 regression tests). |
| `ds_10` MUTATION_FAILURE | BENCHMARK_ERROR | find-string did not match `__main__.py` (missing the `if __name__` guard) |
| `ds_11` no detection | BENCHMARK_ERROR | patched a subcommand option's help text, which the top-level `--help` output does not contain; patched the CLI docstring instead (visible in top-level help) |
| `mi_15` / `mi_16` missing `export_changed` | BENCHMARK_ERROR | `more_itertools` (the package) has no `__all__` of its own — only the namespace changes, so the single `symbol_removed` / `symbol_added` expectation was correct all along (pluggy, which has `__all__`, produced the expected double change and passed) |

**Run 2 — POST-FIX VALIDATION.** **23/23 PASS**, all metrics 100%. The
tool-side change is limited to `selection.py` + its regression tests.

## Findings summary

| # | Class | Item |
|---|---|---|
| 1 | `CORE_BUG` (fixed + tested) | V0.5 selection crashed on venv-interpreter paths in probe commands |
| 2–5 | `BENCHMARK_ERROR` | find-string mismatch; help text not in top-level output; `__all__` semantics misjudged for a star-import package; benchmark evaluator needed the new `selection` visibility |
| 6 | `CORE_BUG` | **none beyond #1** |

## Reproduce

```bash
cp benchmarks/manifest-holdout-v04.yaml benchmarks/manifest.yaml
REGFW_BENCH_WORKSPACE=C:/regfw-bench python -m benchmarks.runner --split holdout
cp benchmarks/manifest-validation-backup.yaml benchmarks/manifest.yaml
```
