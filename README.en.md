# Football Simulation

[简体中文](README.md)

`main` is the team's 2D simulation baseline. It includes a live 1v1 test, an eight-player 4v4 simulator, browser replays, and batch experiments. Webots 3D integration is being developed on `LWY`.

## Windows quick start

On GitHub, select the `main` branch, choose **Code → Download ZIP**, and extract the full archive. With an existing clone, switch to `main` and pull the latest changes.

| Goal | File to open |
| --- | --- |
| Watch 1v1 | Double-click the [five-example replay](Football_1v1_Demo.html) or [seven-case duel replay](Football_1v1_Cases_3-3-1.html). |
| Watch 4v4 | Double-click the [English replay](Football_4v4_Demo.html) or [Chinese replay](Football_4v4_Demo_ZH.html). |
| Run a new 1v1 attempt | Double-click the [1v1 launcher](2D_Shared_Policy_2026-11-11/start_windows.bat). Click **Play**. Use **New random setup** to change the starting layout or **Repeat seed** to rerun it. |
| Run a new 4v4 match | Double-click the [4v4 launcher](Four_vs_Four/start_windows.bat). It computes the match and opens a browser replay. |

The HTML replays open offline. Running a new simulation requires Python 3.8 or later and uses the Python standard library. Check the installation with `py -3 --version` in Command Prompt or PowerShell, or run `python --version` if Python is available under that command. [Python for Windows](https://www.python.org/downloads/windows/)

From the repository root in Command Prompt or PowerShell, run the commands below to select a seed and language or start a batch. Replace `py -3` with `python` if the installation uses that command.

```powershell
py -3 Four_vs_Four/run.py --seed 27 --language en --open
py -3 Four_vs_Four/run.py --seed 27 --batch 20 --no-replay
```

The 4v4 output is saved under `Four_vs_Four/runs/match_*/`. The `4V4_READY` line prints the run's folder. If a browser does not open, open `replay.html` from that folder. A batch with `--no-replay` saves the results to `metrics.json`. Keep the 1v1 console open while using the live interface. Its console prints the local URL if the browser needs to be opened manually.

On Ubuntu or macOS, run `python3 Four_vs_Four/run.py --language en --open` or `python3 2D_Shared_Policy_2026-11-11/server.py --open` from the repository root. The [4v4 package](Football_4v4.zip) and [1v1 package](2D_Shared_Policy_2026-11-11.zip) can also be downloaded and extracted separately.

## Current capabilities and development priorities

| Area | Current capability | Next checks and improvements |
| --- | --- | --- |
| **1v1** | Configure spawn regions, repeat seeded attempts, watch dribbling, tackles and clearances, and download run data. | Check head-on contests, recovery after being beaten, and how slow turns affect positioning. [1v1 live guide in Chinese](2D_Shared_Policy_2026-11-11/README.md) |
| **4v4** | Eight players complete a match using `flow`. The replay shows short touches, directed receptions, interceptions, goalkeeper positioning, and post-goal resets. | Reduce prolonged contests around a stationary ball. Check whether receptions lead to progress or a shot, and verify near-goal coverage and clearances. [4v4 experiment notes in Chinese](Four_vs_Four/README.md) |
| **Testing** | Fixed-seed replays, live run data download, 4v4 batch runs, and outputs including `metrics.json`, `replay.html`, and `scene.json`. | Add fixed cases for strikers, defenders, goalkeepers, and team tactics. Compare changes with the same initial setup, player speeds, and time step. |
| **3D and hardware** | The 2D simulator uses exact positions and simplified motion and contact. Camera errors, balance, and falls require 3D and hardware checks. 3D experiments are on `LWY`. | Recheck selected behaviours in Webots, then measure sensing, motion, balance, and speed on the NAO6. |

The target lines show planned positions. Use the event log or the intended receiver's foot-contact count in `metrics.json` to evaluate completed passes. Playback speed controls viewing time.

## Ownership and code entry points

These tasks map the Gantt plan to the current repository. Each branch can deliver a reproducible test and its results first, then include any behaviour change it supports.

| Branch | Gantt task | Code and proposed deliverable |
| --- | --- | --- |
| **SBH** | 4.2 Striker | `attack()`, `choose_carry()`, and `find_shot()` in `Flow.py`. Test beating a defender, losing possession, and getting a shot away. |
| **CJL** | 3.1 Pitch and rules, 3.5 visualisation and batch runs, 4.3 defender | Start with `interception()` and `recovery_action()` in `DefensivePlan.py` and `Flow.defend()`. Use `CourseSpecs.py` and `MatchEngine.py` to check goal, out-of-play, and reset cases. Keep visualisation and rule changes in separate submissions. |
| **LXR** | 3.4 Sensor representation, 4.1 guidance, 4.4 goalkeeper | Use `Flow.keep_goal()` and the goalkeeper branch in `TeamNavigation.py` for the current `flow` strategy. Test lateral movement and contact against near- and far-post shots. Document the observation interface. |
| **ZYH** | 4.5 Team strategy, P0 integration | `pick_chaser()`, `place_support()`, and `offer_width()` in `Flow.py`. Verify pressing, outlets, cover, and actual receptions, and coordinate PR reviews. |
| **LWY** | 2.3 Interfaces, 3.2–3.3 modelling, 3.6 validation, 4.6–4.7 experiments | Own the ball and robot models in `soccer2d.py`, matched experiments in `run_policy_experiment.py`, and 2D-to-3D adaptation on `LWY`. Maintain the shared baseline and test records. |

Find tactics, navigation, and match rules in [4v4 controller modules](Four_vs_Four/backend/Wenao/controllers/Utils/) and the simulation and experiment entry points in [tools](Four_vs_Four/backend/tools/). Several members share `Flow.py`. Start with the functions assigned above. Sync the personal branch with the latest `main`, test the change, and open a PR into `main` with the Gantt task ID, setup or seed, run command, and before-and-after results.

## Further records

- [Seven 1v1 cases](docs/ONE_V_ONE_CASES_3_3_1_2026-11-19.md) · [1v1 dribbling and tackle experiments](docs/ATTACKING_DUELS_2026-11-19.md)
- [4v4 strategy updates and results](Four_vs_Four/README.md) · [Earlier teamwork experiments](docs/FOUR_V_FOUR_TEAMWORK_2026-11-19.md)
- [2D pitch and model figures](2D_Pitch_and_Modelling_2026-11-04/) · [Bilingual parameter sources](S3_数据来源图片_中英文_2026-11-04/) · [Verification scripts and records](verification/)
