# Robot football simulation — Python version

**Status:** Python rewrite of the MATLAB code in the parent `code` folder. The MATLAB version stays
unchanged as the reference it is checked against. Every member using this code must be able to
explain how it works.

The simulation itself needs only the Python standard library (written for Python 3.10 or newer).
Figures and animations also need matplotlib, installed in a project environment in this folder:

```bash
python3 -m venv .venv
```

```bash
.venv/bin/python -m pip install -r requirements.txt
```

## How to run

From this folder (`code/python`). The self-checks, figures and animations use the project environment:

```bash
.venv/bin/python -m unittest discover -s tests
```

```bash
.venv/bin/python -m robot_soccer.simulations.striker_keeper_drill --animate
```

```bash
.venv/bin/python -m robot_soccer.simulations.striker_keeper_drill --animate --attackers 2 --speed 3
```

```bash
.venv/bin/python -m robot_soccer.simulations.striker_keeper_drill --attempts 2 --save drill.gif
```

```bash
.venv/bin/python -m robot_soccer.simulations.animate_sensor
```

```bash
.venv/bin/python -m robot_soccer.simulations.animate_sensor --speed 2 --save sensor.gif
```

```bash
.venv/bin/python -m robot_soccer.simulations.demo_pitch_ball --plot
```

```bash
.venv/bin/python -m robot_soccer.simulations.demo_sensor --plot
```

Results only, without any window:

```bash
python3 -m robot_soccer.simulations.striker_keeper_drill --attempts 20
```

```bash
python3 -m robot_soccer.simulations.striker_keeper_drill --attempts 20 --attackers 2
```

```bash
python3 -m robot_soccer.simulations.striker_keeper_drill --sensors perfect --keeper-sensors realistic
```

```bash
python3 -m robot_soccer.simulations.compare_sensor_settings --attempts 500 --seed 1
```

The drill and sensor comparison use `--keeper-design refined` by default. Use
`--keeper-design matlab` in either command to run the historical goalkeeper.

Close an animation window to stop it. Saving a GIF opens no window.

## Autonomous 4 v 4 prototype

The Python match extends the drill with two teams of one goalkeeper, two defenders and one
striker. Defenders guard separate lanes and clear nearby balls using their own percept. The
refined goalkeeper and striker control the other positions. Passing and attacker handover from
the two-attacker drill are disabled in this formation, which has a single striker per team.

```bash
.venv/bin/python -m robot_soccer.simulations.match --seconds 120 --seed 1
.venv/bin/python -m robot_soccer.simulations.match --seconds 30 --animate
.venv/bin/python -m robot_soccer.simulations.match --sensors perfect --kickoff-team 2
.venv/bin/python -m robot_soccer.simulations.match --control-design --seconds 120 --seed 1
```

The console lists goals and balls out of play, then prints the score and the number of kicks
that contacted the ball. The replay shows both teams, each robot's role and heading, and the
score. The default sensor setting models vision delay, noise and occlusion. `perfect` is a
comparison condition that supplies the true state through the same sensor interface.

After a goal, the conceding team kicks off from the reset formation. On other restarts, the
referee places the ball and gives a nearby player a short window to take a kick. Restart
procedures are simplified. This is the existing 2D motion model, with no Webots or NAO6
hardware integration yet. The MATLAB comparison below covers the original drills.

The combined walk/turn limit applies on every walking step in both modes. `--control-design`
enables local navigation around perceived players. See [the control design and verification](docs/control_design.md)
for parameter sources, role requirements and the targeted test command.

The [sensor design note](docs/sensor_design.md) traces the parameters to NAO6 specifications
or model assumptions and documents the drift check and sensor comparison.

## Goalkeeper save benchmark (GK-01)

From the Python project folder, run the MATLAB baseline against a stationary reference:

```bash
python3 -m robot_soccer.simulations.keeper_saves --attempts 500 --seed 1 \
  --sensors realistic --aim uniform --keeper-design stationary baseline
```

Set `--aim corner` for the striker-style far corner, `--sensors perfect` for the
idealised perception control, or give one keeper design for a single run. The shot hash
identifies the exact starts and launches for a given attempt count, seed and aim.
Use `--keeper-design baseline updated` to compare the historical keeper and the
GK-02–08 policy on those same shots.

- The shooter is fixed 0.30 m behind the ball, as a normal opponent in the sensor layer.
  The keeper has eight seconds to position and uses its own `Percept` and odometry.
  The report counts attempts in which the shooter was detected during setup. Either keeper
  starts 0.35 m in front of the goal centre. The stationary reference holds this position.
