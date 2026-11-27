# 4.5 Team strategy — supporting a short pass

**Assigned review:** ZYH  
**Replay:** [Football_4v4_Demo_ZH.html](../Football_4v4_Demo_ZH.html)  
**Setup:** Seed 294034. Both teams use the `flow` strategy.  
**Review window:** 0:35.0–0:40.4 on the match clock, with 0:28.0 as a comparison.

## Goal

Check how an off-ball teammate prepares to receive a short pass. Follow Red Forward A as the passer and Red Forward B as the receiver. Look for a change in B's actual position before the ball is kicked, then check who makes the next contact.

## How to reproduce

1. Open the replay in a browser and pause around **0:35.0**. Slow the playback or step through one frame at a time.
2. Select Red Forward B in the player panel and leave **Team targets** enabled. Compare B's position and heading at **0:35.0** and **0:39.0**, then watch the ball from **0:39.2** to **0:40.2**.
3. Check the match events for the pass outcome. The dashed line shows the target the strategy chose. The player's position shows where the robot moved.

## Reference findings from the recorded data

| Match time | Recorded behaviour | What to check |
| --- | --- | --- |
| **0:35.0** | B is in `OFFER_OUTLET` and is side-stepping. | B offers a passing option away from the ball while A approaches it. |
| **0:38.6–0:39.0** | A starts a `TOUCH_PASS` aimed at B. B enters a receiving state and turns. B is about **0.18 m** from its 0:35.0 position. | Part of the receiving movement occurred before the ball was released. The 0.18 m figure is the straight-line change between two samples. |
| **0:39.2** | A's foot contacts the ball. The pass intent changes to released. | The pass begins physically here, about 0.6 seconds after the pass action starts. |
| **0:40.2** | B traps the ball with its foot. The log marks B as both the intended and actual receiver. | The ball's recorded speed reaches zero at the trap. This is a completed foot reception in the 2D model. |
| **0:40.4** | A moves into an outlet role while B starts moving with the ball. | The support role switches as B takes over. |

For comparison, at **0:28.0** in the same replay, Red Defender's intended pass to B is intercepted by Blue Forward A. Both passes had an intended receiver. The observed contact determines whether the pass completed.

## What this case shows

The replay contains one successful sequence of off-ball support, a pass and a foot reception. It also contains an interception, so one clip cannot establish how often the approach succeeds. The next useful comparison is another pass with a defender closer to the receiving lane. Record receiver movement, first contact and whether the receiving team can advance afterward.

## Reviewer observation

- **Replay time and player followed:** [Record the moment reviewed and the player selected.]
- **What was visible before the pass:** [Describe one movement or heading change in your own words.]
- **Result and follow-up:** [Say what confirmed the reception and propose one second case to check.]
