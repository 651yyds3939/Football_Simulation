#!/usr/bin/env python3
"""Run the existing Webots world with this repository's tactic adapter."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
DEFAULT_SOURCE = HERE.parent.parent / "Webots_Robotics_TDP"
PLAYERS = tuple(
    colour + role for colour in ("Red", "Blue")
    for role in ("Goalkeeper", "Defender", "ForwardB", "ForwardA")
)
ENTRY = """import os
import sys
sys.path.insert(0, os.environ["FOOTBALL_WEBOTS_ADAPTER"])
from adapter import start_player
start_player()
"""


def stage_project(source, workspace, candidate, check, scenario=None):
    project = workspace / "Wenao"
    project.mkdir()
    origins = source / "Wenao"
    (project / "worlds").mkdir()
    for name in ("naotdp.wbt", ".naotdp.wbproj"):
        original = origins / "worlds" / name
        if original.is_file():
            shutil.copy2(original, project / "worlds" / name)
    for asset in ("protos", "motions"):
        (project / asset).symlink_to(origins / asset, target_is_directory=True)
    controllers = project / "controllers"
    controllers.mkdir()
    for item in (origins / "controllers").iterdir():
        destination = controllers / item.name
        if candidate and item.name in PLAYERS:
            destination.mkdir()
            (destination / (item.name + ".py")).write_text(ENTRY)
        else:
            destination.symlink_to(item, target_is_directory=item.is_dir())
    if check:
        original_tests = source / "tests"
        tests = workspace / "tests"
        tests.mkdir()
        for item in original_tests.iterdir():
            path = tests / item.name
            if scenario and item.name == "webots_match_check.py":
                path.symlink_to(HERE / "scenario.py")
            elif item.name == "run_webots_check.py":
                shutil.copy2(item, path)
            elif not item.name.startswith("__"):
                path.symlink_to(item, target_is_directory=item.is_dir())
    return project


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--tactics", choices=("baseline", "support", "flow", "passing"), default="baseline")
    parser.add_argument("--team", choices=("RED", "BLUE", "both"), default="both")
    parser.add_argument("--check", action="store_true", help="Run the original project's verification harness")
    parser.add_argument("--locomotion", choices=("legacy", "guarded"),
                        help="Motion scheduler, guarded by default when running interactively")
    parser.add_argument("--output", type=Path, help="Directory for logs and experiment metadata")
    parser.add_argument("--scenario", choices=("crowd", "passing", "defence", "keeper", "keeper-shot"))
    parser.add_argument("--scenario-seconds", type=float, default=45)
    args, options = parser.parse_known_args()
    if args.scenario and (not args.check or "--match" not in options):
        parser.error("--scenario requires --check --match")
    if not 5 <= args.scenario_seconds <= 300:
        parser.error("--scenario-seconds must be between 5 and 300")
    source = args.source.expanduser().resolve()
    if not (source / "Wenao/worlds/naotdp.wbt").is_file():
        parser.error(f"Cannot locate the existing Webots world in {source}")
    env = os.environ.copy()
    for name in ("PYTHONPATH", "PYTHONHOME", "LD_LIBRARY_PATH", "QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH"):
        env.pop(name, None)
    env.update({
        "FOOTBALL_WEBOTS_SOURCE": str(source),
        "FOOTBALL_TEAMPLAY_ROOT": str(HERE.parent),
        "FOOTBALL_WEBOTS_TACTICS": args.tactics,
        "FOOTBALL_WEBOTS_TEAM": args.team,
        "FOOTBALL_WEBOTS_SCENARIO": args.scenario or "",
        "FOOTBALL_WEBOTS_SCENARIO_SECONDS": str(args.scenario_seconds),
        "PYTHONNOUSERSITE": "1",
        "PATH": str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", ""),
    })
    if args.check:
        if args.locomotion:
            options += ["--locomotion", args.locomotion]
    else:
        env["TDP_LOCOMOTION"] = args.locomotion or "guarded"
    output = args.output
    if output is None and not args.check:
        output = HERE / "runs" / ("interactive-" + time.strftime("%Y%m%d-%H%M%S"))
    if output is not None:
        output = output.expanduser().resolve()
        output.mkdir(parents=True, exist_ok=True)
        manifest = output / "transfer-manifest.json"
        if manifest.exists() or any(output.glob("*.jsonl")):
            parser.error("Use a fresh output directory to keep runs independent")
        env["TDP_RUN_DIR"] = str(output)
        if args.check:
            options += ["--output", str(output)]
        shared = HERE.parent / "Four_vs_Four/backend/Wenao/controllers/Utils"
        files = (HERE / "adapter.py", HERE / "run.py", HERE / "scenario.py",
                 *sorted(shared.glob("*.py")), source / "Wenao/worlds/naotdp.wbt",
                 source / "Wenao/controllers/Base/SoccerController.py")
        manifest.write_text(json.dumps({
            "mode": args.tactics, "team": args.team, "scenario": args.scenario,
            "source_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
        }, indent=2) + "\n")

    with tempfile.TemporaryDirectory(prefix="football-webots-") as directory:
        workspace = Path(directory)
        project = stage_project(source, workspace, args.tactics != "baseline", args.check, args.scenario)
        (workspace / "adapter").mkdir()
        shutil.copy2(HERE / "adapter.py", workspace / "adapter/adapter.py")
        env["FOOTBALL_WEBOTS_ADAPTER"] = str(workspace / "adapter")
        if args.check:
            command = [sys.executable, str(workspace / "tests/run_webots_check.py"), *options]
        else:
            command = [shutil.which("webots", path=env["PATH"]) or "webots",
                       *options, str(project / "worlds/naotdp.wbt")]
        try:
            return subprocess.run(command, env=env).returncode
        except KeyboardInterrupt:
            return 130


if __name__ == "__main__":
    raise SystemExit(main())
