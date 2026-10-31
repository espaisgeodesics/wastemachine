"""Kaoss XY reference engine. Explicit clock and MIDI sink; no device or GUI access."""
from dataclasses import asdict, dataclass
from math import ceil, exp, isfinite
from numbers import Real
from rule_outputs import MidiCommand

KAOSS_FUNCTION = 'Kaoss XY espacial'
SCALES = {'Major': (0, 2, 4, 5, 7, 9, 11),
          'Menor natural': (0, 2, 3, 5, 7, 8, 10),
          'Pentatònica menor': (0, 3, 5, 7, 10),
          'Pentatònica major': (0, 2, 4, 7, 9),
          'Cromàtica': tuple(range(12))}
PRESETS = ('ATMOSFERA', 'PULSACIÓ', 'TRANSFORMACIÓ', 'ÒRBITA')


def _real(value, low, high, name):
    if isinstance(value, bool) or not isinstance(value, Real) or not isfinite(value) or not low <= value <= high:
        raise ValueError(f'{name}: cal un valor entre {low} i {high}')


def _int(value, low, high, name):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f'{name}: cal un enter entre {low} i {high}')


@dataclass(frozen=True)
class KaossConfig:
    mode: str = 'Instrument'
    channel: int = 2
    root: int = 9
    scale: str = 'Pentatònica menor'
    note_min: int = 48
    note_max: int = 84
    velocity: int = 90
    y_velocity: bool = False
    x_cc: int = 74
    y_cc: int = 74
    rotation_cc: int = 11
    rotation_enabled: bool = True
    invert_x: bool = False
    invert_y: bool = True  # camera Y grows downwards
    invert_rotation: bool = False
    smoothing_s: float = .08
    deadzone: float = .015
    quantize_beats: float = 0.
    lost_timeout_s: float = .25

    def __post_init__(self):
        if self.mode not in ('Instrument', 'Efectes') or self.scale not in SCALES:
            raise ValueError('Mode o escala Kaoss no vàlids')
        for name in ('y_velocity', 'rotation_enabled', 'invert_x', 'invert_y', 'invert_rotation'):
            if type(getattr(self, name)) is not bool:raise ValueError(f'{name}: cal un booleà')
        _int(self.channel, 1, 16, 'Canal')
        _int(self.root, 0, 11, 'Tònica')
        _int(self.note_min, 0, 127, 'Nota mínima')
        _int(self.note_max, self.note_min, 127, 'Nota màxima')
        _int(self.velocity, 1, 127, 'Velocitat')
        for name in ('x_cc', 'y_cc', 'rotation_cc'):_int(getattr(self, name), 0, 119, name)
        _real(self.smoothing_s, 0, 2, 'Suavització (s)')
        _real(self.deadzone, 0, .2, 'Zona morta')
        _real(self.lost_timeout_s, .05, 2, 'Absència (s)')
        _real(self.quantize_beats, 0, 1, 'Quantització')
        if self.quantize_beats not in (0, .25, .5, 1):raise ValueError('Quantització: 0, 0.25, 0.5 o 1 temps')
        controls = ([self.x_cc] if self.mode == 'Efectes' else [])
        if self.mode == 'Efectes' or not self.y_velocity:controls.append(self.y_cc)
        if self.rotation_enabled:controls.append(self.rotation_cc)
        if set(controls) & {64, 66, 69}:raise ValueError('Els CC de pedal 64, 66 i 69 no són controls XY')
        if len(set(controls)) != len(controls):raise ValueError('Els eixos actius necessiten CC diferents')
        if not self.pitches():raise ValueError('El rang no conté cap nota de l’escala')

    def pitches(self):
        return tuple(n for n in range(self.note_min, self.note_max+1)
                     if (n-self.root) % 12 in SCALES[self.scale])

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict):raise ValueError('Configuració Kaoss no vàlida')
        try:return cls(**data)
        except TypeError as exc:raise ValueError('Camps Kaoss desconeguts o no vàlids') from exc

    def to_dict(self):return asdict(self)


def preset(name, channel=2):
    if name not in PRESETS:raise ValueError('Preset Kaoss desconegut')
    return KaossConfig(channel=channel, **{
        'ATMOSFERA': {},
        'PULSACIÓ': {'y_velocity': True, 'rotation_cc': 74},
        'TRANSFORMACIÓ': {'mode': 'Efectes', 'x_cc': 74, 'y_cc': 1, 'rotation_cc': 11},
        'ÒRBITA': {'mode': 'Efectes', 'x_cc': 10, 'y_cc': 11, 'rotation_cc': 1},
    }[name])


def validate_assignments(configs, reserved_channels=()):
    if not isinstance(configs, dict) or len(configs) > 16:raise ValueError('Màxim 16 assignacions Kaoss')
    used = set(reserved_channels)
    for marker, config in configs.items():
        _int(marker, 0, 49, 'Marcador')
        if not isinstance(config, KaossConfig):raise ValueError('Configuració Kaoss no vàlida')
        if config.channel in used:raise ValueError(f'Canal {config.channel} ocupat; cada Kaoss necessita un canal exclusiu, separat de les regles')
        used.add(config.channel)


def pack_configs(configs):
    validate_assignments(configs)
    return {'schema_version': 1, 'kaoss_xy': {str(k): c.to_dict() for k, c in sorted(configs.items())}}


