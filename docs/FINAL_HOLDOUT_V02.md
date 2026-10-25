# Fresh Holdout V0.2 — tqdm / attrs / black

Status: **executed 2026-10-25** (runs 1–4, Windows 11, Python 3.11.9)
Tool version: **0.2.0** (commit `09dbe56`) — `regression_firewall/` was not
modified between the v0.2.0 tag and any of these runs (verified by
`git status`); only benchmark infrastructure and case authoring changed.
This holdout is now **consumed**: the next release cycle needs a new corpus
(repos disjoint from all 14 previously used).

## Corpus

Selected 2026-10-25, frozen in `benchmarks/manifest-holdout-v02.yaml`
BEFORE the first run. Disjoint from all 11 previously used repos.

| Repo | Pinned commit | License | Surfaces | Why |
|---|---|---|---|---|
| tqdm | `9cf5a12b1f95` | MIT | CLI, public API | zero-dep CLI tool |
| attrs | `c8bb9bfaa284` | MIT | public API (src/ layout) | re-validates src-layout capture on a new repo |
| black | `80db630ac532` | MIT | CLI + **V0.2 directory watch** | formatter CLI; setup-replayed sample dir |

Coverage honesty: **HTTP is not covered** — V0.2 modified no HTTP capture or
diff code (`capture/http_probe.py`, `diff/http.py` untouched since v0.1.0);
HTTP detection was validated on the V0.1 corpus (flaskr, healthchecks). The
V0.2 OpenAPI-import feature is not exercised here (none of these repos ships
an OpenAPI document); it is covered by unit, config-integration, and CLI
tests. The directory-watch path — the V0.2 capture change — IS covered
(black, incl. the setup-replay of a generated sample dir).

## Final result (run 4, POST-FIX VALIDATION)

| Metric | Value |
|---|---|
| Cases ran to verdict | 26 / 26 |
| Detection recall | **100%** (12/12 planted regressions) |
| False-positive rate | **0%** (14/14 controls clean) |
| Severity accuracy | 100% |
| Verdict accuracy | 100% |
| Setup / infra / mutation failures | 0 |

Isolation: `local-scrubbed-env` (**SECURITY LIMITATION**: no Docker on this
machine). Full per-case detail: `benchmarks/results/latest.json` (run 4) —
numbers are computed by the runner, never hand-written.

## Run history (honest ledger)

**Run 1 — first execution (2026-10-25).** 18 cases evaluated, all PASS, no
detection failures. Abort: the evaluator crashed on `black_13` (ground truth
used a `path` field `ExpectedEntry` did not support — benchmark-infra bug,
`TypeError`); black_14 never ran. Infra finding, no tool involvement.

**Run 2 — after infra/authoring fixes (POST-FIX VALIDATION).** Fixes between
run 1 and 2, none in `regression_firewall/`:
- `build_wheel` now purges stale wheels from the workspace `dist/` (a 0.1.0
  wheel from a previous session silently won the glob in the aborted
  pre-run — benchmark would have tested the wrong tool version);
- `ExpectedEntry` gained the `path` field (+ regression tests);
- `tqdm_15` find-string typo fixed (authoring error: omitted `TqdmWarning, `);
- `black_13` (DEFAULT_LINE_LENGTH 88→89) **revoked as BENCHMARK_ERROR**:
  black's format cache keys on the target file, so a formatter-constant
  mutation never triggers a reformat — the generated file genuinely does not
  change and the tool's clean PASS was CORRECT (verified manually). Replaced
  by `black_13b` (generated file inside the watched directory).
  Result: 25/26 PASS; `black_13b` recorded REGRESSION_FIREWALL_FAILURE.

**Run 3.** `black_13b` still failed identically → re-classified: the second
expected entry (file_created on the `version` probe) was impossible by
construction — the manifest gives the `dirs` watch to the `fmt` probe only.
Ground truth corrected to the single fmt entry (authoring error; the tool
had detected exactly the one change that could exist). Additionally found a
real benchmark-infra leak: `clean_excludes: [bench_sample]` let run 2's
generated artifact survive `git clean -fdqx` into run 3's baseline, which
genuinely left nothing to detect. Fix: dropped the exclude (setup reapply
recreates the sample dir after every restore — that is what it is for).

**Run 4 — final (POST-FIX VALIDATION).** Fresh black clone; **26/26 PASS**,
all metrics 100%. No tool-code changes across any run.

## Findings summary

| # | Root cause class | Item |
|---|---|---|
| 1 | `BENCHMARK_ERROR` | black formatter cache shields source-constant mutations (probe design) |
| 2 | `BENCHMARK_ERROR` | impossible expectation: file_created on a probe without a dirs watch |
| 3 | `BENCHMARK_ERROR` | find-string typos (tqdm import list) |
| 4 | `BENCHMARK_ERROR` | clean_excludes leaked generated state across cases/runs |
| 5 | `INFRASTRUCTURE` | stale wheel in persistent workspace dist/ won the glob (now purged) |
| 6 | `INFRASTRUCTURE` | evaluator lacked `path` in ground-truth entries (now supported + tested) |
| 7 | `CORE_BUG` | **none found** |

V0.2 detection behaved correctly in every observed disagreement. The one
behavior worth noting (not a bug, consistent with docs): files generated
inside a watched directory are detected per-probe; probes without a `dirs`
config see nothing.

## Reproduce

```bash
cp benchmarks/manifest-holdout-v02.yaml benchmarks/manifest.yaml
REGFW_BENCH_WORKSPACE=C:/regfw-bench python -m benchmarks.runner --split holdout
cp benchmarks/manifest-validation-backup.yaml benchmarks/manifest.yaml
```

Workspace must be ASCII-only (editable installs write raw paths into .pth
files). Clones and venvs are reused across runs; delete
`C:/regfw-bench/repos/<id>` and `C:/regfw-bench/venvs/<id>` for a fully
fresh run.
