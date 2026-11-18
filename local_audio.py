"""Bounded short-clip audio engine and optional pygame-ce backend.

No optional package is imported until the real backend is explicitly created.
The silent backend runs the same voice, group and fade logic without a device.
"""
from collections import OrderedDict
from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from threading import RLock
import wave

MAX_CLIP_BYTES = 8 * 1024 * 1024
MAX_CACHE_BYTES = 32 * 1024 * 1024
MAX_CACHE_ITEMS = 32
MAX_DURATION_S = 7200
SHORT_CLIP_S = 30
STREAM_CHUNK_S = .5
RATE = 48000


@dataclass(frozen=True)
class AudioClip:
    key: tuple
    path: Path
    duration_s: float
    size_bytes: int
    payload: object = None
    streamed: bool = False


@dataclass(frozen=True)
class AudioCommand:
    kind: str
    group: str = ''
    source_id: str = ''
    marker_id: int | None = None
    path: str = ''
    gain: float = 1.
    fade_s: float = 0.
    loop: bool = False
    scope: str = 'marker'
    priority: int = 10

    def __post_init__(self):
        if self.kind not in ('play_sound', 'stop_sound', 'audio_volume'):
            raise ValueError('Ordre d’àudio no vàlida')
        for value, label in ((self.gain, 'volum'), (self.fade_s, 'fade')):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
                raise ValueError(f'{label} no vàlid')
        if not 0 <= self.gain <= 1 or not 0 <= self.fade_s <= 10 or type(self.loop) is not bool or self.scope not in ('marker', 'group'):
            raise ValueError('Paràmetres d’àudio no vàlids')
        if not isinstance(self.group, str) or not self.group.strip() or len(self.group) > 256:
            raise ValueError('Grup d’àudio no vàlid')
        if not isinstance(self.source_id,str) or len(self.source_id)>128 or not isinstance(self.path,str):raise ValueError('Font o ruta d’àudio no vàlida')
        if self.marker_id is not None and (type(self.marker_id) is not int or not 0<=self.marker_id<=15):raise ValueError('ID de marcador no vàlid')
        if type(self.priority) is not int or not 1<=self.priority<=1000:raise ValueError('Prioritat d’àudio no vàlida')


def command_from_request(request, project_file=None):
    action, event = request.action, request.event
    path = ''
    if action.kind == 'play_sound':
        asset = Path(action.value)
        if not asset.is_absolute():
            if project_file is None:
                raise ValueError('Cal desar el projecte o triar una ruta absoluta per al so')
            asset = Path(project_file).resolve().parent / asset
        path = str(asset.resolve())
    return AudioCommand(action.kind, action.audio_group or request.rule.group, event.source_id,
                        event.marker_id, path, action.gain, action.fade_s, action.loop,
                        action.audio_scope, request.rule.priority)


def inspect_clip(path):
    path = Path(path).resolve()
    if path.suffix.lower() not in ('.wav', '.ogg'):
        raise ValueError('Tria un fitxer WAV o OGG')
    stat = path.stat()
    if stat.st_size > 2 * 1024 * 1024 * 1024:
        raise ValueError('El fitxer supera el límit de 2 GiB')
    try:
        if path.suffix.lower() != '.wav':raise wave.Error('Use soundfile')
        with wave.open(str(path), 'rb') as stream:
            rate, channels, frames = stream.getframerate(), stream.getnchannels(), stream.getnframes()
            if stream.getcomptype() != 'NONE':raise wave.Error('Use soundfile')
    except wave.Error:
        import soundfile as sf
        info = sf.info(str(path))
        if info.format not in ('WAV','WAVEX','RF64','OGG'):raise ValueError('El fitxer no és WAV / OGG vàlid')
        rate, channels, frames = info.samplerate, info.channels, info.frames
    if not 8000 <= rate <= 96000 or channels not in (1, 2) or frames <= 0 or frames / rate > MAX_DURATION_S:
        raise ValueError('Àudio mono/estèreo de fins a 2 hores, entre 8 i 96 kHz')
    size = max(1,round(frames * RATE / rate)) * 4  # 48 kHz, signed 16 bit stereo
    # Songs are streamed in bounded chunks instead of decoded into the cache.
    if size > MAX_CLIP_BYTES or frames / rate > SHORT_CLIP_S:size=0
    return path, (str(path), stat.st_mtime_ns, stat.st_size), frames / rate, size