def unpack_configs(data):
    if not isinstance(data, dict) or set(data) != {'schema_version', 'kaoss_xy'} or type(data['schema_version']) is not int or data['schema_version'] != 1:
        raise ValueError('Format Kaoss: schema_version 1 necessari')
    block = data['kaoss_xy']
    if not isinstance(block, dict) or len(block) > 16:raise ValueError('Assignacions Kaoss no vàlides')
    result = {}
    for marker, config in block.items():
        if not isinstance(marker, str) or not marker.isascii() or not marker.isdecimal() or str(int(marker)) != marker:
            raise ValueError('ID de marcador Kaoss no vàlid')
        result[int(marker)] = KaossConfig.from_dict(config)
    validate_assignments(result)
    return result


@dataclass
class _Voice:
    last_seen: float
    filtered: tuple
    filter_time: float
    desired: tuple | None = None
    due: float | None = None
    playing: int | None = None
    cc: dict = None
    last_cc_time: float = float('-inf')
    cancelled: bool = False

    def __post_init__(self):self.cc = {}


class KaossEngine:
    """One channel per marker. No sustain/transport/channel-mode CCs are emitted.

    Feed only current observations. tick must continue during source outages.
    Failed NoteOffs retain ownership and block replacement notes until retried.
    No NoteOn is queued for a future connection when the sink rejects it.
    """
    def __init__(self, configs=None):
        self.configs = dict(configs or {})
        validate_assignments(self.configs)
        self.voices = {}
        self.last_time = None

    def _time(self, now):
        _real(now, 0, float('inf'), 'Temps Kaoss')
        if self.last_time is not None and now < self.last_time:raise ValueError('El temps Kaoss no pot retrocedir')
        self.last_time = now

    @staticmethod
    def _send(send, command):
        if send is None:return False
        try:return send(command) is not False
        except Exception:return False

    def observe(self, marker, x, y, rotation, now):
        _int(marker, 0, 49, 'Marcador')
        for name, value in (('X', x), ('Y', y), ('Rotació', rotation)):_real(value, 0, 1, name)
        self._time(now)
        config = self.configs.get(marker)
        if config is None:return
        target = (1-x if config.invert_x else x, 1-y if config.invert_y else y,
                  (1-rotation) % 1 if config.invert_rotation else rotation % 1)
        state = self.voices.get(marker)
        if state is None:
            state = self.voices[marker] = _Voice(now, target, now)
        else:
            alpha = 1 if not config.smoothing_s else 1-exp(-(now-state.filter_time)/config.smoothing_s)
            filtered = []
            for i, (old, new) in enumerate(zip(state.filtered, target)):
                delta = (new-old+.5) % 1-.5 if i == 2 else new-old
                value = old if abs(delta) <= config.deadzone else old+alpha*delta
                filtered.append(value % 1 if i == 2 else value)
            state.filtered = tuple(filtered)
            state.filter_time = now
            state.last_seen = now
        if config.mode == 'Instrument':
            x, y, _ = state.filtered
            pitches = config.pitches()
            note = pitches[min(len(pitches)-1, int(x*len(pitches)))]
            velocity = max(1, round(y*127)) if config.y_velocity else config.velocity
            # Velocity changes apply on the next NoteOn, never retrigger a held pitch.
            state.desired = (note, velocity)

    def tick(self, now, send, bpm=120):
        _real(bpm, 1, 999, 'Tempo')
        self._time(now)
        for marker, state in list(self.voices.items()):
            config = self.configs[marker]
            if state.cancelled or now-state.last_seen >= config.lost_timeout_s:
                state.desired = None
                state.due = None
                if self._off(config, state, send):del self.voices[marker]
                continue
            if config.mode == 'Instrument':
                wanted = state.desired[0] if state.desired else None
                if wanted == state.playing:state.due = None
                elif state.desired is not None and state.due is None:
                    interval = config.quantize_beats*60/bpm
                    state.due = ceil((now-1e-9)/interval)*interval if interval else now
                if state.due is not None and now+1e-9 >= state.due:
                    if self._off(config, state, send):
                        note, velocity = state.desired
                        if self._send(send, MidiCommand('note_on', config.channel, note, velocity)):
                            state.playing = note
                        else:state.desired = None
                        state.due = None
            # Limit CC traffic to at most 50 batches/s/marker; unchanged values deduplicate.
            if now-state.last_cc_time >= .02:
                x, y, rotation = state.filtered
                controls = [(config.x_cc, x)] if config.mode == 'Efectes' else []
                if config.mode == 'Efectes' or not config.y_velocity:controls.append((config.y_cc, y))
                if config.rotation_enabled:controls.append((config.rotation_cc, rotation))
                for number, value in controls:
                    value = round(value*127)
                    if state.cc.get(number) != value and self._send(send, MidiCommand('cc', config.channel, number, value)):
                        state.cc[number] = value
                state.last_cc_time = now

    def _off(self, config, state, send):
        if state.playing is None:return True
        if self._send(send, MidiCommand('note_off', config.channel, state.playing, 0)):
            state.playing = None
            return True
        return False

    def stop(self, send):
        """Cancel pending notes and release owned voices; False means retry required."""
        for marker, state in list(self.voices.items()):
            state.desired = None
            state.due = None
            state.cancelled = True
            if self._off(self.configs[marker], state, send):del self.voices[marker]
        return not self.voices
