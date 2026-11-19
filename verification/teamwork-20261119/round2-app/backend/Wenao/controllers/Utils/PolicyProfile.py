"""Shared policy construction and optional experiment roster; no simulator API."""
from dataclasses import dataclass, asdict
from Utils.TeamPolicy import TeamPolicy
from Utils.Navigation import Navigator


@dataclass(frozen=True)
class PolicyProfile:
    locomotion: str = 'guarded'
    finishing_aim: str = 'centre'
    support_mode: str = 'baseline'
    active_names: tuple = ()

    def __post_init__(self):
        if self.locomotion not in ('legacy', 'guarded'):
            raise ValueError('Invalid locomotion profile')
        if self.finishing_aim not in ('centre', 'nearest'):
            raise ValueError('Invalid finishing aim')
        if self.support_mode not in ('baseline', 'possession'):
            raise ValueError('Invalid support mode')
        if len(set(self.active_names)) != len(self.active_names):
            raise ValueError('Duplicate active player')

    def create(self, name):
        return (TeamPolicy(name, goal_depth=.30 if self.locomotion == 'guarded' else 0,
                           finishing_nearest=self.finishing_aim == 'nearest',
                           support_mode=self.support_mode), Navigator())

    def observation(self, world):
        if not self.active_names:
            return world
        names = set(self.active_names)
        missing = names-set(world['robots'])
        if missing:
            raise ValueError('Missing active players: '+str(sorted(missing)))
        result = {**world, 'robots': {n: p for n, p in world['robots'].items() if n in names},
                  'penalties': {n: p for n, p in world.get('penalties', {}).items() if n in names}}
        intent = result.get('pass_intent')
        if intent and (intent['sender'] not in names or intent['receiver'] not in names):
            result.pop('pass_intent')
        return result

    def dictionary(self):
        return asdict(self)
