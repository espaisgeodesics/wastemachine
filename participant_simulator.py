"""Five-person virtual source using the production observation/tracking contract.

The session is deliberately isolated from real camera bindings and outputs.
Virtual positions use camera_normalized coordinates, never calibrated floor data.
"""
from dataclasses import dataclass, replace
from math import isfinite
from numbers import Real

from domain_events import CommonEventLog
from marker_tracking import MarkerObservation, MarkerTracker, ObservationFrame
from participants import ParticipantBinding, ParticipantRegistry
from common_spatial import CommonSpatialObserver
from spatial_zones import Calibration, SpatialMap


SOURCE_ID = 'simulator:0'
COLORS = ('#48B8E8', '#F7A541', '#91CF60', '#E574C7', '#B19CFF')
POSITIONS = ((.25, .3), (.5, .25), (.75, .3), (.35, .7), (.65, .7))


class SimulatorRegistry(ParticipantRegistry):
    MAX_PARTICIPANTS = 5

    def upsert(self, binding):
        if not isinstance(binding, ParticipantBinding) or binding.source_id != SOURCE_ID:
            raise ValueError('El simulador només utilitza la font simulator:0')
        super().upsert(binding)


@dataclass(frozen=True)
class VirtualPose:
    position: tuple[float, float]
    orientation: float = 0.
    visible: bool = True


class SimulatorSession:
    def __init__(self):
        self.registry = SimulatorRegistry(ParticipantBinding(f'virtual-{i+1}', f'Participant {i+1}',
                                                            COLORS[i], SOURCE_ID, i) for i in range(5))
        self.tracker = MarkerTracker()
        self.events = CommonEventLog()
        self.spatial = CommonSpatialObserver(SpatialMap(calibration=Calibration(((.5, 0), (1, .5), (.5, 1), (0, .5)))))
        self.available = True
        self.sequence = 0
        self._poses = {}
        self._last_time = None

    def reset(self):
        """Start a new virtual session, preserving no old detections or events."""
        config = self.spatial.config
        self.__init__()
        self.configure_spatial(config)

    def configure_spatial(self, config):
        if not isinstance(config, SpatialMap):
            raise ValueError('Cal un mapa espacial vàlid')
        # Synthetic identity calibration belongs only to this virtual source.
        virtual = replace(config, calibration=Calibration(((.5, 0), (1, .5), (.5, 1), (0, .5))))
        self.spatial.configure(virtual, reset=True)

    def poses(self):
        bindings = self.registry.snapshot()
        self._poses = {pid: self._poses.get(pid, VirtualPose(POSITIONS[i]))
                       for i, pid in enumerate(bindings)}
        return dict(self._poses)

    def set_pose(self, participant_id, position=None, orientation=None, visible=None):
        poses = self.poses()
        if participant_id not in poses:
            raise ValueError('Participant virtual desconegut')
        old = poses[participant_id]
        observation = MarkerObservation(self.registry.snapshot()[participant_id].marker_id,
                                        old.position if position is None else position,
                                        old.orientation if orientation is None else orientation)
        if visible is not None and type(visible) is not bool:
            raise ValueError('Visibilitat no vàlida')
        self._poses[participant_id] = VirtualPose(observation.position, observation.orientation,
                                                old.visible if visible is None else visible)

    def _validate_time(self, now):
        if isinstance(now, bool) or not isinstance(now, Real) or not isfinite(now) or now < 0:
            raise ValueError('Temps de simulació no vàlid')
        if self._last_time is not None and now <= self._last_time:
            raise ValueError('El temps de simulació ha de créixer')

    def advance(self, now):
        self._validate_time(now)
        poses = self.poses()
        states = self.registry.states(self.tracker.snapshot())
        observations = tuple(MarkerObservation(p.marker_id, poses[pid].position, poses[pid].orientation)
                             for pid, p in self.registry.snapshot().items()
                             if poses[pid].visible and states[pid].presence != 'retired') if self.available else ()
        frame = ObservationFrame(SOURCE_ID, self.sequence + 1, now, observations,
                                 'ok' if self.available else 'unavailable')
        tracked = self.tracker.update(frame)
        batch = self.events.consume(frame, tracked, self.registry)
        batch += self.events.record_zones(frame, self.spatial.update(frame), self.registry, self.spatial.zone_names())
        self.sequence = frame.sequence
        self._last_time = now
        return frame, batch

    def set_retired(self, participant_id, retired, now):
        # Retirement does not remove the binding or let re-detection restore it.
        event = self.events.participant_retirement(self.registry, participant_id, retired, now)
        if not retired:
            self.set_pose(participant_id, visible=True)
        return event
