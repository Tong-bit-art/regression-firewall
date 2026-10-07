# Fresh Final Holdout

**Frozen implementation commit:** `8428a5b13cdd9d54807ee17a23ddbaef61173454`
**Frozen date:** 2026-10-07
**Status:** NOT YET RUN — will be run exactly ONCE

## Selection criteria

These repositories were selected because they have NEVER been used for:
- development of Regression Firewall
- debugging of Regression Firewall
- benchmark or mutation design
- rule adjustment or threshold tuning
- any prior validation or testing

## Repositories (frozen before first run)

| Repo | URL | Commit | License | Type | Surface |
|---|---|---|---|---|---|
| bottle | [bottlepy/bottle](https://github.com/bottlepy/bottle) | `cbd569c447` | MIT | Web framework (library) | public_api |
| urllib3 | [urllib3/urllib3](https://github.com/urllib3/urllib3) | `a164d79c8c` | Apache-2.0 | HTTP library | public_api |
| packaging | [pypa/packaging](https://github.com/pypa/packaging) | `2aada00b15` | Apache-2.0 OR BSD-2-Clause | Library | public_api |

## Mutation cases (frozen before first run)

Each repo has 5 cases: 3 controls + 2 planted regressions.
Ground truth was authored before the first run and stored in
`benchmarks/mutations/<repo>.yaml`.

| Repo | Control | Non-behavior | Symbol removed | Signature changed | Symbol added |
|---|---|---|---|---|---|
| bottle | ×3 | ✓ | ✓ (tob → _tob) | ✓ (makelist + separator) | ✓ (benchmark_added) |
| urllib3 | ×3 | ✓ | ✓ (encode_multipart_formdata) | ✓ (request + new_required_param) | ✓ (benchmark_added) |
| packaging | ×3 | ✓ | ✓ (parse → _parse) | ✓ (parse + strict) | ✓ (benchmark_added) |

## Rules

- This holdout is run EXACTLY ONCE.
- The original results are final, regardless of pass/fail.
- If a critical bug is found: fix it, report the ORIGINAL holdout result,
  move this holdout to the validation corpus, and select a NEW fresh holdout.
- Do NOT re-run after fixes and call it a holdout.
- Do NOT modify ground truth after seeing results.
