"""Phase 1 spatial engine. No Tk, MIDI, camera capture or image playback.

All floor coordinates use a unit square with a circular floor of radius .5.
Camera inputs require calibration. update_normalized is an explicit simulation API.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import floor, hypot, isfinite
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

import numpy as np

Point = tuple[float, float]
Cell = tuple[int, int]  # row, column
SCHEMA_VERSION = 1
PROJECT_KEY = 'spatial_zones'


def _number(value, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError(f'{label} must be a finite number')
    return float(value)


def _integer(value, label: str, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f'{label} must be an integer in {minimum}..{maximum}')
    return value


def _point(value) -> Point:
    if not isinstance(value, (tuple, list)) or len(value) != 2:
        raise ValueError('A point must contain x and y')
    return _number(value[0], 'x'), _number(value[1], 'y')


@dataclass(frozen=True)
class Grid:
    rows: int = 8
    columns: int = 8

    def __post_init__(self):
        _integer(self.rows, 'rows', 1, 128)
        _integer(self.columns, 'columns', 1, 128)

    def eligible(self, cell: Cell) -> bool:
        row, column = cell
        _integer(row, 'row', 0, self.rows - 1)
        _integer(column, 'column', 0, self.columns - 1)
        nearest_x = max(column / self.columns, min(.5, (column + 1) / self.columns))
        nearest_y = max(row / self.rows, min(.5, (row + 1) / self.rows))
        # A zero-area tangency is not an interactive part of the floor.
        return hypot(nearest_x - .5, nearest_y - .5) < .5

    def cell_at(self, point: Point) -> Cell | None:
        x, y = _point(point)
        if not (0 <= x <= 1 and 0 <= y <= 1) or hypot(x - .5, y - .5) > .5 + 1e-12:
            return None
        def index(value, count):
            scaled = value * count
            if abs(scaled - round(scaled)) < 1e-10:
                scaled = round(scaled)
            return min(count - 1, floor(scaled))
        return index(y, self.rows), index(x, self.columns)

    def expanded_contains(self, cell: Cell, point: Point, margin: float) -> bool:
        row, column = cell
        x, y = point
        return (column / self.columns - margin <= x <= (column + 1) / self.columns + margin
                and row / self.rows - margin <= y <= (row + 1) / self.rows + margin)


@dataclass(frozen=True)
class Zone:
    id: str
    name: str
    cells: frozenset[Cell]
    authorized_cards: frozenset[int]
    image_path: str | None = None
    enabled: bool = True

    def __post_init__(self):
        for key in ('id', 'name'):
            value = getattr(self, key)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f'Zone {key} must be nonempty text')
            object.__setattr__(self, key, value.strip())
        cells = []
        for cell in self.cells:
            if not isinstance(cell, (tuple, list)) or len(cell) != 2 or any(type(n) is not int for n in cell):
                raise ValueError('Cells must contain integer row and column')
            cells.append(tuple(cell))
        if not cells:
            raise ValueError('A zone must contain at least one cell')
        object.__setattr__(self, 'cells', frozenset(cells))
        cards = frozenset(self.authorized_cards)
        for card in cards:
            _integer(card, 'ArUco ID', 0, 15)
        object.__setattr__(self, 'authorized_cards', cards)
        if type(self.enabled) is not bool:
            raise ValueError('enabled must be a boolean')
        if self.image_path is not None:
            if not isinstance(self.image_path, str):
                raise ValueError('image_path must be text or null')
            path = self.image_path.strip() or None
            if path and Path(path).suffix.lower() not in ('.jpg', '.jpeg', '.png'):
                raise ValueError('Only JPG and PNG images are supported')
            object.__setattr__(self, 'image_path', path)


@dataclass(frozen=True)
class Stabilization:
    enter_delay_s: float = .15
    exit_delay_s: float = .20
    min_detections: int = 3
    hysteresis: float = .01
    max_detection_gap_s: float = .20

    def __post_init__(self):
        for key in ('enter_delay_s', 'exit_delay_s', 'hysteresis', 'max_detection_gap_s'):
            value = _number(getattr(self, key), key)
            if value < 0 or (key == 'max_detection_gap_s' and value == 0):
                raise ValueError(f'Invalid {key}')
            object.__setattr__(self, key, value)
        _integer(self.min_detections, 'min_detections', 1, 1000)


def _quad(points) -> tuple[Point, ...]:
    points = tuple(_point(point) for point in points)
    if len(points) != 4 or any(not 0 <= n <= 1 for point in points for n in point):
        raise ValueError('Calibration requires four normalized points in perimeter order')
    crosses = []
    for i in range(4):
        a, b, c = points[i], points[(i + 1) % 4], points[(i + 2) % 4]
        crosses.append((b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]))
    area = abs(sum(points[i][0] * points[(i + 1) % 4][1] - points[(i + 1) % 4][0] * points[i][1] for i in range(4))) / 2
    if area < 1e-4 or not (all(c > 1e-8 for c in crosses) or all(c < -1e-8 for c in crosses)):
        raise ValueError('Calibration points must form a nondegenerate convex quadrilateral')
    return points


@dataclass(frozen=True)
class Calibration:
    # Corresponding physical markers: north, east, south, west of the floor.
    camera_points: tuple[Point, ...]
    floor_points: tuple[Point, ...] = ((.5, 0), (1, .5), (.5, 1), (0, .5))
    _matrix: np.ndarray = field(init=False, repr=False, compare=False)

    def __post_init__(self):
        source, target = _quad(self.camera_points), _quad(self.floor_points)
        object.__setattr__(self, 'camera_points', source)
        object.__setattr__(self, 'floor_points', target)
        rows, values = [], []
        for (x, y), (u, v) in zip(source, target):
            rows.extend(((x, y, 1, 0, 0, 0, -u*x, -u*y), (0, 0, 0, x, y, 1, -v*x, -v*y)))
            values.extend((u, v))
        system = np.array(rows, dtype=np.float64)
        if np.linalg.cond(system) > 1e10:
            raise ValueError('Ill-conditioned calibration')
        try:
            matrix = np.append(np.linalg.solve(system, values), 1).reshape(3, 3)
        except np.linalg.LinAlgError as exc:
            raise ValueError('Invalid calibration') from exc
        if abs(np.linalg.det(matrix)) < 1e-10:
            raise ValueError('Singular calibration')
        denominators = [matrix[2] @ np.array((x, y, 1)) for x, y in source]
        if not (all(d > 1e-8 for d in denominators) or all(d < -1e-8 for d in denominators)):
            raise ValueError('Calibration crosses a projective horizon')
        inverse = np.linalg.inv(matrix)
        center = inverse[2] @ np.array((.5, .5, 1))
        extent = .5 * hypot(inverse[2, 0], inverse[2, 1])
        if abs(center) <= extent + 1e-8:
            raise ValueError('Calibration horizon intersects the circular floor')
        matrix.setflags(write=False)
        object.__setattr__(self, '_matrix', matrix)

    def unproject(self, floor_point: Point) -> Point | None:
        """Map a normalized floor point back onto the original camera image."""
        x, y = _point(floor_point)
        if not (0 <= x <= 1 and 0 <= y <= 1):
            return None
        result = np.linalg.solve(self._matrix, np.array((x, y, 1)))
        if abs(result[2]) < 1e-10:
            return None
        point = result[:2] / result[2]
        return (float(point[0]), float(point[1])) if np.isfinite(point).all() else None

    def project(self, camera_point: Point) -> Point | None:
        x, y = _point(camera_point)
        if not (0 <= x <= 1 and 0 <= y <= 1):
            return None
        result = self._matrix @ np.array((x, y, 1))
        if abs(result[2]) < 1e-10:
            return None
        point = result[:2] / result[2]
        point[np.abs(point) < 1e-10] = 0
        point[np.abs(point - 1) < 1e-10] = 1
        return (float(point[0]), float(point[1])) if np.isfinite(point).all() else None


@dataclass(frozen=True)
class SpatialMap:
    grid: Grid = field(default_factory=Grid)
    zones: tuple[Zone, ...] = ()
    calibration: Calibration | None = None
    stabilization: Stabilization = field(default_factory=Stabilization)
    _owners: Mapping[Cell, Zone] = field(init=False, repr=False, compare=False)

    def __post_init__(self):
        if not isinstance(self.grid, Grid) or not isinstance(self.stabilization, Stabilization):
            raise ValueError('Invalid grid or stabilization')
        if self.calibration is not None and not isinstance(self.calibration, Calibration):
            raise ValueError('Invalid calibration')
        if self.stabilization.hysteresis >= .5 * min(1 / self.grid.rows, 1 / self.grid.columns):
            raise ValueError('Hysteresis must be smaller than half a cell')
        zones = tuple(self.zones)
        ids, owners = set(), {}
        for zone in zones:
            if not isinstance(zone, Zone) or zone.id in ids:
                raise ValueError('Zone IDs must be unique')
            ids.add(zone.id)
            for cell in zone.cells:
                if not self.grid.eligible(cell):
                    raise ValueError(f'Cell {cell} lies outside the circular floor')
                if zone.enabled:
                    if cell in owners:
                        raise ValueError(f'Active zones overlap at {cell}')
                    owners[cell] = zone
        object.__setattr__(self, 'zones', zones)
        object.__setattr__(self, '_owners', MappingProxyType(owners))

    def to_dict(self) -> dict:
        calibration = None if self.calibration is None else {
            'camera_points': [list(p) for p in self.calibration.camera_points],
            'floor_points': [list(p) for p in self.calibration.floor_points]}
        return {'schema_version': SCHEMA_VERSION,
                'grid': {'rows': self.grid.rows, 'columns': self.grid.columns},
                'zones': [{'id': z.id, 'name': z.name, 'cells': [list(c) for c in sorted(z.cells)],
                           'authorized_cards': sorted(z.authorized_cards), 'image_path': z.image_path,
                           'enabled': z.enabled} for z in self.zones],
                'calibration': calibration,
                'stabilization': {key: getattr(self.stabilization, key) for key in
                                  ('enter_delay_s', 'exit_delay_s', 'min_detections', 'hysteresis', 'max_detection_gap_s')}}

    @classmethod
    def from_dict(cls, data: dict) -> SpatialMap:
        if not isinstance(data, dict) or type(data.get('schema_version')) is not int or data['schema_version'] != SCHEMA_VERSION:
            raise ValueError('Unsupported spatial map schema')
        try:
            zones = tuple(Zone(**zone) for zone in data.get('zones', []))
            calibration = data.get('calibration')
            return cls(Grid(**data.get('grid', {})), zones,
                       Calibration(**calibration) if calibration is not None else None,
                       Stabilization(**data.get('stabilization', {})))
        except (TypeError, KeyError) as exc:
            raise ValueError('Malformed spatial map') from exc

    @classmethod
    def from_project(cls, project: dict) -> SpatialMap:
        if not isinstance(project, dict):
            raise ValueError('A project must be a JSON object')
        data = project.get(PROJECT_KEY)
        return cls() if data is None else cls.from_dict(data)

    def into_project(self, project: dict) -> dict:
        if not isinstance(project, dict):
            raise ValueError('A project must be a JSON object')
        return dict(project, **{PROJECT_KEY: self.to_dict()})


@dataclass(frozen=True)
class AssetCheck:
    status: str
    path: Path | None


def image_reference(image_file: str | Path, project_file: str | Path) -> str:
    """Store files inside the project directory relatively; keep external paths absolute."""
    image = Path(image_file).resolve()
    parent = Path(project_file).resolve().parent
    try:
        return image.relative_to(parent).as_posix()
    except ValueError:
        return str(image)


def check_image_asset(reference: str | None, project_file: str | Path | None) -> AssetCheck:
    if not reference:
        return AssetCheck('not_assigned', None)
    path = Path(reference)
    if path.suffix.lower() not in ('.jpg', '.jpeg', '.png'):
        return AssetCheck('unsupported', path)
    if not path.is_absolute():
        if project_file is None:
            return AssetCheck('unresolved', None)
        path = Path(project_file).resolve().parent / path
    try:
        return AssetCheck('exists' if path.is_file() else 'missing', path)
    except OSError:
        return AssetCheck('unreadable', path)


@dataclass(frozen=True)
class ZoneEvent:
    kind: str
    card_id: int
    zone_id: str
    at: float
    reason: str = 'movement'


@dataclass(frozen=True)
class Scene:
    zone_id: str
    image_path: str
    card_id: int
    confirmed_at: float


@dataclass(frozen=True)
class FrameResult:
    status: str
    events: tuple[ZoneEvent, ...]
    scene: Scene | None
    scene_changed: bool = False
    image_changed: bool = False


@dataclass
class _CardState:
    confirmed: str | None = None
    last_entered: str | None = None
    candidate: str | None = None
    candidate_since: float = 0
    detections: int = 0
    last_seen: float | None = None


class SpatialEngine:
    def __init__(self, spatial_map: SpatialMap):
        if not isinstance(spatial_map, SpatialMap):
            raise ValueError('Expected SpatialMap')
        self.map = spatial_map
        self.scene: Scene | None = None
        self._states: dict[int, _CardState] = {}
        self._zones = {z.id: z for z in spatial_map.zones}
        self._last_frame: float | None = None

    def confirmed_zone(self, card_id: int) -> str | None:
        state = self._states.get(card_id)
        return state.confirmed if state else None

    def last_entered_zone(self, card_id: int) -> str | None:
        state = self._states.get(card_id)
        return state.last_entered if state else None

    def update_camera(self, observations: Mapping[int, Point], now: float) -> FrameResult:
        points = self._validate_frame(observations, now)
        if self.map.calibration is None:
            self._last_frame = float(now)
            return FrameResult('uncalibrated', (), self.scene)
        projected = {card: self.map.calibration.project(point) for card, point in points.items()}
        return self._update(projected, float(now))

    def update_normalized(self, observations: Mapping[int, Point], now: float) -> FrameResult:
        """Explicit simulation/testing API; these coordinates are already floor coordinates."""
        return self._update(self._validate_frame(observations, now), float(now))

    def _validate_frame(self, observations, now):
        now = _number(now, 'timestamp')
        if now < 0 or (self._last_frame is not None and now <= self._last_frame):
            raise ValueError('Frame timestamps must increase strictly')
        if not isinstance(observations, Mapping):
            raise ValueError('Observations must map ArUco IDs to points')
        result = {}
        for card, point in observations.items():
            _integer(card, 'ArUco ID', 0, 15)
            result[card] = _point(point)
        return result

    def _candidate(self, card, point, confirmed):
        if point is None or self.map.grid.cell_at(point) is None:
            return None
        if confirmed is not None:
            previous = self._zones[confirmed]
            if previous.enabled and card in previous.authorized_cards and any(
                    self.map.grid.expanded_contains(cell, point, self.map.stabilization.hysteresis)
                    for cell in previous.cells):
                return confirmed
        zone = self.map._owners.get(self.map.grid.cell_at(point))
        return zone.id if zone is not None and card in zone.authorized_cards else None

    def _update(self, observations, now):
        self._last_frame = now
        options = self.map.stabilization
        events = []
        for card in sorted(set(observations) | set(self._states)):
            state = self._states.setdefault(card, _CardState())
            visible = card in observations
            if visible and state.last_seen is not None and now - state.last_seen > options.max_detection_gap_s:
                if state.confirmed is not None:
                    events.append(ZoneEvent('exit', card, state.confirmed, now, 'detection_gap'))
                state.confirmed = state.candidate = None
                state.detections = 0
            if visible:
                state.last_seen = now
            candidate = self._candidate(card, observations.get(card), state.confirmed) if visible else None
            if candidate == state.confirmed:
                state.candidate = candidate
                state.candidate_since = now
                state.detections = 0
                continue
            if candidate != state.candidate or state.detections == 0:
                state.candidate = candidate
                state.candidate_since = now
                state.detections = 1
            else:
                state.detections += 1
            if candidate is None:
                ready = now - state.candidate_since + 1e-12 >= options.exit_delay_s
            else:
                ready = state.detections >= options.min_detections and now - state.candidate_since + 1e-12 >= options.enter_delay_s
            if not ready:
                continue
            if state.confirmed is not None:
                events.append(ZoneEvent('exit', card, state.confirmed, now, 'missing' if not visible else 'movement'))
            state.confirmed = candidate
            if candidate is not None:
                state.last_entered = candidate
                events.append(ZoneEvent('enter', card, candidate, now))
            state.detections = 0
        # Same frame = same confirmation time. Lowest ArUco ID wins the tie,
        # independent of detector/dictionary iteration order.
        entries = [event for event in events if event.kind == 'enter' and self._zones[event.zone_id].image_path]
        scene_changed = image_changed = False
        if entries:
            event = min(entries, key=lambda e: e.card_id)
            zone = self._zones[event.zone_id]
            scene_changed = self.scene is None or (self.scene.zone_id, self.scene.image_path) != (zone.id, zone.image_path)
            image_changed = self.scene is None or self.scene.image_path != zone.image_path
            self.scene = Scene(zone.id, zone.image_path, event.card_id, now)
        return FrameResult('ok', tuple(events), self.scene, scene_changed, image_changed)
