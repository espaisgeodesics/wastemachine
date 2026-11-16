"""Per-card Kaoss configuration and live MIDI, using the existing XY engine."""
from dataclasses import replace
import time
import tkinter as tk
from tkinter import ttk, messagebox

from kaoss_xy import KaossConfig, KaossEngine, PRESETS, SCALES, preset, validate_assignments

CHAOS_FUNCTION = 'Chaos Oscillator (Kaoss XY)'
MIDI_FUNCTIONS = {'Nota MIDI', 'Harmonia espacial', 'Arpegiador espacial', 'Control MIDI CC',
                  'Patró rítmic', 'Ritme de bateria', 'Àudio', 'Control d’àudio / Mute'}


def live_configs(cards, rules):
    configs = {}
    reserved = {action.channel for rule in rules.rules if rule.enabled
                for action in rule.actions if action.kind in ('note', 'cc')}
    for index, card in enumerate(cards):
        function = card.get('function')
        if function == CHAOS_FUNCTION:
            config = KaossConfig.from_dict(card.get('kaoss', KaossConfig(channel=card.get('channel', 2)).to_dict()))
            if config.channel != card['channel']:
                raise ValueError('El canal de Chaos ha de coincidir amb el canal de la targeta.')
            configs[index] = config
        elif function in MIDI_FUNCTIONS:
            reserved.add(card.get('channel', 1))
            if isinstance(card.get('mixer'), dict):
                reserved.add(card['mixer'].get('channel', card.get('channel', 1)))
    validate_assignments(configs, reserved)
    return configs


class LiveKaoss:
    def __init__(self, app):
        self.app = app
        self.engine = KaossEngine()
        self.generation = 0

    def send(self, command):
        # NoteOff retries must remain possible during panic and disconnect.
        if self.app.muted and command.kind != 'note_off': return False
        return self.app.send_rule_midi(command)

    def prepare(self, cards, rules):
        configs = live_configs(cards, rules)
        if configs != self.engine.configs and not self.engine.stop(self.send):
            raise ValueError('No s’han pogut alliberar les notes Chaos. Reconnecta el port MIDI abans de canviar la configuració.')
        return configs

    def configure(self, cards, rules):
        configs = self.prepare(cards, rules)
        if configs != self.engine.configs:
            self.engine = KaossEngine(configs)

    def observe(self, marker, x, y, rotation):
        if self.app.muted: return
        self.engine.observe(marker, x, y, rotation, time.monotonic())

    def tick(self):
        self.engine.tick(time.monotonic(), self.send, self.app.bpm)

    def release(self, marker):
        voice = self.engine.voices.get(marker)
        if voice is not None:
            voice.cancelled = True
            self.tick()

    def stop(self):
        return self.engine.stop(self.send)

    def invalidate_editors(self):
        self.generation += 1


def default_config(app, index):
    used = {card.get('channel', 1) for i, card in enumerate(app.cards)
            if i != index and card.get('function') in MIDI_FUNCTIONS | {CHAOS_FUNCTION}}
    used.update(action.channel for rule in app.rule_config.rules if rule.enabled
                for action in rule.actions if action.kind in ('note', 'cc'))
    channel = next((channel for channel in range(2, 17) if channel not in used),
                   1 if 1 not in used else None)
    if channel is None: raise ValueError('No queda cap canal MIDI lliure per a Chaos.')
    return KaossConfig(channel=channel)


