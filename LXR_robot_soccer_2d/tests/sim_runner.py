"""A small simulation loop shared by the tests; same order as the drill."""
import random
from dataclasses import dataclass, field
from typing import List

from robot_soccer.behaviours.goalkeeper import DEFAULT_KEEPER, goalkeeper_behaviour
from robot_soccer.behaviours.striker import striker_behaviour
from robot_soccer.environment.ball import ball_kick
from robot_soccer.environment.world import world_step
from robot_soccer.robot.motion import keep_apart, robot_state_init, robot_step
from robot_soccer.sensors.sensor_layer import sensor_init, sensor_step

DT = 0.02


@dataclass
class RunInfo:
    passes: int = 0
    received: int = 0
    states: List[List[str]] = field(default_factory=list)
    samples: List[dict] = field(default_factory=list)


def run_sim(w, roles, sp, pp, bp, rp, T, stop_on_receive=False, sample_every=0, rng=None,
            *, keeper_params=DEFAULT_KEEPER):
    """All robots sense, then decide, then move.

    Returns (outcome, info). outcome is a referee event type, 'cleared' (the
    keeper kicked the ball), 'received' (a pass reached a team-mate, if
    stop_on_receive) or 'timeout'.
    """
    rng = rng or random.Random(42)
    n = len(w.robots)
    ss = sensor_init(n)
    rs = robot_state_init(n)
    mem = [None] * n
    info = RunInfo(states=[[] for _ in range(n)])
    pass_from = None
    pass_kick = [False] * n
    n_steps = round(T / DT)

    for step in range(1, n_steps + 1):
        percepts = [sensor_step(w, k, ss[k], sp, DT, rs[k].odom, rng) for k in range(n)]
        cmds = []
        for k in range(n):
            if roles[k] == 'striker':
                cmd, mem[k] = striker_behaviour(percepts[k], mem[k], w.robots[k].team, pp, bp, rp,
                                                rs[k].odom, rng)
            else:
                cmd, mem[k] = goalkeeper_behaviour(percepts[k], mem[k], w.robots[k].team, pp, bp, rp,
                                                   rs[k].odom, params=keeper_params)
            cmds.append(cmd)
            if mem[k].state not in info.states[k]:
                info.states[k].append(mem[k].state)

        for k in range(n):
            if cmds[k].kick and rs[k].kick_t is None and mem[k].state == 'pass':
                pass_kick[k] = True
            if robot_step(w.robots[k], rs[k], cmds[k], rp, DT, rng):
                kicked = ball_kick(w.ball, w.robots[k], k, rs[k].kick_dir, rs[k].kick_speed, bp, rng)
                if kicked and roles[k] == 'keeper':
                    return 'cleared', info
                if kicked and pass_kick[k]:
                    info.passes += 1
                    pass_from = k
                pass_kick[k] = False
        keep_apart(w.robots, pp, rp)
        event = world_step(w, pp, bp, DT)

        touch = w.ball.last_touch_robot
        if pass_from is not None and touch is not None and touch != pass_from and roles[touch] == 'striker':
            info.received += 1
            pass_from = None
            if stop_on_receive:
                return 'received', info
        if event is not None:
            return event.type, info
        if sample_every and step % sample_every == 0:
            info.samples.append({'t': w.t, 'ball': list(w.ball.pos),
                                 'poses': [v for r in w.robots for v in (*r.pos, r.heading)],
                                 'states': [m.state for m in mem]})
    return 'timeout', info
