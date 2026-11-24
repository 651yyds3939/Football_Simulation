"""Directed pass metrics derived from the same contact events as the replay."""
from dataclasses import dataclass
import math

from Utils.CourseSpecs import PITCH_LENGTH


@dataclass
class Reception:
    receiver: str
    direction: int
    origin_x: float
    expiry: float
    record: dict


class PassReport:
    def __init__(self):
        self.event_index = 0
        self.active = None
        self.teams = {
            team: {"attempts": 0, "intended_body_contacts": 0, "intended_foot_contacts": 0,
                   "receptions": []}
            for team in ("RED", "BLUE")
        }

    def observe(self, simulation):
        events = simulation.events
        if self.event_index != len(events):
            for event in events[self.event_index:]:
                self.record_event(simulation, event)
            self.event_index = len(events)
        reception = self.active
        if reception is None:
            return
        if simulation.time > reception.expiry:
            self.active = None
        elif simulation.touch == reception.receiver:
            movement = reception.direction * (simulation.ball[0] - reception.origin_x)
            old = reception.record["max_forward_metres"]
            reception.record["max_forward_metres"] = max(old, movement)

    def record_event(self, simulation, event):
        kind = event["event"]
        if self.active is not None:
            if (kind in ("place_ball", "goal", "fixture_formation")
                    or kind == "contact" and event["robot"] != self.active.receiver):
                self.active = None
        if kind == "kick_start" and event.get("receiver"):
            team = simulation.policies[event["robot"]].team
            self.teams[team]["attempts"] += 1
        if kind != "pass_result" or not event["completed"]:
            return
        team = simulation.policies[event["sender"]].team
        if event["contact_source"] == "body":
            self.teams[team]["intended_body_contacts"] += 1
            return
        self.teams[team]["intended_foot_contacts"] += 1
        receiver = event["receiver"]
        direction = simulation.engine.direction(team)
        x, y = event["point"]
        heading = simulation.players[receiver]["yaw"]
        goal_bearing = math.atan2(-y, direction * PITCH_LENGTH / 2 - x)
        error = abs(math.degrees((goal_bearing - heading + math.pi) % (2 * math.pi) - math.pi))
        record = {
            "sender": event["sender"], "receiver": receiver, "time": event["time"],
            "heading_error_degrees": round(error, 2), "max_forward_metres": 0.,
        }
        self.teams[team]["receptions"].append(record)
        self.active = Reception(receiver, direction, x, simulation.time + 15., record)

    def summary(self):
        summaries = {}
        for team, stats in self.teams.items():
            records = stats["receptions"]
            summaries[team] = {
                **stats,
                "advanced_025m": sum(record["max_forward_metres"] >= .25 for record in records),
                "receptions": [
                    {**record, "max_forward_metres": round(record["max_forward_metres"], 4)}
                    for record in records
                ],
            }
        return summaries
