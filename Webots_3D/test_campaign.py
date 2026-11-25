"""Run repeatable Webots comparisons for approximately the requested wall time."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
EXPERIMENTS = (
    ("baseline", "both"), ("support", "RED"), ("support", "BLUE"),
    ("flow", "RED"), ("flow", "BLUE"), ("passing", "RED"), ("passing", "BLUE"),
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration", type=float, default=3600)
    parser.add_argument("--half-seconds", type=float, default=120)
    parser.add_argument("--seed", type=int, default=27)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--resume", action="store_true", help="Continue the recorded campaign after an interruption")
    args = parser.parse_args()
    if args.duration <= 0 or args.half_seconds <= 11:
        parser.error("Supply positive duration and halves longer than READY/SET")
    root = args.output.resolve()
    manifest_path = root / "campaign.json"
    results_path = root / "trials.jsonl"
    configuration = {"requested_wall_seconds": args.duration, "half_seconds": args.half_seconds,
                     "experiments": [list(experiment) for experiment in EXPERIMENTS], "seed": args.seed}
    trial = 0
    recorded = 0.0
    if args.resume:
        manifest = json.loads(manifest_path.read_text())
        if any(manifest[key] != value for key, value in configuration.items()):
            parser.error("Resume options must match the original campaign")
        if (root / "complete.json").exists():
            parser.error("The campaign is already complete")
        if results_path.exists():
            rows = [json.loads(line) for line in results_path.read_text().splitlines() if line.strip()]
            trial = len(rows)
            if rows:
                recorded = rows[-1]["elapsed_seconds"]
    else:
        root.mkdir(parents=True)
        manifest_path.write_text(json.dumps({"started_epoch": time.time(), **configuration}, indent=2) + "\n")
    started = time.monotonic()
    while recorded + time.monotonic() - started < args.duration:
        mode, team = EXPERIMENTS[trial % len(EXPERIMENTS)]
        seed = args.seed + trial // len(EXPERIMENTS)
        name = f"{trial + 1:03d}-{mode}-{team}-{seed}"
        run = root / name
        retry = 0
        while run.exists():
            retry += 1
            run = root / f"{name}-retry{retry}"
        run.mkdir()
        command = [
            sys.executable, str(HERE / "run.py"), "--check", "--tactics", mode,
            "--team", team, "--match", "--seed", str(seed), "--half-seconds",
            str(args.half_seconds), "--ready-seconds", "10", "--stuck-seconds", "60",
            "--reset-formation", "--locomotion", "guarded", "--timeout", "600",
            "--output", str(run),
        ]
        if args.source:
            command += ["--source", str(args.source)]
        print("START", trial + 1, mode, team, seed, flush=True)
        before = time.monotonic()
        with (run / "console.log").open("w") as console:
            status = subprocess.run(command, stdout=console, stderr=subprocess.STDOUT).returncode
        completed = (run / "integration-result.json").exists() and status == 0
        with results_path.open("a") as results:
            row = {"trial": trial + 1, "path": run.name, "mode": mode, "team": team,
                   "seed": seed, "status": status, "completed": completed,
                   "wall_seconds": round(time.monotonic() - before, 2),
                   "elapsed_seconds": round(recorded + time.monotonic() - started, 2)}
            results.write(json.dumps(row) + "\n")
        print("END", json.dumps(row), flush=True)
        trial += 1
    (root / "complete.json").write_text(json.dumps({
        "trials": trial, "elapsed_seconds": recorded + time.monotonic() - started
    }, indent=2) + "\n")


if __name__ == "__main__":
    main()
