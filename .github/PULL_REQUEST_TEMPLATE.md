## What

<!-- One paragraph: what this PR changes and why. -->

## How tested

<!-- Every detection-behavior change needs a test or eval case. -->

- [ ] `python -m pytest tests -q` passes locally
- [ ] New detection behavior is covered by a unit/integration test or an eval case (`evals/cases/`)
- [ ] Docs updated (README / docs/* / SKILL.md) if behavior or config changed

## Honesty checklist

- [ ] The report/verdict behavior is deterministic (no LLM in the pipeline)
- [ ] No change weakens a guard (re-baseline guard, post-hoc intent, no-evidence PASS floor) — if a guard *must* change, explain why in this PR
- [ ] CHANGELOG.md updated under [Unreleased]
