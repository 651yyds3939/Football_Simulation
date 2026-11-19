# Model sources and behaviour

## Course geometry

The course project specification (2026–27), p. 3, supplies the 9 × 6 m pitch, 1 m border, goal width 2.6 m, height 1.2 m, depth 0.6 m, goal area 1 × 3 m, penalty area 2 × 5 m, centre-circle diameter 1.5 m, penalty-mark distance 1.5 m and approximate 0.14 m ball diameter. The drawing is a top view; height is not simulated. The original project stores geometry in `Wenao/controllers/Utils/CourseSpecs.py`.

This is an attack-versus-defence exercise, not a full match referee or a statement of complete course-rule compliance. Red always attacks the right goal. The goal test interpolates the first whole-ball boundary crossing and checks the opening. A goal, out-of-play or timeout ends the round. Clearance is a logged event and play continues. Optional automatic continuation starts a new random round after a 3-second result display.

## Motion and ball values

Parameters are embedded in `index.html` and documented with source hashes in `model_parameters.json`. No original repository files are required at run time.

- Forward/backward and lateral rates come from the existing isolated Webots tests in `verification/development/navigation/motion-result.json`, using directional displacement divided by 8 s.
- Turn rates use the `left20`/`right20` test yaw changes divided by 4 s.
- Shot duration 4.800 s and clearance duration 3.299 s reuse the configured final timestamps of `Shoot.motion` and `LongPass.motion`. These are not measured total skill-completion times; the latter file's first pose is at 0.100 s.
- Shot/pass distance parameters reuse single-fixture maximum ball displacements from `verification/development/navigation/skills-result.json`. The pass fixture included receiver contact, so its displacement is not a calibrated free-rolling range.
- Disc radius 0.15 m, rolling deceleration 0.35 m/s² and direction noise 0.04 rad are assumptions retained from `tools/soccer2d.py`. The 1v1 contact response is a separate planar approximation using a 0.35 velocity response factor.
- The 0.04 s fixed integration step, 180 s attempt duration, initial scenes and clearance outcome threshold are explicit choices for this demo. They are not course-prescribed match timing or hardware measurements.

## Independent state policies

Attacker: **APPROACH → ALIGN → DRIBBLE → SHOOT**, with feedback to approach or align when contact geometry is lost. It chooses a lane at setup, targets the ball from behind, moves through disc contact, and only attempts a shot near the right goal. Entry and exit tolerances differ to limit near-ball alignment chatter. A shot is an attempt until the wind-up completes with the ball still within the modelled foot gate.

Defender: **INTERCEPT → BLOCK → CLEAR**, with feedback to interception if the ball moves away. It targets a point between the ball and the right goal, faces left and attempts a clearance only when the ball is within reach. A clearance is counted after a defender kick contact and subsequent leftward ball travel of 0.18 m; it does not end the scene.

Both state policies run at every fixed simulation step using exact state. They are newly implemented here and are not equivalent to the original `TeamPolicy.py`, `Navigation.py` or any trained controller. Seeded kick-direction noise is deterministic. State changes, kick attempts, successful kick contacts, manual setup edits and final outcomes are logged separately. `robotContactSteps` counts simulation steps with body overlap resolution, not distinct collision events.

## Random starts and reproducibility

The random scene samples ball x in [-1.5, 2.4] m and y in [-1.45, 1.45] m. The attacker starts 0.25–0.35 m behind the ball, with a small heading variation. The defender starts 0.45–1.95 m ahead with a lateral offset up to 1.4 m, clipped to remain on the pitch, and faces the ball. The initial attacking lane is selected away from the defender's starting side. These ranges are test choices, not course requirements.

The browser obtains a new seed for each new random start, while all model draws use a deterministic PRNG. The seed and exact starting states are exported. **Repeat seed** reproduces the random starting state and noise. **New random setup** changes both the initial geometry and seed. Fixed fixtures still use fixed geometry, so changing only their seed need not change the outcome class. No success/failure outcome is selected randomly or assigned in advance.

The default playback multiplier is 2×. This replaces the initial version's 8× multiplier and single-clearance termination, which made a fixed fixture look like a very short repeated clip.

## Limits and presentation wording

This demo is suitable for explaining a two-player feedback loop, testing simple initial positions, and displaying state transitions quickly. Playback acceleration changes wall time without increasing simulated speeds. It is a live model rather than a recorded clip.

It does not simulate legs, balance, falls, joint dynamics, ball flight, camera detection, communication delay, fouls or full RoboCup match rules. Source measurements plus assumed contact dynamics do not establish real-robot performance. A visible successful goal is evidence for this planar fixture only, not a general 1v1 success rate or 4v4 improvement.