- Setup samples start distances of 1.0–2.3 m and angles of ±60° about the direction straight
  out from goal. Uniform aim draws the ball centre's target across the mouth, inset by a ball
  radius at each post. Corner aim uses ±0.95 m, away from the side of the baseline's nominal
  guard position on the ray from the goal centre to the ball. It uses the same reference in
  every run. Each nominal speed is drawn uniformly from the minimum for the **whole ball** to
  cross the line up to 2 m/s. Setups outside the reach of a 2 m/s kick are redrawn. The current
  ball rolls about 2.31 m at that speed, so the far-corner distance band near 2.3 m can be empty.
  Kick noise from `BallParams` (5° direction and 10% speed standard deviations) is applied
  once per shot when generating the replay list.
- The benchmark uses the 2D referee's whole-ball goal and out-of-play checks, with posts and
  nets in the physics. The keeper moves and kicks within the standard motion limits and blocks
  with its body. It is constrained by the carpet boundary and the shooter's position. The
  baseline attempts to clear close stationary balls in its penalty area. The attempt ends at
  a referee event or when the shot comes to rest, with no restart sequence.
- `cleared_early` is a keeper kick or body contact displacing the ball before launch.
  `goal` takes precedence over keeper contact after launch.
  `saved` is a keeper touch with no goal against it.
  Without a keeper touch, a ball out of play is `wide` and a ball that stops in play is
  `short`. A shot stopped in play by a post also counts as `short`.
  Save rate is `saved / (saved + goal)`. All five outcomes are reported overall and by
  distance, absolute start angle and launch speed after noise.
