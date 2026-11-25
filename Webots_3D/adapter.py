"""Connect the shared team planner to the existing Webots action interface."""
from dataclasses import dataclass
import math
import os
from pathlib import Path
import sys

sys.path.insert(0, os.environ.get("FOOTBALL_TEAMPLAY_ROOT", str(Path(__file__).resolve().parents[1])))
from Four_vs_Four.backend.Wenao.controllers.Utils.Flow import Flow  # noqa: E402


@dataclass(frozen=True)
class WebotsMotionProfile:
    # Isolated motion observations. The pass displacement includes receiver
    # interaction, so use it only as a conservative short-pass experiment.
    walk_speed: float = 0.085
    back_speed: float = 0.034
    left_speed: float = 0.013
    right_speed: float = 0.022
    left_turn: float = 0.074
    right_turn: float = 0.076
    planar_turn_rate: float = 0.074
    robot_radius: float = 0.15
    rolling_deceleration: float = 0.35
    shot_range: float = 0.406
    pass_range: float = 0.305
    planar_pass_seconds: float = 3.299
    pass_seconds: float = 3.299


class SharedTactics:
    def __init__(self, controller, mode, policy_type, decision_type):
        self.controller = controller
        self.original = controller.policy
        self.prefix = self.original.prefix
        self.decision_type = decision_type
        self.mode = mode
        self.flows = Flow(WebotsMotionProfile())
        self.flows.enabled = {self.prefix}
        self.flows.use_wider_pass = False
        self.flows.tap_enabled = False
        self.flows.touch_pass = False
        self.flows.snap_enabled = False
        self.flows.long_shot = False
        self.flows.finish_movement = False
        self.flows.finish_range = False
        self.flows.quick_outlet = mode == "passing"
        self.flows.allow_trap = False
        self.flows.keeper_loose = False
        self.flows.diagonal_save = False
        self.flows.edge_min_stall = math.inf
        self.flows.keeper_near_depth = 1.3
        self.flows.press_gap = 0.40
        self.flows.outlet_space = 0.58
        self.policies = {}
        self.policy_type = policy_type
        self.last_time = None
        self.plan = None

    def prepare(self, world):
        # All players update tactical state on received snapshots even while an
        # individual robot is completing a walking cycle or standing up.
        if self.last_time == world["time"]:
            return
        self.last_time = world["time"]
        intent = self.controller.pass_intent
        if (intent and intent["expires"] > world["time"]
                and intent["receiver"] in world["robots"]
                and world["match"]["last_touch"] != intent["receiver"]):
            world = {**world, "pass_intent": intent}
        orders = {}
        for name in world["robots"]:
            if name not in self.policies:
                self.policies[name] = self.policy_type(name, goal_depth=self.original.goal_depth)
            orders[name] = self.policies[name].decide(world)
        kickers = {world["pass_intent"]["sender"]} if "pass_intent" in world else set()
        # The radio protocol supplies approximate referee contacts, not a
        # certified foot-contact signal. The planner handles that input absent.
        self.plan = self.flows.adjust(world, orders, kickers)[self.controller.name]

    def decide(self, world):
        baseline = self.original.decide(world)
        if self.plan is None or not world["match"]["released"] or world["match"]["phase"] != "PLAYING":
            return baseline
        order = self.plan
        behaviour = order.behaviour
        # Translate team goals into decisions understood by the Webots
        # navigator. The physical motion scheduler still owns execution.
        if behaviour in {"OFFER_OUTLET", "DOUBLE_COVER", "COVER_CUTBACK", "MAKE_SPACE",
                         "PRESS_LANE", "FLANK_PRESS", "DUEL_RELAY", "DUEL_WITHDRAW", "EARLY_RECEIVE",
                         "PREPARE_FORWARD", "RECEIVE_FORWARD"}:
            return self.decision_type(behaviour, order.target, order.face)
        if self.mode == "support":
            return baseline
        if behaviour in {"CARRY_LANE", "BEAT_MARKER", "CUT_AROUND"}:
            return self.decision_type("DRIBBLE", order.target, order.face)
        if behaviour == "PURSUE_BALL":
            return self.decision_type("DEFENSIVE_INTERCEPT", order.target, order.face)
        if behaviour in {"KEEPER_STEP", "KEEPER_HOLD", "KEEPER_SHOT", "SWEEP_NEAR_POST"}:
            return self.decision_type(behaviour, order.target, order.face)
        if behaviour == "OUTLET_PASS" and self.mode == "passing":
            return self.decision_type("TRANSFER_PASS", order.target, order.face, "pass", order.receiver)
        return baseline


