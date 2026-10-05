# Regression Firewall — Risk Model

Version: 0.1 (2026-10-04)

Goals: **simple, explainable, testable, tunable**. No machine learning, no
opaque weights. Every verdict must be reconstructible by a human from the
report.

## 1. Inputs

Each `Change` contributes, depending on its classification:

- `EXPECTED` → contributes **0** (still listed in the report, as confirmation).
- `UNEXPECTED` → full contribution.
- `UNCERTAIN` → contribution × **0.6** (uncertainty discount).

Contribution = `POINTS[severity] × confidence`, where confidence comes from
the category class (structural diffs 0.95, value-level diffs 0.75,
reachability state changes 0.9) — see `BEHAVIOR_MODEL.md`.

## 2. Severity points

| Severity | Points | Rationale |
|---|---|---|
| INFO | 0 | Purely additive, no caller impact (e.g. new public symbol) |
| LOW | 4 | Cosmetic or additive detail; review only in aggregate |
| MEDIUM | 20 | Contract detail changed; usually survivable, must be looked at |
| HIGH | 34 | Likely caller-visible breakage (status flip, exit-code flip, removed field) |
| CRITICAL | 55 | Known hard breakage (removed public symbol) |

## 3. Score

```
risk_score = min(100, Σ contribution(change) for all non-EXPECTED changes)
```

Reported as `Risk Score: N / 100`.

## 4. Verdict rules (applied in order)

| # | Condition | Verdict |
|---|---|---|
| 1 | Any `UNEXPECTED` change with severity `CRITICAL` | **BLOCK** |
| 2 | Any `UNEXPECTED` change with severity `HIGH` and `thresholds.block_on_high: true` (default) | **BLOCK** |
| 3 | `risk_score ≥ thresholds.block_score` (default 70) | **BLOCK** |
| 4 | Any `UNEXPECTED` change with severity `MEDIUM` | **REVIEW** |
| 5 | Any `UNCERTAIN` change that is content-level (`stdout_changed`, `stderr_changed`, `header_changed`) or severity `MEDIUM+` | **REVIEW** |
| 6 | `risk_score ≥ thresholds.review_score` (default 30) | **REVIEW** |
| 7 | otherwise | **PASS** |

Purely additive uncertain changes (a new response field, a new public symbol)
do **not** force a REVIEW on their own — additive changes are the classic
false-positive trap. They still accumulate score and surface in the report.

**Score floors for consistency.** When a rule (not the raw score) triggers a
verdict, the reported score is floored to the corresponding threshold so the
number never contradicts the verdict (e.g. one CRITICAL change yields score
≥ 70). Floored scores are marked in the JSON report (`score_floored: true`).

## 5. Worked examples

| Changes | Score | Verdict |
|---|---|---|
| `field_added` LOW unexpected (4 × 0.95 ≈ 3.8) | 4 | PASS |
| `symbol_added` INFO uncertain | 0 | PASS |
| `header_changed` LOW uncertain (4 × 0.75 × 0.6 ≈ 1.8) | 2 (+floor 30) | REVIEW (rule 5) |
| `field_type_changed` MEDIUM unexpected (20 × 0.95 = 19) | 19 (+floor 30) | REVIEW (rule 4) |
| `status_changed` 401→400 HIGH unexpected (34 × 0.95 ≈ 32) | 32 (+floor 70) | BLOCK (rule 2) |
| `symbol_removed` CRITICAL (55 × 0.95 ≈ 52) | 52 (+floor 70) | BLOCK (rule 1) |
| Intent-matched rename (removed+added both EXPECTED) | 0 | PASS |

## 6. Configuration

```yaml
thresholds:
  review_score: 30
  block_score: 70
  block_on_high: true     # false ⇒ HIGH unexpected changes land in REVIEW instead

severity_overrides:       # key: "category" or "surface:category"
  header_changed: medium
  "http:field_added": low
```

Overrides apply to the *default* severity assigned by the diff stage; the
verdict rules are fixed (they encode the product's safety stance).

## 7. Recommended actions

Each category maps to a short, deterministic recommended action rendered in
the report ("Restore the previous HTTP status unless this API contract change
is intentional." etc.). The report always names the top-scoring change's
action first.