- The paired estimate is the second design's save rate minus the first's on shots eligible
  in both runs. The report also shows how many shots qualify in only one run. The 95% interval
  resamples complete pairs using a percentile bootstrap. The p-value uses the exact
  two-sided McNemar test on pairs with different results.
  [Percentile bootstrap](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html)
  and [exact McNemar test](https://www.statsmodels.org/stable/generated/statsmodels.stats.contingency_tables.mcnemar.html).

## Goalkeeper behaviour (GK-02–08)

`KeeperParams` is immutable and labels the source of each setting. `DEFAULT_KEEPER`
is the refined policy used by default in the striker–keeper drill, 4 v 4 match and
sensor comparison. In the save benchmark, `baseline` selects `MATLAB_KEEPER` and
`updated` selects `DEFAULT_KEEPER`. The MATLAB trajectory cross-check selects
`MATLAB_KEEPER` together with the historical motion configuration.

- **Guarding.** Place the keeper on the ray from goal centre to ball at a distance of
  `ball distance - gap` from goal, facing the ball. Clamp the distance along the ray so
  the target stays 0.5 m to `max_out` from goal, inside the penalty area and within
  ±1.2 m laterally. The bounds take precedence when the requested gap is infeasible.
  A missing ball estimate or an estimated ball centre more than one ball radius
  beyond the own goal line sends the keeper home. For the guard calculation,
  the ball's estimated depth in front of the goal line is floored at 0.05 m.
  GK-14 selected `gap = 0.5 m` and `max_out = 1.5 m`.
  The [goalkeeper evaluation](docs/keeper_evaluation.md) records the nine candidate settings
  and the independent GK-15 comparison with the MATLAB policy.
- **Intercepting.** `ball_path` gives the available rolling distance. If the ball's
  path reaches both the keeper's current estimated x-coordinate and the goal mouth,
  the keeper holds that x-coordinate and targets the crossing y. A path that has
  already passed the keeper's line, stops before the goal line or misses the mouth
  does not trigger interception. The prediction assumes straight rolling without bounces.
- **Clearing.** Challenge a ball inside the own penalty area when its estimated speed
  is below 0.5 m/s. Estimate travel time as distance divided by `RobotParams.v_forward`
  for both players, a baseline assumption because the percept contains no opponent
  heading or velocity. With a recent opponent, the keeper must reach the ball at
  least 0.5 s sooner to start clearing. At the default forward speed of 0.25 m/s,
  the keeper must therefore be at least 0.125 m nearer the ball. The 0.8 m clearance
  radius applies to the MATLAB baseline. Once clearing, give up the race if an
  opponent leads by more than 0.5 s. The ball location and speed conditions continue
  to apply, and a shot takes priority. The keeper uses all opponent positions seen within the last 2 s of
  measurement time and may go when none are recent. As observations have no player
  IDs, the nearest position can be a recent sighting of a player who has since moved.
- **Limitations.** The keeper uses `Percept` and its own odometry and keeps the
  `home`, `guard`, `intercept` and `clear` states. This version blocks with its
  walking body model and leaves diving and split-leg saves for a later phase.
  The outcome of a body block depends on `BallParams.e_robot = 0.3`, which
  `ball.py` marks as `[CHECK]`.
  The shared `track_ball` estimator is also used by the striker. With the current
  sensor parameters, the single-frame range standard deviation at 1.5 m is 0.105 m.
  Independent range errors across two frames spaced 0.1 s apart would give a speed
  standard deviation of about 1.5 m/s, so this design uses the existing multi-frame fit.

## Goalkeeper rules and model constraints (GK-09 / BEH-08)

The ENG5325 Project Specification (pp. 1–3, Table 1 and Appendix A) gives the
goalkeeper's role, the KidSize pitch dimensions and the competition rules used
here. Appendix A cites the [2025 RoboCup Humanoid League rulebook](https://humanoid.robocup.org/wp-content/uploads/RC-HL-2025-Rules.pdf).

1. **Activity area and goalkeeper privileges.** In open play the designated goalkeeper
   may leave its own penalty area. Inside that area, Law 12 permits goalkeeper-specific
   use of the hands and arms, subject to ball-holding and hand-contact restrictions such
   as the deliberate pass-back rule. Outside it, the ordinary hand-contact restrictions
   apply. Law 14 sets a separate pre-kick position for a goalkeeper defending a penalty.
   [Rules, Laws 1, 3, 12 and 14](https://humanoid.robocup.org/wp-content/uploads/RC-HL-2025-Rules.pdf)

   The 2D policy uses the 2 m deep, 5 m wide penalty area in
   [`PitchParams`](robot_soccer/environment/pitch.py). In
   [`goalkeeper.py`](robot_soccer/behaviours/goalkeeper.py), `_guard_target`
   keeps the guard target inside that area and within ±1.2 m laterally.
   `_can_claim` requires the estimated ball position to be inside the area before
   starting or continuing a clearance. Interception holds the current estimated
   depth and clearance uses the shared ball-approach routine. Robot motion and
   collision correction enforce the carpet boundary, so the penalty-area checks
   do not constrain the goalkeeper's actual position in every state. The model
   uses body blocks and foot kicks. It has no handling, ball-holding or penalty-kick procedure.

2. **Clearance direction.** The goalkeeper requests a kick away from its own goal
   with a sideways component. [`ball_kick`](robot_soccer/environment/ball.py)
   applies the same reach and front-cone checks as for the other players. It caps
   the requested kick direction at `BallParams.kick_dir_max = 45°` either side of
   the robot's heading, then adds directional noise. The simulated outgoing
   angle can therefore exceed ±45°. The command cap is a baseline motion-model assumption.

3. **Restarts.** The official referee determines the restart and the team entitled
   to take it. After a goal, the conceding team kicks off. Law 8 requires players
   to start in their own halves and opponents to stay outside the centre circle
   until the ball is in play. Laws 13 and 15–17 specify placement and procedures
   for free kicks, throw-ins, goal kicks and corners.
   [Rules, Laws 5, 8–10, 13 and 15–17](https://humanoid.robocup.org/wp-content/uploads/RC-HL-2025-Rules.pdf)

   [`referee_step`](robot_soccer/environment/referee.py) decides the restart type,
   team and ball position after the whole ball crosses a boundary. In the 4 v 4
   match, [`_prepare_restart`](robot_soccer/simulations/match.py) selects the
   entitled team's striker for kick-off and the eligible player closest to the
   run-up spot for other implemented restarts. This can be the goalkeeper.
   `play_match` issues zero commands to other players until the taker contacts
   the ball or 12 s elapse. These are simplified match procedures. For example,
   the model places goal kicks at the near-side corner of the goal area, while
   Law 16 specifies the touchline at halfway on the side where the ball went out.
   GK-01 ends at the shot outcome and does not simulate the ensuing restart.

4. **Collisions and pushing.** Law 12 provides for forceful-contact fouls and uses
   a separate contact test in virtual matches. The text gives an exception for
   the designated goalkeeper chasing the ball inside its own penalty area.
   [Rules, Law 12 and Figure 4](https://humanoid.robocup.org/wp-content/uploads/RC-HL-2025-Rules.pdf)

   In the match and drill, [`keep_apart`](robot_soccer/robot/motion.py)
   separates overlapping robot discs equally along the line between their
   centres. In GK-01, the shooter stays fixed and an overlapping keeper is
   blocked. The model applies no pushing foul or fall consequence. This may
   overestimate the benefit of an aggressive challenge because it omits the
   risk of destabilisation and of conceding a restart for illegal contact.

## Where each MATLAB file went

| Python module (`robot_soccer/`) | MATLAB files |
|---|---|
| `geometry.py` | `wrap_angle`, `to_body` and small vector helpers |
| `environment/pitch.py` | `pitch_params`, `goal_geometry` |
| `environment/ball.py` | `ball_params`, `ball_step`, `ball_kick` |
| `environment/referee.py` | `referee_step` |
| `environment/world.py` | `world_init`, `world_step` |
| `sensors/params.py` | `sensor_params` |
| `sensors/percept.py` | `empty_percept` |
| `sensors/sensor_layer.py` | `sensor_init`, `sensor_step`, `sense_once`, `update_percept`, `perfect_percept`, `head_control` |
| `robot/motion.py` | `robot_params`, `robot_state_init`, `robot_step`, `walk_cmd`, `keep_apart` |
| `behaviours/ball_prediction.py` | `ball_path`, `track_ball`, `intercept_point`, `pass_speed` |
| `behaviours/approach.py` | `approach_ball`, `odometry_update` |
| `behaviours/striker.py` | `striker_behaviour` |
| `behaviours/goalkeeper.py` | `goalkeeper_behaviour` |
| `simulations/striker_keeper_drill.py` | `striker_keeper_drill` |
| `simulations/compare_sensor_settings.py` | `compare_sensor_settings` |
| `simulations/demo_pitch_ball.py` | `demo_pitch_ball` |
| `simulations/demo_sensor.py` | `demo_sensor` |
| `simulations/animate_sensor.py` | `animate_sensor` |
| `visual/pitch_view.py` | `draw_pitch` |
| `visual/plots.py` | the figures of `demo_pitch_ball` and `demo_sensor` |
| `visual/animation.py` | the animations of `animate_sensor` and `striker_keeper_drill` |

Only the `visual` folder uses matplotlib, and it is loaded only when something is drawn.

## Differences from the MATLAB version

- Robot indices start at 0, and `ball.last_touch_robot` is `None` when nobody has touched the ball.
- Functions update the ball, robots and world in place instead of returning new copies.
- Random numbers come from an `rng` argument. Python and MATLAB draw different random numbers, so
  a single random run differs between them; the statistics agree (see below).
- The drill runs without a window unless `--animate` or `--save` is given, and GIFs of the drill
  are saved with `--save` (MATLAB's GIF saving applied only to `animate_sensor`).
- Walking and turning together are limited on the speed actually used in each step. MATLAB scales
  the command into the walk limit before the acceleration limit, so a robot that is still slowing
  down or changing direction can walk and turn faster together than the limit allows. Python gives
  turning only the share left by the current walking speed. `RobotParams(strict_walk_limit=False)`
  restores the MATLAB behaviour; the trace comparison uses it.
- The self-localisation drift uses the actual time between two images, `exp(-Δt/loc_tau)`, where
  MATLAB uses the nominal `update_period`. At the default 0.02 s step the images are 0.1 s apart and
  both give the same results. With a step longer than `update_period`, the images are one step
  apart and the MATLAB formula keeps too much of the old error: at a 0.2 s step the 1 s correlation
  is 0.768 instead of the intended 0.607.

The values of the ported model are the same as in MATLAB. In Python, `[CHECK]` placeholders remain
only in `environment/ball.py` and `environment/pitch.py`. The sensor and motion values state their
source or assumption in the comments, and [the sensor design note](docs/sensor_design.md) traces
the sensor values. `[RULE]` marks the simplified rules in `environment/referee.py`. See the READMEs
in `../environment`, `../sensors`, `../robot` and `../behaviours` for what each one means in the
MATLAB version.

## How the port was checked

The comparisons with MATLAB describe the original port. The trace comparison explicitly selects the
historical walk limiter. Both Python match modes use the updated per-step limiter by default.

| Check | Result |
|---|---|
| All 72 self-checks in `tests`: the 49 ported from MATLAB, plus 23 added in Python (3 MATLAB trace comparisons, 8 drawing checks, 1 drift check, 8 control checks, 3 match checks) | all pass |
| 12 noise-free scenarios compared with MATLAB every 0.5 s (471 samples: positions, headings, ball, behaviour states) | largest difference 9e-15; no state or outcome differs |
| Deliberate errors (walk speed +1 %, rolling drag +1 %, field of view +1°) | all detected by the comparison |
| Goal rate with noise on, 1000 attempts per setting, six settings | within chance of MATLAB (largest gap 3.0 points, z = 1.8) |
| 8 checks of the drawing code: pitch lines against Table 1, figures, GIFs, stopping early | all pass; watching a drill does not change its results |

`tests/golden/make_matlab_traces.m` regenerates the MATLAB reference file
`tests/golden/matlab_traces.json`. Run it again whenever the MATLAB model changes on purpose.

## Using other people's code

This code is an independent rewrite: nothing in it is copied from the team's Webots repository or
from any earlier project. If an idea, a measurement or code is taken from another source later,
record it here, so that the report can state the source accurately.

| Date | What was used | Source (repository, commit, file) | Where it is used | Who checked it |
|---|---|---|---|---|
| | | | | |
