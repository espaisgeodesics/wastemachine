"""Passive adapter from common observations to the existing spatial engine.

Each source has independent hysteresis and authorization state. This module
never loads photographs, sends MIDI or changes the public output.
"""
from dataclasses import dataclass, replace
from types import MappingProxyType

from marker_tracking import ObservationFrame
from spatial_zones import SpatialEngine, SpatialMap


@dataclass(frozen=True)
class CommonZoneState:
    source_id: str
    marker_id: int
    zone_id: str | None
    floor_position: tuple[float, float] | None
    observed: bool
    source_available: bool
    calibrated: bool
    updated_at: float
    zone_name: str | None = None


class CommonSpatialObserver:
    def __init__(self, config=None, max_sources=4):
        if type(max_sources) is not int or not 1 <= max_sources <= 32:
            raise ValueError('Límit de fonts espacials no vàlid')
        self.max_sources = max_sources
        self.configure(config if config is not None else SpatialMap(), reset=True)

    def configure(self, config, reset=False):
        if not isinstance(config, SpatialMap):
            raise ValueError('Cal un mapa espacial vàlid')
        if reset or not hasattr(self, 'config') or config != self.config:
            self._engines = {}
            self._frames = {}
            self._states = {}
        self.config = config
        self._names = {zone.id: zone.name for zone in config.zones}

    def zone_names(self):
        return MappingProxyType(dict(self._names))

    def snapshot(self):
        return MappingProxyType(dict(self._states))

    def update(self, frame):
        if not isinstance(frame, ObservationFrame):
            raise ValueError('Cal un fotograma d’observacions')
        previous = self._frames.get(frame.source_id)
        if previous is not None:
            if frame.sequence <= previous.sequence or frame.captured_at <= previous.captured_at:
                raise ValueError('La seqüència i el temps espacials han de créixer per font')
        elif len(self._frames) >= self.max_sources:
            raise ValueError('S’ha assolit el límit de fonts espacials')
        if frame.status == 'unavailable':
            # An unavailable image cannot establish a physical zone exit.
            self._states = {key: replace(state, observed=False, source_available=False,
                                        updated_at=frame.captured_at) if key[0] == frame.source_id else state
                            for key, state in self._states.items()}
            self._frames[frame.source_id] = frame
            return ()
        engine = self._engines.get(frame.source_id)
        if engine is None:
            engine = SpatialEngine(self.config)
        points = {o.marker_id: o.position for o in frame.observations}
        result = engine.update_camera(points, frame.captured_at)
        updated = dict(self._states)
        ids = set(points) | {marker for source, marker in updated if source == frame.source_id}
        for marker in sorted(ids):
            key = frame.source_id, marker
            old = updated.get(key)
            floor = (self.config.calibration.project(points[marker])
                     if marker in points and self.config.calibration is not None else
                     old.floor_position if old is not None else None)
            updated[key] = CommonZoneState(frame.source_id, marker, engine.confirmed_zone(marker), floor,
                                           marker in points and self.config.calibration is not None,
                                           True, self.config.calibration is not None, frame.captured_at,
                                           self._names.get(engine.confirmed_zone(marker)))
        self._engines[frame.source_id] = engine
        self._states = updated
        self._frames[frame.source_id] = frame
        return result.events
