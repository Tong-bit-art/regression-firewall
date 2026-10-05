# Contributing to Regression Firewall

Thanks for helping make AI-driven code changes safer. This project holds
itself to a high bar: **deterministic, explainable, low-noise detection**.

## Development setup

```bash
git clone <your-fork>
cd regression-firewall
pip install -e ".[dev]"
```

Run the test suites:

```bash
python -m pytest tests            # unit + integration + eval suite
python -m evals.runner            # eval suite standalone with metrics table
```

## Project principles

1. **Verification first.** Never add an LLM call where deterministic code
   works. Detection, diffing, classification, and scoring stay in plain code.
2. **Low false positives.** A change that floods users with meaningless diffs
   is a failed change. If you touch detection, run the eval suite — the
   noise cases (06, 07, 14, 20) must stay clean.
3. **Explainability.** Every finding must answer: what changed, before,
   after, why it matters, was it requested, how confident are we.
4. **Minimal dependencies.** Any new runtime dependency needs a written
   justification in the PR: why, could stdlib do it, maintenance status,
   cross-platform story.
5. **No speculative abstraction.** Roadmap items do not justify unused
   interfaces in V0.x.

## Pull requests

- Keep PRs scoped; split large changes.
- `pyproject.toml` pins no linter yet — match the surrounding style:
  typed, explicit, small modules, no `except Exception: pass`, no silent
  fallbacks.
- Update docs when behavior changes:

| You changed... | Update... |
|---|---|
| detection/diff behavior | `docs/BEHAVIOR_MODEL.md`, relevant eval case |
| normalization | `docs/NORMALIZATION.md` + unit tests |
| scoring/verdicts | `docs/RISK_MODEL.md` + unit tests |
| CLI/config | `README.md` + config validation tests |

## Tests

- **Unit** (`tests/unit/`): normalizer, diff, risk, config, models.
- **Integration** (`tests/integration/`): full CLI loops per surface, via
  subprocess, like agents run it.
- **Evals** (`evals/cases/`): planted regressions with expected
  classification/severity/verdict.

## Reporting bugs

Include: OS, Python version, the config file, the command output, and —
most importantly — the baseline/latest snapshots (`.regression-firewall/`)
with any secrets redacted. A minimal repro project is even better, and the
best repro is a new eval case.

## A note on security-sensitive changes

Anything that affects the anti-gaming story (baseline handling, verdict
computation, config parsing that could silently weaken checks) will be
reviewed carefully. See `SECURITY.md` for reporting vulnerabilities.
