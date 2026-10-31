"""Bounded passive event journal. Events never dispatch MIDI or public visuals."""
from collections import deque
from dataclasses import dataclass
from math import isfinite
from numbers import Real


@dataclass(frozen=True)
class DomainEvent:
    sequence: int
    occurred_at: float
    kind: str
    source_id: str
    frame_sequence: int | None = None
    marker_id: int | None = None
    participant_id: str | None = None


class CommonEventLog:
    def __init__(self, limit=500):
        if type(limit) is not int or not 1 <= limit <= 10000:
            raise ValueError('Límit de registre no vàlid')
        self._events = deque(maxlen=limit)
        self._sequence = 0
        self._sources = {}
        self._markers = {}

    def snapshot(self):
        return tuple(self._events)

    def _record(self, now, kind, source, frame_sequence=None, marker_id=None, participant_id=None):
        self._sequence += 1
        event = DomainEvent(self._sequence, now, kind, source, frame_sequence, marker_id, participant_id)
        self._events.append(event)
        return event

    def consume(self, frame, states, registry):
        """Call only after the tracker accepts a frame. Replays are ignored.

        Position changes do not generate events. Source outages cannot confirm
        absence; the tracker owns that distinction. Bindings annotate events at
        creation time, so editing a name/binding never rewrites history.
        """
        previous = self._sources.get(frame.source_id)
        if previous is not None and frame.sequence <= previous[0]:
            return ()
        emitted = []
        if previous is None or previous[1] != frame.status:
            kind = 'source_available' if frame.status == 'ok' else 'source_unavailable'
            emitted.append(self._record(frame.captured_at, kind, frame.source_id, frame.sequence))
        for key, state in sorted(states.items()):
            if key[0] != frame.source_id:
                continue
            old = self._markers.get(key)
            kind = None
            if state.presence == 'detected' and old != 'detected':
                kind = 'marker_recovered' if old == 'temporarily_lost' else 'marker_appeared'
            elif state.presence != old:
                kind = {'temporarily_lost': 'marker_temporarily_lost',
                        'absent': 'marker_absent', 'retired': 'marker_retired'}.get(state.presence)
            if kind:
                participant = registry.participant_for(*key)
                emitted.append(self._record(frame.captured_at, kind, frame.source_id, frame.sequence, key[1],
                                            participant.participant_id if participant else None))
            self._markers[key] = state.presence
        self._sources[frame.source_id] = (frame.sequence, frame.status)
        return tuple(emitted)

    def participant_retirement(self, registry, participant_id, retired, now):
        if isinstance(now, bool) or not isinstance(now, Real) or not isfinite(now) or now < 0:
            raise ValueError('Temps de sessió no vàlid')
        binding = registry.snapshot()[participant_id]
        if registry.set_retired(participant_id, retired):
            return self._record(now, 'participant_retired' if retired else 'participant_restored',
                                binding.source_id, marker_id=binding.marker_id, participant_id=participant_id)
