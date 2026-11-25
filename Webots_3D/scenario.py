"""Fixed starting poses for focused tests with real Webots controllers."""
import json
import math
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from Base.SupervisorBase import SupervisorBase
from Utils.CourseSpecs import BALL_RADIUS, TIME_STEP
from Utils.MatchEngine import MatchConfig

LAYOUTS = {
    "crowd": {
        "RedForwardA": (-0.28, -0.03, 0.0),
        "BlueForwardA": (0.28, 0.03, math.pi),
        "RedForwardB": (-0.46, 0.40, -0.55),
        "RedDefender": (-1.1, -0.52, 0.15),
        "BlueForwardB": (0.60, -0.47, 2.60),
        "BlueDefender": (1.35, 0.6, math.pi),
    },
    "passing": {
        "RedForwardA": (-0.19, -0.05, 0.0),
        "RedForwardB": (0.48, 0.02, math.pi),
        "RedDefender": (-1.08, -0.66, 0.15),
        "BlueDefender": (1.45, 0.53, math.pi),
        "BlueForwardA": (1.60, -0.75, math.pi),
        "BlueForwardB": (0.80, 1.2, -2.0),
    },
    "keeper": {
        "RedGoalkeeper": (-4.15, 0.28, 0.0),
        "BlueForwardA": (-2.98, 0.99, math.pi),
        "RedDefender": (-2.7, -0.6, 0.12),
        "RedForwardA": (-1.42, 1.70, 0.0),
        "RedForwardB": (-1.51, -1.10, 0.0),
        "BlueDefender": (0.80, 0.08, math.pi),
        "BlueForwardB": (-1.36, -0.13, math.pi),
    },
    "defence": {
        "RedForwardA": (0.44, -1.75, 0.0),
        "RedForwardB": (-1.12, 1.57, -0.4),
        "RedDefender": (-0.77, 0.20, 0.05),
        "BlueDefender": (1.30, 0.60, math.pi),
        "BlueForwardA": (0.24, -0.04, math.pi),
        "BlueForwardB": (0.85, -1.14, 2.66),
    },
}


def run(supervisor, name, duration):
    tick = TIME_STEP / 1000
    origins = LAYOUTS["keeper" if name == "keeper-shot" else name]
    ball = {
        "defence": (-3.12, 0.77, BALL_RADIUS),
        "keeper": (-3.48, 0.51, BALL_RADIUS),
        "keeper-shot": (-3.0, 0.21, BALL_RADIUS),
    }.get(name, (0.0, 0.0, BALL_RADIUS))
    for player, node in supervisor.robots.items():
        default = (-4.13, 0.0, 0.0) if player.startswith("Red") else (4.13, 0.0, math.pi)
        x, y, yaw = origins.get(player, default)
        if name == "defence" and not player.endswith("Goalkeeper"):
            x += ball[0]
            y += ball[1]
        node.getField("translation").setSFVec3f([x, y, 0.334])
        node.getField("rotation").setSFRotation([0, 0, 1, yaw])
        node.resetPhysics()
        node.restartController()
    supervisor.setBallPosition(list(ball))
    match = supervisor.match
    match.phase = "SET"
    match.phase_started = supervisor.getTime()
    match.red_direction = 1

    for _ in range(round(2.0 / tick)):
        if supervisor.step(TIME_STEP) < 0:
            raise RuntimeError("Webots stopped while preparing the fixture")
        supervisor.sendSupervisorData()
    started = supervisor.getTime()
    match.phase = "PLAYING"
    match.half_started = match.phase_started = started
    match.restart = "DROP_BALL"
    match.restart_point = list(ball)
    match.restart_team = None
    match.released = True
    match.indirect = match.kickoff_restriction = match.restart_goal_guard = False
    velocity = {"keeper": (-0.71, -0.10), "keeper-shot": (-3.6, 0.45)}.get(name)
    if velocity:
        # Test input from a declared rolling-ball state. The simulated ball
        # and the keeper are free to respond through Webots physics.
        supervisor.ball.setVelocity([*velocity, 0.0, 0.0, 0.0, 0.0])
    match.previous = list(supervisor.ball.getPosition())
    first_advance = None
    ball_path = 0.0
    previous = match.previous
    touches = []
    for _ in range(round(duration / tick)):
        if supervisor.step(TIME_STEP) < 0:
            raise RuntimeError("Webots stopped while running the fixture")
        supervisor.updateMatch()
        supervisor.sendSupervisorData()
        point = list(supervisor.ball.getPosition())
        ball_path += math.dist(previous[:2], point[:2])
        previous = point
        elapsed = supervisor.getTime() - started
        if first_advance is None and math.dist(ball[:2], point[:2]) > 0.25:
            first_advance = round(elapsed, 2)
        touch = match.last_touch
        if touch and (not touches or touches[-1]["robot"] != touch):
            touches.append({"time": round(elapsed, 2), "robot": touch})
        if match.phase != "PLAYING":
            break
    result = {"scenario": name, "simulated_seconds": round(elapsed, 2),
              "advance_025_seconds": first_advance, "score": list(match.score),
              "touches": touches, "ball_path_metres": round(ball_path, 3)}
    (supervisor.log_directory / "scenario-result.json").write_text(json.dumps(result, indent=2))
    print("MATCH_CHECK_OK", json.dumps(result), flush=True)


supervisor = SupervisorBase(
    MatchConfig(half_seconds=600, startup_seconds=0, ready_seconds=10, set_seconds=1)
)
try:
    run(supervisor, os.environ["FOOTBALL_WEBOTS_SCENARIO"],
        float(os.environ["FOOTBALL_WEBOTS_SCENARIO_SECONDS"]))
except Exception:
    import traceback
    traceback.print_exc()
    supervisor.step(TIME_STEP)
    supervisor.simulationQuit(1)
else:
    supervisor.step(TIME_STEP)
    supervisor.simulationQuit(0)
