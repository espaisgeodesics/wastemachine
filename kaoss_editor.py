"""Kaoss test controls. The supplied session owns all output; no MIDI ports here."""
import json
import os
from pathlib import Path
import tempfile
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from kaoss_xy import KaossConfig, PRESETS, SCALES, pack_configs, preset, unpack_configs


class KaossEditor(ttk.Frame):
    def __init__(self, parent, session):
        super().__init__(parent, padding=8)
        self.session = session
        self.pack(fill='both', expand=True)
        self.marker = tk.StringVar(value=self.marker_ids()[0] if self.marker_ids() else '0')
        self.preset_name = tk.StringVar(value=PRESETS[0])
        self.status = tk.StringVar(value='Prova independent: cap canvi al projecte ni a les sortides reals.')
        header = ttk.Frame(self);header.pack(fill='x')
        ttk.Label(header, text='ID de marcador').pack(side='left')
        self.markers = ttk.Combobox(header, textvariable=self.marker, values=self.marker_ids(), width=5, state='readonly')
        self.markers.pack(side='left', padx=5);self.markers.bind('<<ComboboxSelected>>', lambda e:self.load_marker())
        ttk.Combobox(header, textvariable=self.preset_name, values=PRESETS, state='readonly', width=20).pack(side='left', padx=5)
        ttk.Button(header, text='CARREGAR PRESET', command=self.load_preset).pack(side='left')
        ttk.Label(self, text='X: esquerra → dreta. Y invertida: baix → dalt. Rotació: voltes de 0 a 1.\nCada marcador reserva un canal propi, separat de les regles. Els presets només omplen el formulari.').pack(anchor='w', pady=8)
        form = ttk.Frame(self);form.pack(fill='x')
        self.variables = {}
        rows = [
            ('mode', 'Mode', ('Instrument', 'Efectes')), ('channel', 'Canal MIDI', None),
            ('root', 'Tònica (Do=0, La=9)', None), ('scale', 'Escala', tuple(SCALES)),
            ('note_min', 'Nota mínima', None), ('note_max', 'Nota màxima', None),
            ('velocity', 'Velocitat fixa', None), ('y_velocity', 'Y controla velocitat', bool),
            ('x_cc', 'CC de X (efectes)', None), ('y_cc', 'CC de Y', None),
            ('rotation_cc', 'CC de rotació', None), ('rotation_enabled', 'Activar rotació', bool),
            ('invert_x', 'Invertir X', bool), ('invert_y', 'Invertir Y', bool),
            ('invert_rotation', 'Invertir rotació', bool), ('smoothing_s', 'Suavització (0–2 s)', None),
            ('deadzone', 'Zona morta (0–0.2)', None), ('quantize_beats', 'Quantització (temps)', ('0', '0.25', '0.5', '1')),
            ('lost_timeout_s', 'Silenciar absència (0.05–2 s)', None)]
        for i, (key, title, choices) in enumerate(rows):
            row, column = i//2, (i%2)*2
            var = tk.BooleanVar() if choices is bool else tk.StringVar()
            self.variables[key] = var
            if choices is bool:
                ttk.Checkbutton(form, text=title, variable=var).grid(row=row, column=column, columnspan=2, sticky='w', padx=5, pady=3)
            else:
                ttk.Label(form, text=title).grid(row=row, column=column, sticky='w', padx=5, pady=3)
                widget = ttk.Combobox(form, textvariable=var, values=choices, state='readonly', width=22) if choices else ttk.Entry(form, textvariable=var, width=24)
                widget.grid(row=row, column=column+1, sticky='w', padx=5, pady=3)
        controls = ttk.Frame(self);controls.pack(fill='x', pady=10)
        for title, action in [('APLICAR A LA PROVA', self.apply), ('DESACTIVAR MARCADOR', self.remove),
                              ('SILENCIAR PROVA', self.silence), ('DESAR KAOSS…', self.save), ('OBRIR KAOSS…', self.open)]:
            ttk.Button(controls, text=title, command=action).pack(side='left', padx=3)
        ttk.Label(self, textvariable=self.status, wraplength=850).pack(anchor='w')
        ttk.Label(self, text='Els fitxers .kaoss.json desen només la configuració de prova. No s’activa MIDI físic.\nCC 64, 66, 69 i 120–127 no s’admeten per evitar pedals i ordres de canal.').pack(anchor='w', pady=8)
        self.load_marker()

    def marker_ids(self):return tuple(str(p.marker_id) for p in self.session.registry.snapshot().values())

    def show(self, config):
        for key, value in config.to_dict().items():self.variables[key].set(value)

    def refresh_markers(self):
        markers = self.marker_ids()
        self.markers.configure(values=markers)
        if markers and self.marker.get() not in markers:
            self.marker.set(markers[0]);self.load_marker()

    def load_marker(self):
        self.markers.configure(values=self.marker_ids())
        marker = int(self.marker.get())
        self.show(self.session.kaoss.configs.get(marker, preset(PRESETS[0], min(16, marker+2))))
        self.status.set(f'ID {marker}: '+('actiu a la prova' if marker in self.session.kaoss.configs else 'desactivat; aplica el formulari per activar-lo'))

    def load_preset(self):
        try:self.show(preset(self.preset_name.get(), int(self.variables['channel'].get())))
        except ValueError as exc:self.error(exc)

    def read(self):
        template = KaossConfig().to_dict()
        data = {}
        for key, var in self.variables.items():
            value = var.get()
            data[key] = value if type(template[key]) is bool or isinstance(template[key], str) else (int(value) if type(template[key]) is int else float(value))
        return KaossConfig.from_dict(data)

    def apply(self):
        try:
            configs = dict(self.session.kaoss.configs);configs[int(self.marker.get())] = self.read()
            self.session.configure_kaoss(configs)
            self.status.set('Kaoss aplicat només al simulador. Mou i gira el marcador al mapa; consulta «Sortida de prova».')
            return True
        except (ValueError, tk.TclError) as exc:self.error(exc);return False

    def remove(self):
        configs = dict(self.session.kaoss.configs);configs.pop(int(self.marker.get()), None)
        self.session.configure_kaoss(configs);self.load_marker()

    def silence(self):
        self.session.kaoss.stop(self.session.send_rule_midi)
        # Visibility remains unchanged; next simulated observation may activate notes.
        self.session.configure_kaoss({})
        self.status.set('Kaoss desactivat per a tots els marcadors; notes de prova alliberades.')

    def save(self):
        path = filedialog.asksaveasfilename(parent=self, defaultextension='.kaoss.json', filetypes=[('Kaoss XY', '*.kaoss.json')])
        if not path:return
        temporary = None
        try:
            data = pack_configs(self.session.kaoss.configs)
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=Path(path).resolve().parent, delete=False) as stream:
                temporary = stream.name;json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False);stream.write('\n')
            os.replace(temporary, path);temporary = None
            self.status.set('Configuració aplicada desada: '+str(path))
        except (OSError, ValueError) as exc:self.error(exc)
        finally:
            if temporary is not None:Path(temporary).unlink(missing_ok=True)

    def open(self):
        path = filedialog.askopenfilename(parent=self, filetypes=[('Kaoss XY', '*.kaoss.json')])
        if not path:return
        try:
            if Path(path).stat().st_size > 65536:raise ValueError('Fitxer Kaoss massa gran (màxim 64 KiB)')
            configs = unpack_configs(json.loads(Path(path).read_text(encoding='utf-8')))
            self.session.configure_kaoss(configs);self.load_marker()
            self.status.set('Configuració carregada només al simulador.')
        except (OSError, ValueError) as exc:self.error(exc)

    def error(self, exc):messagebox.showerror('Kaoss XY de prova', str(exc), parent=self)
