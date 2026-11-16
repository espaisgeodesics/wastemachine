"""Independent overlapping zone-audio layers, using the shared audio worker."""
from dataclasses import replace
from pathlib import Path

from local_audio import AudioCommand
from spatial_zones import SpatialEngine

SOURCE = 'atmo-zone-audio'


class ZoneAudioPlayer:
    def __init__(self, controller):
        self.controller = controller
        self.playing = {}
        self.pending_stops = {}
        self.last_error = ''
        self.config = None
        self.project = None
        self.zones = {}
        self.engines = {}
        self.occupants = {}
        self.pending_starts = set()
        self.deadlines = {}

    def command(self, kind, zone, fade=0):
        path = ''
        if kind == 'play_sound':
            asset = Path(zone.audio_path)
            if not asset.is_absolute():
                if self.project is None:raise ValueError('Desa el projecte per resoldre la ruta relativa del so.')
                asset = Path(self.project).resolve().parent / asset
            path = str(asset.resolve())
        return AudioCommand(kind, 'zone:' + zone.id, SOURCE, None, path,
                            zone.audio_gain, fade, zone.audio_loop and zone.audio_mode != 'once',
                            'marker', zone.priority)

    def submit(self, command):
        try:
            accepted = self.controller.submit(command)
            if not accepted:
                status = self.controller.snapshot()
                self.last_error = 'Àudio de zones: ' + status.detail + '. Activa l’àudio local.'
            return accepted
        except (ValueError, OSError, RuntimeError) as exc:
            self.last_error = 'Àudio de zones: ' + str(exc)
            return False

    def flush_stops(self):
        for id, (zone, fade) in list(self.pending_stops.items()):
            if self.submit(self.command('stop_sound', zone, fade)):
                self.pending_stops.pop(id, None)
                self.playing.pop(id, None)

    def stop(self, immediate=True):
        self.pending_starts.clear()
        self.deadlines.clear()
        for id, zone in self.playing.items():
            self.pending_stops[id] = zone, 0 if immediate else zone.audio_fade_out_s
        self.flush_stops()
        # Reset detector states so an explicit resume can observe current presence.
        if self.config is not None:self._detectors()

    def _detectors(self):
        self.engines = {}
        self.occupants = {}
        for id, zone in self.zones.items():
            # Each sound layer has its own stabilized occupancy, independent of
            # whichever overlapping photograph wins the visual priority.
            sensor = replace(zone, image_path=None, audio_path=None, allow_overlap=False)
            self.engines[id] = SpatialEngine(replace(self.config, zones=(sensor,)))
            self.occupants[id] = set()

    def configure(self, config, project=None):
        if config == self.config and project == self.project:return
        self.stop()
        self.config, self.project = config, project
        self.zones = {zone.id: zone for zone in config.zones if zone.enabled and zone.audio_path}
        self._detectors()

    def update(self, observations, now, normalized=False):
        self.last_error = ''
        self.flush_stops()
        for id, engine in self.engines.items():
            zone = self.zones[id]
            occupied = self.occupants[id]
            before = bool(occupied)
            result = (engine.update_normalized(observations, now) if normalized
                      else engine.update_camera(observations, now))
            for event in result.events:
                if event.kind == 'enter':occupied.add(event.card_id)
                elif event.kind == 'exit':occupied.discard(event.card_id)
            after = bool(occupied)
            if after and not before:
                self.pending_stops.pop(id, None)
                self.deadlines.pop(id, None)
                self.pending_starts.add(id)
            elif before and not after:
                self.pending_starts.discard(id)
                if zone.audio_mode == 'presence':
                    if id in self.playing:self.pending_stops[id] = zone, zone.audio_fade_out_s
                elif zone.audio_mode == 'after_exit':
                    self.deadlines[id] = now + zone.audio_duration_s
            if id in self.deadlines and now >= self.deadlines[id]:
                self.deadlines.pop(id, None)
                if id in self.playing:self.pending_stops[id] = zone, zone.audio_fade_out_s
        self.flush_stops()
        for id in list(self.pending_starts):
            zone = self.zones[id]
            try: command = self.command('play_sound', zone, zone.audio_fade_in_s)
            except (ValueError, OSError) as exc:
                self.last_error = str(exc);continue
            if self.submit(command):
                self.playing[id] = zone
                self.pending_starts.discard(id)
        status = self.controller.snapshot()
        if status.state == 'error':self.last_error = 'Àudio local: ' + status.detail
        elif status.log:
            _, kind, detail = status.log[-1]
            if kind == 'play_sound' and not detail.startswith(('acceptada:', 'cancel·lada')):
                self.last_error = 'Àudio local: ' + detail
