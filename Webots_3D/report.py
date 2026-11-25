"""Summarize observed Webots match and controller events."""
import argparse
from collections import Counter
import json
import math
from pathlib import Path

TRANSFERRED = {
    "OFFER_OUTLET", "DOUBLE_COVER", "COVER_CUTBACK", "MAKE_SPACE", "PRESS_LANE",
    "FLANK_PRESS", "DUEL_RELAY", "DUEL_WITHDRAW", "EARLY_RECEIVE", "PREPARE_FORWARD",
    "RECEIVE_FORWARD", "SWEEP_NEAR_POST", "KEEPER_STEP", "KEEPER_SHOT", "KEEPER_HOLD",
    "TRANSFER_PASS",
}


def read_logs(files):
    for path in files:
        with path.open() as source:
            for line in source:
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue  # an active controller may still be writing its last line


def inspect(run):
    commands = {"RED": Counter(), "BLUE": Counter()}
    movement = {"RED": Counter(), "BLUE": Counter()}
    for event in read_logs(run.glob("player-*.jsonl")):
        if event.get("event") not in {"command", "decision", "pass_intent_received", "pass_intent_sent"}:
            continue
        name = event.get("robot")
        if not name:
            continue
        side = "RED" if name.startswith("Red") else "BLUE"
        category = event["event"]
        if category == "command":
            commands[side][event["action"]] += 1
            if event.get("behaviour") in TRANSFERRED:
                movement[side][event["behaviour"]] += 1
        elif category.startswith("pass_intent"):
            commands[side][category] += 1
    previous = None
    ball_path = 0.0
    longest = 0.0
    anchor = None
    touch_samples = Counter()
    fallen_samples = Counter()
    standing = {}
    observed_falls = Counter()
    playing_samples = 0
    for sample in read_logs(run.glob("match-*.jsonl")):
        if sample.get("event") != "sample":
            continue
        if sample["match"]["phase"] != "PLAYING":
            previous = anchor = None
            standing.clear()
            continue
        playing_samples += 1
        ball = sample["ball"]["position"][:2]
        now = sample["time"]
        if previous:
            step = math.dist(previous, ball)
            if step < 0.45:
                ball_path += step
        previous = ball
        touch = sample["match"].get("last_touch")
        if touch:
            touch_samples[touch] += 1
        robots = sample["robots"]
        for name, robot in robots.items():
            upright = robot["standing"]
            if not upright:
                fallen_samples[name] += 1
                if standing.get(name):
                    observed_falls[name] += 1
            standing[name] = upright
        near = [any(n.startswith(team) and math.dist(p["position"][:2], ball) < .50
                    for n, p in robots.items()) for team in ("Red", "Blue")]
        stationary = math.hypot(*sample["ball"]["velocity"][:2]) < .045
        if all(near) and stationary:
            if not anchor or math.dist(anchor[0], ball) > 0.08:
                anchor = ball, now
            longest = max(longest, now - anchor[1])
        else:
            anchor = None
    values = {"commands": commands, "transferred_behaviour_commands": movement,
              "sampled_ball_path_metres": round(ball_path, 2),
              "max_sampled_crowd_stall_seconds": round(longest, 2),
              "playing_samples": playing_samples,
              "fallen_player_samples": fallen_samples,
              "observed_standing_to_fallen": observed_falls,
              "referee_last_touch_samples": touch_samples}
    for name in ("integration-result", "scenario-result"):
        result = run / (name + ".json")
        if result.is_file():
            values[name] = json.loads(result.read_text())
    return values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    log = args.directory / "trials.jsonl"
    if log.exists():
        trials = [{**row, **inspect(args.directory / row["path"])} for row in read_logs([log])]
        modes = {}
        for row in trials:
            mode = modes.setdefault(row["mode"], Counter())
            mode["completed"] += int(row["completed"])
            mode["trials"] += 1
            if not row["completed"]:
                continue
            mode["ball_path_metres"] += row["sampled_ball_path_metres"]
            side = row["team"]
            selected = row["commands"].values() if side == "both" else [row["commands"][side]]
            mode["selected_recovery_commands"] += sum(
                commands.get("recover_back", 0) + commands.get("recover_front", 0)
                for commands in selected
            )
            mode["shared_tactic_commands"] += sum(sum(team.values())
                                                      for team in row["transferred_behaviour_commands"].values())
        result = {"trials": trials, "by_mode": modes}
        complete = args.directory / "complete.json"
        if complete.exists():
            result["campaign"] = json.loads(complete.read_text())
    else:
        result = inspect(args.directory)
    text = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
