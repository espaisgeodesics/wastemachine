"""Explicit visual ownership and bounded, owned MIDI note lifetimes for rules."""
from collections import deque
from dataclasses import dataclass
from threading import RLock
from pathlib import Path

import numpy as np
from spatial_projection import ImageStore
from local_audio import command_from_request


@dataclass(frozen=True)
class MidiCommand:
    kind: str
    channel: int  # user channel, 1..16
    number: int
    value: int


@dataclass(frozen=True)
class VisualClaim:
    request: object
    image: object = None
    deadline: float | None = None


class RuleOutputs:
    def __init__(self):
        self.claims = {}
        self.notes = {}
        self.store = ImageStore()
        self.log = deque(maxlen=200)
        self.lock = RLock()
        self.serial = 0
        self.midi_channels = set()

    def log_snapshot(self):
        with self.lock:return tuple(self.log)

    def apply(self, requests, now, send=None, project_file=None, midi_enabled=True, audio=None):
        # Apply the whole batch before rendering: no intermediate black frame.
        cc_winners = {}
        audio_winners={}
        play_winners={}
        for request in requests:
            if request.action.kind == 'cc':
                key = request.action.channel, request.action.number
                if key not in cc_winners or self.rank(request) < self.rank(cc_winners[key]):cc_winners[key] = request
            if request.action.kind in ('stop_sound','audio_volume'):
                key=(request.action.kind,request.action.audio_group or request.rule.group,request.action.audio_scope,
                     (request.event.source_id,request.event.marker_id) if request.action.audio_scope=='marker' else None)
                if key not in audio_winners or self.rank(request)<self.rank(audio_winners[key]):audio_winners[key]=request
            if request.action.kind=='play_sound':
                key=(request.action.audio_group or request.rule.group,request.event.source_id,request.event.marker_id)
                if key not in play_winners or self.rank(request)<self.rank(play_winners[key]):play_winners[key]=request
        for request in requests:
            if request.action.kind == 'cc' and cc_winners[request.action.channel, request.action.number] is not request:
                self.log.append((now, request.rule.name, 'cc', 'descartada per prioritat'));continue
            try:
                if request.action.kind in ('stop_sound','audio_volume'):
                    key=(request.action.kind,request.action.audio_group or request.rule.group,request.action.audio_scope,
                         (request.event.source_id,request.event.marker_id) if request.action.audio_scope=='marker' else None)
                    if audio_winners[key] is not request:
                        self.log.append((now,request.rule.name,request.action.kind,'descartada per prioritat'));continue
                if request.action.kind == 'play_sound':
                    group=request.action.audio_group or request.rule.group
                    if play_winners[group,request.event.source_id,request.event.marker_id] is not request:
                        self.log.append((now,request.rule.name,'play_sound','descartada per prioritat'));continue
                    stops=[r for r in requests if r.action.kind=='stop_sound' and (r.action.audio_group or r.rule.group)==group
                           and (r.action.audio_scope=='group' or (r.event.source_id,r.event.marker_id)==(request.event.source_id,request.event.marker_id))]
                    if any(self.rank(stop)<self.rank(request) for stop in stops):
                        self.log.append((now,request.rule.name,'play_sound','suprimida per aturada prioritària'));continue
                queued=self._apply(request, now, send, project_file, midi_enabled,audio)
                self.log.append((now, request.rule.name, request.action.kind, 'en cua d’àudio' if queued else 'acceptada'))
            except Exception as exc:
                self.log.append((now, request.rule.name, request.action.kind, str(exc)))

    def _apply(self, request, now, send, project_file, midi_enabled,audio):
        action, rule, event = request.action, request.rule, request.event
        if action.kind in ('play_sound','stop_sound','audio_volume'):
            if not midi_enabled:raise ValueError('Sortides de so bloquejades pel silenci absolut')
            if audio is None or audio(command_from_request(request,project_file)) is False:raise ValueError('Àudio local no activat; no es reproduirà més tard')
            return True
        if action.kind == 'release_visual':
            for owner in list(self.claims):
                if owner[0] == rule.group and (event.marker_id is None or owner[1:3] == (event.source_id, event.marker_id)):
                    del self.claims[owner]
            return
        if action.kind in ('image', 'color'):
            owner = (rule.group, event.source_id, event.marker_id, rule.rule_id, request.action_index)
            if owner not in self.claims and len(self.claims) >= 256:
                raise ValueError('Massa propietaris visuals actius')
            image = None
            if action.kind == 'image':
                path = Path(action.value)
                if not path.is_absolute():
                    if project_file is None:raise ValueError('No es pot resoldre la imatge sense projecte')
                    path = Path(project_file).resolve().parent / path
                path = path.resolve()
                active = {claim.image.path:claim.image for key,claim in self.claims.items() if key != owner and claim.image is not None}
                if path not in active and len(active) >= 4:
                    raise ValueError('Màxim quatre imatges diferents amb propietari actiu; allibera un grup visual')
                image = active.get(path) or self.store.load(action.value, project_file)
            self.claims[owner] = VisualClaim(request, image, now+action.duration_s if action.duration_s else None)
            return
        if not midi_enabled or send is None:
            raise ValueError('MIDI bloquejat o sense connexió; no es reenviarà en reconnectar')
        with self.lock:
            if action.kind == 'cc':
                if send(MidiCommand('cc', action.channel, action.number, int(action.value))) is False:
                    raise ValueError('No hi ha sortida MIDI')
                self.midi_channels.add(action.channel)
                if action.number in (120, 123):
                    self.notes = {owner: note for owner, note in self.notes.items() if note[0][0] != action.channel}
                return
            if len(self.notes) >= 256:
                raise ValueError('Massa notes de regles actives')
            key = action.channel, action.number
            if not any(note[0] == key for note in self.notes.values()):
                if send(MidiCommand('note_on', *key, action.velocity)) is False:
                    raise ValueError('No hi ha sortida MIDI')
            self.serial += 1
            self.notes[self.serial] = (key, now+action.duration_s)
            self.midi_channels.add(action.channel)

    def tick(self, now, send=None, visuals=True):
        with self.lock:
            for owner, (key, deadline) in list(self.notes.items()):
                if now < deadline:
                    continue
                others = any(o != owner and note[0] == key for o, note in self.notes.items())
                try:
                    if not others and (send is None or send(MidiCommand('note_off', *key, 0)) is False):
                        raise ValueError('No s’ha pogut finalitzar la nota de regla')
                    del self.notes[owner]
                except Exception as exc:
                    self.log.append((now, 'MIDI', 'note_off', str(exc)))
                    self.notes[owner] = key, now+.1
        if visuals:
            for owner, claim in list(self.claims.items()):
                if claim.deadline is not None and now >= claim.deadline:
                    self.claims.pop(owner, None)

    def stop_midi(self, send=None):
        with self.lock:
            for key in sorted({note[0] for note in self.notes.values()}):
                try:
                    if send is not None:
                        if send(MidiCommand('note_off', *key, 0)) is False:raise ValueError('Sortida MIDI no disponible')
                except Exception as exc:
                    self.log.append((0, 'Aturada', 'note_off', str(exc)))
            for channel in sorted(self.midi_channels):
                try:
                    if send is not None:
                        send(MidiCommand('cc', channel, 64, 0))
                except Exception as exc:
                    self.log.append((0, 'Aturada', 'sustain', str(exc)))
            self.notes.clear()
            self.midi_channels.clear()

    def clear_visuals(self):
        self.claims.clear()

    def winner(self):
        if not self.claims:
            return None
        return min(self.claims.values(), key=lambda claim:self.rank(claim.request))

    @staticmethod
    def rank(r):
        return (-r.rule.priority, -r.event.occurred_at, r.rule.rule_id, r.event.source_id,
                r.event.marker_id if r.event.marker_id is not None else -1, -r.action_index)

    def frame(self, size):
        winner = self.winner()
        if winner is None:
            return None
        if winner.image is not None:
            return self.store.fit(winner.image, size)
        color = winner.request.action.value
        rgb = tuple(int(color[i:i+2], 16) for i in (1, 3, 5))
        return np.full((size[1], size[0], 3), rgb[::-1], dtype=np.uint8)
