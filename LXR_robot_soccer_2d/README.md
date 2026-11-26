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

Close an animation window to stop it. Saving a GIF opens no window.

## Autonomous 4 v 4 prototype

The Python match extends the drill with two teams of one goalkeeper, two defenders and one
striker. Defenders guard separate lanes and clear nearby balls using their own percept. The
existing goalkeeper and striker control the other positions. Passing and attacker handover from
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
