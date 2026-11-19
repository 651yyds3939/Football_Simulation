# Four vs four evidence · 2026-11-19

Production entry: `../../Four_vs_Four/run.py`. Main report: `../../docs/FOUR_V_FOUR_TUNING_2026-11-19.md`.

- `baseline-app/`: starting backend snapshot; `production-app/`: frozen candidate snapshot.
- `selected-before-holdout.json`: pre-held-out freeze time and Python SHA256 hashes.
- `production-holdout.json`, `baseline-holdout.json`: 50 seeds120000–120049; each evaluated with swapped candidate colours.
- `failure-cases.json`, `failure-replay/replay.html`: worst congestion/stationary seeds, plus reproducible seed120013 baseline RED vs candidate BLUE losing0:1.
- `comparison.json`: comparison and seed-cluster bootstrap interval. Independent performance gain was not established.
- `experiment-index.json`: development and validation result index. Many configurations reuse seeds, so combined counts are not independent trials.
- `fine-step-sensitivity.json`, `coarse-step-sensitivity.json`: same four seeds, dt0.04 vs0.2; numerical sensitivity is material.
- `fine-validation-*.json`: additional frozen-policy fine-step check, seeds127000–127007.
- `selfplay-holdout.json`: ten independent self-play trajectories; swapped labels duplicate each trajectory.
- `test_tactics.py`: handoff, cover, unchanged executor/referee and unchanged 1v1 checks.
- `one-v-one-before.json`: pre-run hashes for every pre-existing 1v1 file except caches.
- `browser-check.json`: English/Chinese eight-player offline replay, controls and mobile layout.
- `package-check.json`: extracted standalone ZIP runs full matches from outside repository, renders replay, preserves existing output.

`evaluate.py --app ../../Four_vs_Four --mode candidate --seed 120000 --count 50 --output NEW.json` is interpreted relative to the current working directory. From the repository root, use `--app Four_vs_Four` and the full script path. Each output must be new.

The per-run field `candidate: baseline` originates from the base Simulation constructor and describes its built-in profile, not the injected policy. The top-level `mode`, `tuning`, source hashes and candidate_team describe actual experimental assignment. For delivery runs, `policies` explicitly labels both sides.

Exact-state 2D discs omit cameras, falls, balance and hardware. Contact and pass counters are proxies; issued actions are not automatically successful skills. No Git commits or pushes were made.