class SilentAudioBackend:
    """Metadata and deterministic playback clock; never opens an audio device."""
    description='Simulació d’àudio sense dispositiu'
    def __init__(self):
        self.cache = OrderedDict()
        self.active = {}
        self.ends = {}
        self.gains = {}
        self.closed = False

    @property
    def cache_bytes(self):
        return sum(clip.size_bytes for clip in self.cache.values())

    def check(self):
        if self.closed:raise RuntimeError('Backend d’àudio tancat')

    def _make_room(self, size):
        while self.cache_bytes + size > MAX_CACHE_BYTES or len(self.cache)>=MAX_CACHE_ITEMS:
            key = next((key for key in self.cache if key not in {clip.key for clip in self.active.values()}), None)
            if key is None:
                raise ValueError('Memòria d’àudio ocupada: atura alguna capa abans de carregar-ne més')
            del self.cache[key]

    def load(self, path):
        if self.closed:
            raise RuntimeError('Backend d’àudio tancat')
        path, key, duration, size = inspect_clip(path)
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]
        self._make_room(size)
        clip = self._decode(path, key, duration, size)
        self._make_room(clip.size_bytes)
        self.cache[key] = clip
        return clip

    def _decode(self, path, key, duration, size):
        return AudioClip(key, path, duration, size, streamed=size==0)

    def start(self, clip, slot, loop, now):
        if self.closed:raise RuntimeError('Backend d’àudio tancat')
        self.active[slot] = clip
        self.ends[slot] = None if loop else now + clip.duration_s

    def volume(self, slot, gain):
        self.gains[slot] = gain

    def stop(self, slot):
        self.active.pop(slot, None);self.ends.pop(slot, None);self.gains.pop(slot, None)

    def busy(self, slot, now):
        if self.closed:raise RuntimeError('Backend d’àudio tancat')
        result = slot in self.active and (self.ends[slot] is None or now < self.ends[slot])
        if not result:self.stop(slot)
        return result

    def close(self):
        self.active.clear();self.ends.clear();self.gains.clear();self.cache.clear();self.closed = True


