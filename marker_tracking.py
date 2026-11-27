"""Read-only marker tracking. No camera, GUI, MIDI, floor mapping or game actions."""
from dataclasses import dataclass, replace
from math import isfinite
from numbers import Real
from types import MappingProxyType


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, Real) or not isfinite(value):
        raise ValueError(f'{name} must be a finite number')
    return float(value)


def _integer(value, name, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f'Invalid {name}')
    return value


def _point(value):
    if not isinstance(value, (tuple, list)) or len(value) != 2:
        raise ValueError('Expected a normalized camera point')
    point = tuple(_number(v, 'coordinate') for v in value)
    if any(not 0 <= v <= 1 for v in point):
        raise ValueError('Camera coordinates must be normalized to [0, 1]')
    return point


@dataclass(frozen=True)
class MarkerObservation:
    marker_id: int
    position: tuple[float, float]
    orientation: float  # turns in [0, 1), as in the legacy detector path
    corners: tuple[tuple[float, float], ...] = ()

    def __post_init__(self):
        _integer(self.marker_id, 'marker ID', 0, 15)
        object.__setattr__(self, 'position', _point(self.position))
        angle = _number(self.orientation, 'orientation')
        if not 0 <= angle < 1:
            raise ValueError('Orientation must be in [0, 1) turns')
        object.__setattr__(self, 'orientation', angle)
        corners = tuple(_point(point) for point in self.corners)
        if corners and len(corners) != 4:
            raise ValueError('Expected four marker corners')
        object.__setattr__(self, 'corners', corners)


@dataclass(frozen=True)
class ObservationFrame:
    source_id: str
    sequence: int
    captured_at: float
    observations: tuple[MarkerObservation, ...] = ()
    status: str = 'ok'
    coordinate_space: str = 'camera_normalized'

    def __post_init__(self):
        if not isinstance(self.source_id, str) or not self.source_id.strip() or len(self.source_id) > 128:
            raise ValueError('Invalid source ID')
        _integer(self.sequence, 'frame sequence', 0, 2**63-1)
        stamp = _number(self.captured_at, 'capture time')
        if stamp < 0:
            raise ValueError('Capture time must be nonnegative')
        object.__setattr__(self, 'captured_at', stamp)
        if self.status not in ('ok', 'unavailable') or self.coordinate_space != 'camera_normalized':
            raise ValueError('Invalid frame status or coordinate space')
        observations = tuple(self.observations)
        if any(not isinstance(o, MarkerObservation) for o in observations):
            raise ValueError('Invalid marker observation')
        if len({o.marker_id for o in observations}) != len(observations):
            raise ValueError('Duplicate marker ID in one frame')
        if self.status == 'unavailable' and observations:
            raise ValueError('An unavailable source cannot contain detections')
        object.__setattr__(self, 'observations', observations)


@dataclass(frozen=True)
class ObservationSample:
    captured_at: float
    position: tuple[float, float]
    orientation: float


@dataclass(frozen=True)
class MarkerState:
    source_id: str
    marker_id: int
    first_seen: float
    last_seen: float
    updated_at: float
    last_observation: MarkerObservation
    presence: str  # detected, temporarily_lost, absent, retired
    observed: bool
    source_available: bool
    history: tuple[ObservationSample, ...]

    @property
    def age_s(self):
        return self.updated_at - self.last_seen


@dataclass(frozen=True)
class SourceState:
    source_id: str
    sequence: int
    captured_at: float
    status: str


class MarkerTracker:
    """Stable physical identities keyed by (source, ID), not participant identities.

    A valid empty frame can confirm absence. A source outage cannot: its markers
    remain temporarily lost until valid observations resume. Retirement is explicit.
    """
    def __init__(self, absence_after_s=1., history_limit=90, history_duration_s=2.5, max_sources=4):
        self.absence_after_s = _number(absence_after_s, 'absence threshold')
        self.history_duration_s = _number(history_duration_s, 'history duration')
        if self.absence_after_s <= 0 or self.history_duration_s <= 0:
            raise ValueError('Tracking durations must be positive')
        self.history_limit = _integer(history_limit, 'history limit', 1, 512)
        self.max_sources = _integer(max_sources, 'source limit', 1, 32)
        self._markers = {}
        self._sources = {}

    def snapshot(self):
        return MappingProxyType(dict(self._markers))

    def sources(self):
        return MappingProxyType(dict(self._sources))

    def update(self, frame):
        if not isinstance(frame, ObservationFrame):
            raise ValueError('Expected an ObservationFrame')
        previous = self._sources.get(frame.source_id)
        if previous is not None:
            if frame.sequence <= previous.sequence or frame.captured_at <= previous.captured_at:
                raise ValueError('Frame sequence and capture time must strictly increase per source')
        elif len(self._sources) >= self.max_sources:
            raise ValueError('Tracking source limit reached')
        # Build a complete replacement before changing any published state.
        now = frame.captured_at
        updated = dict(self._markers)
        observations = {o.marker_id: o for o in frame.observations}
        ids = set(observations) | {marker for source, marker in updated if source == frame.source_id}
        for marker in sorted(ids):
            key = frame.source_id, marker
            old = updated.get(key)
            observation = observations.get(marker)
            history = tuple(s for s in old.history if now-s.captured_at <= self.history_duration_s) if old else ()
            if old is not None and old.presence == 'retired':
                updated[key] = replace(old, updated_at=now, source_available=frame.status == 'ok', history=history)
            elif observation is not None:
                history = (history + (ObservationSample(now, observation.position, observation.orientation),))[-self.history_limit:]
                updated[key] = MarkerState(frame.source_id, marker, old.first_seen if old else now, now, now,
                                           observation, 'detected', True, True, history)
            elif old is not None:
                presence = 'absent' if frame.status == 'ok' and now-old.last_seen >= self.absence_after_s else 'temporarily_lost'
                updated[key] = replace(old, updated_at=now, presence=presence, observed=False,
                                       source_available=frame.status == 'ok', history=history)
        self._markers = updated
        self._sources = dict(self._sources, **{frame.source_id: SourceState(frame.source_id, frame.sequence, now, frame.status)})
        return self.snapshot()

    def retire(self, source_id, marker_id):
        """Explicit development API; camera loss never calls this method."""
        _integer(marker_id, 'marker ID', 0, 15)
        key = source_id, marker_id
        if key not in self._markers:
            raise ValueError('Unknown marker')
        self._markers = dict(self._markers)
        self._markers[key] = replace(self._markers[key], presence='retired', observed=False)
        return self._markers[key]