class CardKaossEditor(ttk.Frame):
    def __init__(self, window, app):
        super().__init__(window, padding=12)
        self.pack(fill='both', expand=True)
        self.window, self.app = window, app
        self.index = int(app.card_id.get()) - 1
        self.generation = app.live_kaoss.generation
        self.variables = {}
        card = app.cards[self.index]
        config = (KaossConfig.from_dict(card['kaoss']) if 'kaoss' in card
                  else default_config(app, self.index))
        ttk.Label(self, text=f'Chaos Oscillator · Targeta {self.index+1:02d}',
                  font=('Segoe UI', 14, 'bold')).pack(anchor='w', pady=(0, 8))
        ttk.Label(self, text='X controla notes o CC. Y i rotació controlen velocitat o CC.\n'
                            'Sortida MIDI cap al teu instrument o DAW; cada Chaos utilitza un canal propi.',
                  wraplength=780).pack(anchor='w', pady=(0, 10))
        header = ttk.Frame(self);header.pack(fill='x')
        self.preset_name = tk.StringVar(value=PRESETS[0])
        ttk.Combobox(header, textvariable=self.preset_name, values=PRESETS,
                     state='readonly', width=23).pack(side='left')
        ttk.Button(header, text='Carregar preset', command=self.load_preset).pack(side='left', padx=8)
        fields = [
            ('mode', 'Mode', ('Instrument', 'Efectes')), ('channel', 'Canal MIDI exclusiu', None),
            ('root', 'Tònica (Do=0, La=9)', None), ('scale', 'Escala', tuple(SCALES)),
            ('note_min', 'Nota mínima', None), ('note_max', 'Nota màxima', None),
            ('velocity', 'Velocitat', None), ('y_velocity', 'Y controla velocitat', bool),
            ('x_cc', 'CC de X (mode Efectes)', None), ('y_cc', 'CC de Y', None),
            ('rotation_cc', 'CC de rotació', None), ('rotation_enabled', 'Activar rotació', bool),
            ('invert_x', 'Invertir X', bool), ('invert_y', 'Invertir Y', bool),
            ('invert_rotation', 'Invertir rotació', bool), ('smoothing_s', 'Suavització (0–2 s)', None),
            ('deadzone', 'Zona morta (0–0.2)', None), ('quantize_beats', 'Quantització (temps)', ('0', '0.25', '0.5', '1')),
            ('lost_timeout_s', 'Silenciar absència (0.05–2 s)', None)]
        form = ttk.Frame(self);form.pack(fill='both', expand=True, pady=10)
        for position, (key, title, choices) in enumerate(fields):
            row, column = position//2, (position%2)*2
            variable = tk.BooleanVar() if choices is bool else tk.StringVar()
            self.variables[key] = variable
            if choices is bool:
                ttk.Checkbutton(form, text=title, variable=variable).grid(row=row, column=column, columnspan=2, sticky='w', padx=5, pady=4)
            else:
                ttk.Label(form, text=title).grid(row=row, column=column, sticky='w', padx=5, pady=4)
                control = (ttk.Combobox(form, textvariable=variable, values=choices, state='readonly', width=22)
                           if choices else ttk.Entry(form, textvariable=variable, width=24))
                control.grid(row=row, column=column+1, sticky='ew', padx=5, pady=4)
        ttk.Button(self, text='Aplicar a la targeta', command=self.apply, style='Accent.TButton').pack(fill='x', pady=6)
        self.status = tk.StringVar(value='Els presets omplen el formulari. Aplica els canvis i desa el projecte.')
        ttk.Label(self, textvariable=self.status, wraplength=800).pack(fill='x')
        self.show(config)

    def show(self, config):
        for key, value in config.to_dict().items(): self.variables[key].set(value)

    def read(self):
        template = KaossConfig().to_dict()
        data = {}
        for key, variable in self.variables.items():
            value = variable.get()
            if isinstance(template[key], bool) or isinstance(template[key], str): data[key] = value
            elif isinstance(template[key], int): data[key] = int(value)
            else: data[key] = float(str(value).replace(',', '.'))
        return KaossConfig.from_dict(data)

    def load_preset(self):
        try: self.show(preset(self.preset_name.get(), int(self.variables['channel'].get())))
        except (ValueError, tk.TclError) as exc: self.error(exc)

    def apply(self):
        if self.generation != self.app.live_kaoss.generation:
            self.error('El projecte ha canviat. Tanca aquest formulari i torna a obrir la configuració.');return False
        if int(self.app.card_id.get())-1 != self.index:
            self.error(f'Selecciona de nou la targeta {self.index+1:02d} abans d’aplicar.');return False
        previous = self.app.kaoss_draft
        previous_channel = self.app.channel.get()
        try:
            config = self.read()
            self.app.kaoss_draft = config
            self.app.channel.set(config.channel)
            self.app.fun.set(CHAOS_FUNCTION)
            if not self.app.apply_card():
                self.app.kaoss_draft = previous
                self.app.channel.set(previous_channel)
                return False
            self.status.set('Chaos aplicat a la targeta. Desa el projecte per conservar-lo.')
            return True
        except (ValueError, tk.TclError) as exc:
            self.app.kaoss_draft = previous
            self.app.channel.set(previous_channel)
            self.error(exc);return False

    def error(self, error):
        messagebox.showerror('ATMO ESFERA FX · Chaos Oscillator', str(error), parent=self.window)