class WebotsNavigation:
    def __init__(self, original, route, controller, tactics):
        self.original = original
        self.route = route
        self.controller = controller
        self.tactics = tactics

    def choose(self, decision, own, yaw, ball, robots=()):
        if decision.behaviour == "DUEL_RELAY" and math.dist(own[:2], ball[:2]) < 0.40:
            decision = self.tactics.decision_type("CHALLENGE", decision.target, tuple(ball[:2]))
        if decision.behaviour == "DUEL_WITHDRAW":
            if math.dist(own[:2], decision.target) <= 0.07:
                return "stand", "TRANSFER_SIDE_LANE_OPEN"
            return "back", "TRANSFER_WITHDRAW"
        if decision.behaviour == "TRANSFER_PASS":
            original = self.tactics.decision_type("PASS", decision.target, decision.face, "pass", decision.receiver)
            action, stage = self.original.choose(original, own, yaw, ball, robots)
            if action == "pass":
                world = self.controller.observation.world
                rivals = [p["position"] for name, p in world["robots"].items()
                          if not name.startswith(self.tactics.prefix)]
                if not self.tactics.flows.safe_pass_path(
                    ball[:2], decision.face, rivals, self.tactics.flows.model.pass_seconds
                ):
                    return "stand", "TRANSFER_PASS_LANE_BLOCKED"
            return action, stage
        if decision.behaviour in {"KEEPER_STEP", "KEEPER_HOLD", "KEEPER_SHOT", "SWEEP_NEAR_POST"}:
            _, action, _ = self.route(own, yaw, decision.target, tolerance=0.09)
            if decision.behaviour != "SWEEP_NEAR_POST" and action.startswith(("left", "right")):
                dx, dy = decision.target[0] - own[0], decision.target[1] - own[1]
                forward = dx * math.cos(yaw) + dy * math.sin(yaw)
                sideways = -dx * math.sin(yaw) + dy * math.cos(yaw)
                if abs(sideways) > 0.085:
                    action = "step_left" if sideways > 0 else "step_right"
                elif abs(forward) > 0.085:
                    action = "walk" if forward > 0 else "back"
                else:
                    action = "stand"
            return action, "TRANSFER_GOAL_COVER"
        return self.original.choose(decision, own, yaw, ball, robots)


def start_player():
    sys.path.insert(0, str(Path(os.environ["FOOTBALL_WEBOTS_SOURCE"]) / "Wenao/controllers"))
    from Base.SoccerController import SoccerController
    from Utils.DefensivePlan import route
    from Utils.TeamPolicy import Decision, TeamPolicy

    class Player(SoccerController):
        def act(self, world):
            if isinstance(self.policy, SharedTactics):
                self.policy.prepare(self.policy_profile.observation(world))
            return super().act(world)

    controller = Player()
    mode = os.environ["FOOTBALL_WEBOTS_TACTICS"]
    team = os.environ["FOOTBALL_WEBOTS_TEAM"]
    if mode != "baseline" and (team == "both" or controller.policy.team == team):
        if controller.source != "supervisor":
            raise ValueError("The transferred policy requires the supervisor observation profile")
        controller.policy = SharedTactics(controller, mode, TeamPolicy, Decision)
        controller.navigator = WebotsNavigation(controller.navigator, route, controller, controller.policy)
        controller.log.write(
            '{"event":"transferred_tactics_enabled","mode":"' + mode + '"}\n'
        )
    controller.run()
