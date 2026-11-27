# 4.2 Striker behaviour — short touch under pressure

**Assigned review:** SBH  
**Replay:** [Football_4v4_Demo_ZH.html](../Football_4v4_Demo_ZH.html)  
**Setup:** Seed 294034. Both teams use the `flow` strategy.  
**Review window:** 0:34.0–0:40.2 on the match clock.

## Goal

Check what a striker does when a blue player is near the ball and the immediate route is crowded. Follow Red Forward A from its approach to a short touch, then classify the next action as another dribble, a pass, a shot or a loss of possession.

## How to reproduce

1. Open the replay in a browser, pause at about **0:34.0**, and select **Red Forward A** in the player list.
2. Step through **0:36.2–0:37.4**. Watch the striker's heading and the ball trail. Use the match clock and the player inspector for positions.
3. Continue to **0:40.2**. Check the match events to see whether the next kick names a receiver and who contacts the ball.

## Reference findings from the recorded data

| Match time | Recorded behaviour | Interpretation |
| --- | --- | --- |
| **0:34.0–0:35.0** | The ball is stationary. A approaches and turns. Blue Forward A is nearby on the other side of the ball. | A adjusts its approach before the touch. The nearby blue player is relevant to the pressure in this clip. |
| **0:35.8–0:36.4** | A starts a short touch at 0:35.8 and contacts the ball at 0:36.4. The action is logged as `CARRY_TAP`, with no intended receiver. | This touch moves the ball locally and prepares the next action. |
| **0:36.2–0:37.4** | The ball moves from about **(−0.85, −0.40) m** before the contact to **(−0.67, −0.28) m** at rest. That is a straight-line displacement of about **0.22 m**. A follows the ball. | The ball moved diagonally and stopped within a short distance. |
| **0:38.6–0:40.2** | A starts a separate `TOUCH_PASS` to Red Forward B, kicks at **0:39.2**, and B traps the ball at **0:40.2**. | A follows the short touch with a completed pass. |

## What this case shows

The short touch changed the ball's position and led into a pass. The clip ends before a shot and does not establish that A beat the defender alone. A useful follow-up is a fixed case with a defender directly ahead. Record whether the striker gets past the defender, loses possession, makes a pass or takes a shot. Assess those outcomes separately.

## Reviewer observation

- **Replay time and player followed:** [Record the frames reviewed.]
- **What was visible before and after the touch:** [Describe the striker's movement and the ball direction.]
- **Result and follow-up:** [Record what the next action was and what another case could show.]