class PygameAudioBackend(SilentAudioBackend):
    """Exclusive optional SDL mixer. Channels are allocated explicitly, never stolen."""
    _mixer_lock = RLock()
    description='Àudio local actiu · SDL · 48 kHz · clips i cançons'

    def __init__(self):
        super().__init__()
        try:
            import pygame
            import soundfile
        except ImportError as exc:
            raise RuntimeError('Instal·la requirements-audio.txt per activar l’àudio local') from exc
        self.streams = {}
        self.pg = pygame
        self.sf = soundfile
        with self._mixer_lock:
            if pygame.mixer.get_init() is not None:
                raise RuntimeError('El mesclador SDL ja està ocupat per un altre backend')
            try:
                pygame.mixer.init(frequency=RATE, size=-16, channels=2, buffer=512, allowedchanges=0)
                pygame.mixer.set_num_channels(16)
            except Exception:
                pygame.mixer.quit();raise

    def _ready(self):
        if self.closed or self.pg.mixer.get_init() != (RATE, -16, 2):
            raise RuntimeError('El dispositiu d’àudio no està disponible; cal tornar a activar-lo')

    def check(self):
        self._ready()

    def _decode(self, path, key, duration, size):
        import numpy as np
        self._ready()
        if size==0:return AudioClip(key,path,duration,0,str(path),True)
        with self.sf.SoundFile(str(path)) as stream:
            if stream.channels not in (1, 2) or not 8000 <= stream.samplerate <= 96000:
                raise ValueError('Format d’àudio no admès')
            limit = min(stream.samplerate * SHORT_CLIP_S, MAX_CLIP_BYTES // (2 * stream.channels))
            data = stream.read(frames=limit+1, dtype='int16', always_2d=True)
            rate = stream.samplerate
        if not len(data) or len(data) > limit:
            raise ValueError('El clip supera el límit de descodificació')
        frames = max(1,round(len(data)*RATE/rate))
        if frames*4 > MAX_CLIP_BYTES:
            raise ValueError('Massa memòria per al clip')
        if data.shape[1] == 1:data = np.repeat(data, 2, axis=1)
        if rate != RATE:
            indexes = np.arange(frames)*rate/RATE
            original = np.arange(len(data))
            data = np.column_stack([np.interp(indexes, original, data[:, channel]) for channel in range(2)]).astype(np.int16)
        data = np.ascontiguousarray(data)
        sound = self.pg.sndarray.make_sound(data)
        return AudioClip(key, path, sound.get_length(), data.nbytes, sound)

    def _chunk(self, state):
        import numpy as np
        stream=state['file']
        data=stream.read(max(1,round(stream.samplerate*STREAM_CHUNK_S)),dtype='int16',always_2d=True)
        if not len(data) and state['loop']:
            stream.seek(0)
            data=stream.read(max(1,round(stream.samplerate*STREAM_CHUNK_S)),dtype='int16',always_2d=True)
        if not len(data):state['eof']=True;return None
        if stream.channels==1:data=np.repeat(data,2,axis=1)
        if stream.samplerate!=RATE:
            count=max(1,round(len(data)*RATE/stream.samplerate))
            indexes=np.arange(count)*stream.samplerate/RATE
            original=np.arange(len(data))
            data=np.column_stack([np.interp(indexes,original,data[:,c]) for c in range(2)]).astype(np.int16)
        return self.pg.sndarray.make_sound(np.ascontiguousarray(data))

    def start(self, clip, slot, loop, now):
        self._ready()
        state=None
        if clip.streamed:
            state=dict(file=self.sf.SoundFile(str(clip.path)),loop=loop,eof=False)
            try:first=self._chunk(state)
            except Exception:state['file'].close();raise
            if first is None:state['file'].close();raise ValueError('El fitxer de so és buit')
        self.stop(slot)
        channel=self.pg.mixer.Channel(slot);channel.set_volume(0.)
        if state is not None:
            self.streams[slot]=state;channel.play(first)
            second=self._chunk(state)
            if second is not None:channel.queue(second)
        else:channel.play(clip.payload, loops=-1 if loop else 0)
        super().start(clip, slot, loop, now)

    def volume(self, slot, gain):
        self._ready();self.pg.mixer.Channel(slot).set_volume(gain)
        super().volume(slot, gain)

    def stop(self, slot):
        state=self.streams.pop(slot,None)
        if state is not None:state['file'].close()
        if not self.closed and self.pg.mixer.get_init() is not None:self.pg.mixer.Channel(slot).stop()
        super().stop(slot)

    def busy(self, slot, now):
        self._ready();channel=self.pg.mixer.Channel(slot)
        state=self.streams.get(slot)
        if state is not None and not state['eof'] and channel.get_queue() is None:
            chunk=self._chunk(state)
            if chunk is not None:
                if channel.get_busy():channel.queue(chunk)
                else:channel.play(chunk)
        result=channel.get_busy()
        if not result:self.stop(slot)
        return result

    def close(self):
        with self._mixer_lock:
            for slot in list(self.streams):self.stop(slot)
            if not self.closed:self.pg.mixer.quit()
            super().close()


@dataclass
class _Voice:
    owner: tuple
    slot: int
    clip: AudioClip
    gain: float
    loop: bool
    fade: tuple | None = None
    stop_after_fade: bool = False
    sent_gain: float = -1.


@dataclass(frozen=True)
class VoiceState:
    group: str
    source_id: str
    marker_id: int | None
    slot: int
    path: str
    gain: float
    loop: bool
    fading: bool


def ramp(start, target, since, duration, now):
    fraction = min(1., max(0., (now-since)/duration)) if duration else 1.
    return start+(target-start)*fraction


def audio_time(value,previous):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not isfinite(value) or value<previous:
        raise ValueError('El temps d’àudio ha de ser finit i no decreixent')
    return float(value)


class AudioEngine:
    def __init__(self, backend):
        self.backend = backend
        self.voices = {}
        self.groups = {}
        self.master = 1.
        self.now=0.

    def dispatch(self, command, now, cancelled=None, clock=None):
        if not isinstance(command, AudioCommand):raise ValueError('Cal una ordre d’àudio')
        self.tick(now)
        if command.kind == 'play_sound':
            owner = command.group, command.source_id, command.marker_id
            previous = self.voices.get(owner)
            if previous is None and len(self.voices) >= 16:raise ValueError('Els 16 canals locals estan ocupats')
            clip = self.backend.load(command.path)
            if cancelled is not None and cancelled():return False
            if clock is not None:now=audio_time(clock(),self.now)
            slot = previous.slot if previous else next(i for i in range(16) if i not in {v.slot for v in self.voices.values()})
            if previous is not None and previous.clip.key == clip.key and previous.loop == command.loop:
                voice = previous
            else:
                self.backend.start(clip, slot, command.loop, now)
                voice = _Voice(owner, slot, clip, 0. if command.fade_s else command.gain, command.loop)
                self.voices[owner] = voice
            voice.fade = (voice.gain, command.gain, now, command.fade_s)
            voice.stop_after_fade = False
        else:
            if command.kind == 'audio_volume' and command.scope == 'group':
                if command.group not in self.groups and len(self.groups) >= 64:raise ValueError('Massa grups d’àudio')
                current = self.group_gain(command.group, now)
                self.groups[command.group] = (current, command.gain, now, command.fade_s)
            for voice in list(self.voices.values()):
                if voice.owner[0] != command.group or (command.scope == 'marker' and voice.owner[1:] != (command.source_id, command.marker_id)):
                    continue
                if command.kind == 'stop_sound':
                    if not command.fade_s:
                        self.backend.stop(voice.slot);del self.voices[voice.owner]
                    else:
                        voice.fade = (voice.gain, 0., now, command.fade_s);voice.stop_after_fade = True
                elif command.scope == 'marker':
                    voice.fade = (voice.gain, command.gain, now, command.fade_s);voice.stop_after_fade = False
        self.tick(now)

    def group_gain(self, group, now):
        fade = self.groups.get(group)
        return ramp(*fade, now) if fade is not None else 1.

    def tick(self, now):
        now=audio_time(now,self.now)
        self.backend.check()
        self.now=now
        for owner, voice in list(self.voices.items()):
            if not self.backend.busy(voice.slot, now):
                del self.voices[owner];continue
            if voice.fade is not None:
                voice.gain = ramp(*voice.fade, now)
                if now >= voice.fade[2]+voice.fade[3]:
                    voice.fade = None
                    if voice.stop_after_fade:
                        self.backend.stop(voice.slot);del self.voices[owner];continue
            gain = voice.gain*self.group_gain(owner[0], now)*self.master
            if abs(gain-voice.sent_gain) > .0001:
                self.backend.volume(voice.slot, gain);voice.sent_gain = gain

    def snapshot(self):
        return tuple(VoiceState(v.owner[0], v.owner[1], v.owner[2], v.slot, str(v.clip.path),
                                max(0., v.sent_gain), v.loop, v.fade is not None or
                                (v.owner[0] in self.groups and self.now<self.groups[v.owner[0]][2]+self.groups[v.owner[0]][3])) for v in self.voices.values())

    def stop_all(self):
        failure=None
        for voice in list(self.voices.values()):
            try:self.backend.stop(voice.slot)
            except Exception as exc:failure=exc
        self.voices.clear();self.groups.clear()
        if failure is not None:raise failure

    def close(self):
        try:self.stop_all()
        finally:self.backend.close()
