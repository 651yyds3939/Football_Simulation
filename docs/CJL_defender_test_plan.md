# CJL · Task 4.3 Defender Test Plan (Round 1)

Covers CJL's tasks in the README team split: 3.1 pitch rules, 3.5 visualisation and batch runs, 4.3 defender.

## Code entry points
- `DefensivePlan.py`: `interception()`, `recovery_action()`
- `Flow.py`: `defend()`
- Rule checks: `CourseSpecs.py`, `MatchEngine.py` (goals, out of bounds, reset)

## Fixed test cases
| ID | Scenario | What to check |
|---|---|---|
| D1 | Opponent plays a through pass from midfield; defender beside the passing lane | Does the defender block the lane / intercept the pass |
| D2 | Defender has been dribbled past | `recovery_action()` recovery path and time to get back in position |
| D3 | Two defenders on the same side as the incoming ball | Clear split: one blocks the lane, one covers |
| D4 | Ball stops in front of our own penalty area | Does the defender clear it, or get stuck contesting with the goalkeeper |
| D5 | Tackle near the touchline | Out-of-bounds call and ball re-placement are correct |

## Commands (from the repository root)
    py -3 Four_vs_Four/run.py --seed 27 --language en --open
    py -3 Four_vs_Four/run.py --seed 27 --batch 20 --no-replay

On Ubuntu/macOS replace `py -3` with `python3`. After a batch run, check `Four_vs_Four/runs/match_*/metrics.json`. Compare before and after a change with the same seeds and the same time step.

## Results template
| Case | Seed | Time step | Before | After | Notes |
|---|---|---|---|---|---|
| D1 |  |  |  |  |  |
| D2 |  |  |  |  |  |
| D3 |  |  |  |  |  |
| D4 |  |  |  |  |  |
| D5 |  |  |  |  |  |
