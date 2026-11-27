"""Participant configuration and read-only views of physical marker tracking.

No GUI, camera, musical actions or game rules. Only bindings are persisted;
retirement and detection state belong to the current session.
"""
from dataclasses import dataclass
import re
from types import MappingProxyType
from marker_tracking import MarkerState


@dataclass(frozen=True)
class ParticipantBinding:
    participant_id: str
    name: str
    color: str
    source_id: str
    marker_id: int

    def __post_init__(self):
        for field, limit in (("participant_id", 128), ("name", 80), ("source_id", 128)):
            value = getattr(self, field)
            if not isinstance(value, str) or len(value) > limit or (field != 'name' and not value.strip()):
                raise ValueError(f'Camp de participant no vàlid: {field}')
            if any(ord(c) < 32 for c in value):
                raise ValueError(f'Caràcter de control no permès: {field}')
        if not isinstance(self.color, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', self.color):
            raise ValueError('El color ha de tenir el format #RRGGBB')
        object.__setattr__(self, 'color', self.color.upper())
        if type(self.marker_id) is not int or not 0 <= self.marker_id <= 15:
            raise ValueError('L’ID ArUco ha de ser un enter entre 0 i 15')

    @property
    def marker_key(self):
        return self.source_id, self.marker_id

    def to_dict(self):
        return dict(participant_id=self.participant_id, name=self.name, color=self.color,
                    source_id=self.source_id, marker_id=self.marker_id)


@dataclass(frozen=True)
class ParticipantState:
    binding: ParticipantBinding
    presence: str
    marker_state: MarkerState | None = None
    zone_id: str | None = None
    zone_observed: bool = False

    @property
    def observed(self):
        return self.presence == 'detected' and self.marker_state is not None and self.marker_state.observed


class ParticipantRegistry:
    MAX_PARTICIPANTS = 64  # four sources, sixteen markers each in the default tracker

    def __init__(self, bindings=()):
        self._bindings = {}
        self._retired = set()
        for binding in bindings:
            if binding.participant_id in self._bindings:
                raise ValueError('Identificador de participant duplicat')
            self.upsert(binding)

    def snapshot(self):
        return MappingProxyType(dict(self._bindings))

    def upsert(self, binding):
        if not isinstance(binding, ParticipantBinding):
            raise ValueError('Cal una vinculació de participant')
        if binding.participant_id not in self._bindings and len(self._bindings) >= self.MAX_PARTICIPANTS:
            raise ValueError('S’ha assolit el límit de participants')
        if any(p.participant_id != binding.participant_id and p.marker_key == binding.marker_key
               for p in self._bindings.values()):
            raise ValueError('Aquest marcador i font ja estan assignats a un altre participant')
        self._bindings[binding.participant_id] = binding

    def remove(self, participant_id):
        del self._bindings[participant_id]
        self._retired.discard(participant_id)

    def set_retired(self, participant_id, retired=True):
        if participant_id not in self._bindings:
            raise ValueError('Participant desconegut')
        if type(retired) is not bool:
            raise ValueError('Estat de retirada no vàlid')
        was_retired = participant_id in self._retired
        if retired:
            self._retired.add(participant_id)
        else:
            self._retired.discard(participant_id)
        return was_retired != retired

    def participant_for(self, source_id, marker_id):
        return next((p for p in self._bindings.values() if p.marker_key == (source_id, marker_id)), None)

    def states(self, markers, zones=None):
        states = {}
        for pid, binding in self._bindings.items():
            marker = markers.get(binding.marker_key)
            presence = 'retired' if pid in self._retired else (marker.presence if marker else 'not_seen')
            zone = (zones or {}).get(binding.marker_key)
            states[pid] = ParticipantState(binding, presence, marker,
                                           zone.zone_id if zone is not None and presence != 'retired' else None,
                                           bool(zone is not None and zone.observed and zone.source_available and presence != 'retired'))
        return MappingProxyType(states)

    def to_dict(self):
        return {'schema_version': 1, 'bindings': [p.to_dict() for p in self._bindings.values()]}

    @classmethod
    def from_project(cls, data):
        if 'participants' not in data:
            return cls()  # legacy projects do not invent people from card names
        block = data['participants']
        if not isinstance(block, dict) or type(block.get('schema_version')) is not int or block['schema_version'] != 1:
            raise ValueError('Versió del registre de participants no compatible')
        rows = block.get('bindings')
        if not isinstance(rows, list) or len(rows) > cls.MAX_PARTICIPANTS:
            raise ValueError('Llista de participants no vàlida')
        fields = {'participant_id', 'name', 'color', 'source_id', 'marker_id'}
        if any(not isinstance(row, dict) or set(row) != fields for row in rows):
            raise ValueError('Vinculació de participant no vàlida')
        return cls(ParticipantBinding(**row) for row in rows)
