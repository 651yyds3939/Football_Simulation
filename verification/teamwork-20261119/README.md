# 2D four-player teamwork evidence · 2026-11-19

Main report: `../../docs/FOUR_V_FOUR_TEAMWORK_2026-11-19.md`. Delivery: `../../Four_vs_Four/`.

- `previous-app`: starting snapshot. `one-v-one-before.json`: 1v1 file integrity snapshot.
- `candidate-app`, `round2-app` ... `round7-app`: development snapshots. Wide advances, forced close passes and forced relief were rejected.
- `selected-app`: spacing-only finalist; frozen before seeds214000–214049, result34W31L35D; retained as an ablation, not final shipping source.
- `final-app`: guarded short-pass candidate frozen before seeds218000–218049; 31W32L37D,12 targeted attempts,11 intended receiver contacts,10 confirmed by foot-control events.
- `release-app`: shipping source; adds explicit phase, expiry and penalty guards around receiver staging. Frozen before fresh seeds222000–222029. 22W22L16D,6 targeted/receiver/foot receptions.
- `*-before-holdout.json`: timestamps and source hashes. No policy thresholds were retuned using the shipping holdout.
- `*-heldout-*.json`, `final-fine-*.json`: results including colour swaps; each seed's two colours are correlated. Self-reference colour swaps can duplicate trajectories.
- `experiment-index.json`: indexed development and verification configurations. Total logged runs are not independent trials.
- `release-comparison.json`: final statistics and seed-cluster bootstrap; competitive gain is not established.
- `test_release.py`, `tests-release.log`:18 checks. Simulator AST is identical after removing only pass metadata and coordinated-miss cancellation; carrier/navigation/referee source remains unchanged.
- `release-demo-en`, `release-demo-zh`: actual full-match examples with one controlled reception each. `pass-followup.json` shows subsequent turning/stalled progress; reception is not a successful attack.
- `browser-check.json`: both offline eight-player viewers, target coordinates, controls, mobile layout and zero external requests/errors.
- `package-check.json`: extracted archive runs outside repository from a path with spaces; standard full match, batch and output preservation checked.

Reproduce from repository root:

    python verification/teamwork-20261119/evaluate_final.py --app Four_vs_Four --seed 222000 --count 30 --mode candidate --output NEW.json

`--mode reference` uses the previous policy for both sides; `--opponent baseline` chooses the original TeamPolicy. Mode and source hashes define injected policy assignment; the inherited per-run `candidate: baseline` field only describes the base constructor profile, not the injected policy. For delivery scenes, `policies` explicitly labels both teams.

Perfect-state 2D kinematics do not validate cameras, falls, joint dynamics or hardware. Target arrows are actual decision outputs, not achieved motion. No Git commits or pushes were made.
