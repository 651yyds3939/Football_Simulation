"""Simulate an existing 4v4 policy and export a self-contained browser replay."""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys
import webbrowser

from soccer2d import Model, ROOT, Simulation
from Utils import CourseSpecs as specs
from Utils.ProcessSupervisor import ROBOT_NAMES


def finite_json(data):
    return json.dumps(data, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def record_scene(seed, candidate, candidate_team, model):
    frames = []

    def observe(sim):
        world = sim.observation()
        players = []
        for name in ROBOT_NAMES:
            p = sim.players[name]
            # Read already selected decisions/actions. Calling decide() here
            # would update stateful policies a second time and change the run.
            held = sim.kicking.get(name)
            players.append([
                round(p["position"][0], 6), round(p["position"][1], 6),
                round(p["yaw"], 6), sim.last_decisions.get(name, ""),
                sim.last_actions.get(name, ""),
                held[1].kick if held else "",
                round(max(0, held[0]-sim.time), 3) if held else 0,
            ])
        frames.append({
            "t": round(sim.time, 6), "match": world["match"],
            "ball": [round(v, 6) for v in sim.ball[:2]],
            "velocity": [round(v, 6) for v in sim.velocity[:2]],
            "players": players, "touch": sim.touch,
            "pass": dict(world["pass_intent"]) if "pass_intent" in world else None,
        })

    sim = Simulation(seed, candidate_team, candidate, model)
    result = sim.run(observer=observe)
    geometry = {name: getattr(specs, name) for name in (
        "PITCH_LENGTH", "PITCH_WIDTH", "GOAL_WIDTH", "GOAL_HEIGHT", "GOAL_DEPTH",
        "GOAL_AREA_LENGTH", "GOAL_AREA_WIDTH", "PENALTY_AREA_LENGTH", "PENALTY_AREA_WIDTH",
        "PENALTY_MARK_DISTANCE", "CENTRE_CIRCLE_DIAMETER", "BORDER_WIDTH", "LINE_WIDTH", "BALL_RADIUS",
    )}
    scene = {"schema": 1, "seed": seed, "candidate": candidate,
             "candidateTeam": candidate_team, "names": list(ROBOT_NAMES),
             "geometry": geometry, "model": asdict(model),
             "frames": frames, "events": sim.events, "result": result}
    finite_json(scene)
    return scene


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=27)
    parser.add_argument("--candidate", choices=("baseline", "possession"), default="baseline",
                        help="baseline is the default; possession is an experimental policy")
    parser.add_argument("--candidate-team", choices=("RED", "BLUE"), default="RED")
    parser.add_argument("--half-seconds", type=float, default=300)
    parser.add_argument("--ready-seconds", type=float, default=10)
    parser.add_argument("--language", choices=("zh", "en"), default="zh", help="Viewer interface language")
    parser.add_argument("--output", required=True, type=Path, help="New output directory")
    parser.add_argument("--open", action="store_true", help="Open the exported scene in a browser")
    args = parser.parse_args(argv)
    try:
        model = Model(half_seconds=args.half_seconds, ready_seconds=args.ready_seconds)
    except ValueError as exc:
        parser.error(str(exc))
    if args.output.exists():
        parser.error("Use a fresh output directory; existing results are preserved")
    template = Path(__file__).with_name(
        "soccer2d_viewer_en.html" if args.language == "en" else "soccer2d_viewer.html")
    html = template.read_text(encoding="utf-8")
    if html.count("__SCENE_DATA__") != 1:
        raise RuntimeError("Viewer template must contain exactly one scene-data placeholder")
    scene = record_scene(args.seed, args.candidate, args.candidate_team, model)
    args.output.mkdir(parents=True)
    sources = [Path(__file__).resolve(), template, Path(__file__).with_name("soccer2d.py")]
    sources += [ROOT / "Wenao/controllers/Utils" / (n+".py") for n in
                ("TeamPolicy", "Navigation", "MatchEngine", "CourseSpecs", "ProcessSupervisor")]
    hashes = {}
    for source in sources:
        relative = source.relative_to(ROOT)
        target = args.output / "source_snapshot" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        hashes[str(relative)] = hashlib.sha256(source.read_bytes()).hexdigest()
    manifest = {"mode": "recorded_kinematic_2d_scene", "created_utc": datetime.now(timezone.utc).isoformat(),
                "seed": args.seed, "candidate": args.candidate, "candidate_team": args.candidate_team,
                "viewer_language": args.language,
                "model": asdict(model), "python": sys.version, "source_sha256": hashes,
                "frames": len(scene["frames"]), "sample_seconds": model.dt,
                "observations": "ground_truth", "formation_fixture": True,
                "note": "Recorded simulation replay, not live control or 3D/hardware validation."}
    scene["source_sha256"] = hashes
    # Embedded JSON must not terminate the surrounding script element.
    embedded = finite_json(scene).replace("<", "\\u003c").replace("&", "\\u0026")
    replay = args.output / "replay.html"
    replay.write_text(html.replace("__SCENE_DATA__", embedded), encoding="utf-8")
    for name, data in (("scene.json", scene), ("result.json", scene["result"]), ("manifest.json", manifest)):
        (args.output / name).write_text(json.dumps(data, ensure_ascii=False, allow_nan=False, indent=2)+"\n",
                                        encoding="utf-8")
    print(f"2D_SCENE_READY {replay.resolve()}")
    print(f"Score {scene['result']['score_red_blue']}; {len(scene['frames'])} frames; "
          f"{scene['result']['simulated_seconds']:.2f} simulated seconds")
    if args.open:
        if not webbrowser.open(replay.resolve().as_uri()):
            print("Browser did not open automatically; open replay.html manually.", file=sys.stderr)


if __name__ == "__main__":
    main()
