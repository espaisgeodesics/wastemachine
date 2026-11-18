"""Tk editor for phase 2. It configures maps; it does not drive projection."""
from dataclasses import replace
from pathlib import Path
from uuid import uuid4
from functools import lru_cache
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk, ImageOps

from spatial_zones import SpatialMap, Zone, check_image_asset, image_reference


def rebase_map_images(config, old_project, new_project):
    zones = []
    for zone in config.zones:
        references = {}
        for field in ('image_path', 'audio_path'):
            reference = getattr(zone, field)
            if reference:
                path = Path(reference)
                if not path.is_absolute():
                    if old_project is None:
                        raise ValueError('No es pot resoldre un recurs relatiu sense projecte d’origen.')
                    path = Path(old_project).resolve().parent / path
                reference = image_reference(path, new_project)
            references[field] = reference
        zones.append(replace(zone, **references))
    return replace(config, zones=tuple(zones))


@lru_cache(maxsize=4096)
def _cell_polygon(row, column, grid):
    # Clip an approximation of the circle to the cell rectangle.
    from math import cos, sin, tau
    points = [(.5 + .5*cos(i*tau/96), .5 + .5*sin(i*tau/96)) for i in range(96)] if grid.shape=='circle' else [(0,0),(1,0),(1,1),(0,1)]
    for axis, boundary, greater in ((0, column/grid.columns, True),
                                    (0, (column+1)/grid.columns, False),
                                    (1, row/grid.rows, True),
                                    (1, (row+1)/grid.rows, False)):
        output = []
        for a, b in zip(points, points[1:] + points[:1]):
            inside_a = a[axis] >= boundary if greater else a[axis] <= boundary
            inside_b = b[axis] >= boundary if greater else b[axis] <= boundary
            if inside_a != inside_b:
                ratio = (boundary-a[axis])/(b[axis]-a[axis])
                output.append(tuple(a[j] + ratio*(b[j]-a[j]) for j in (0, 1)))
            if inside_b:
                output.append(b)
        points = output
        if not points:
            break
    return tuple(points)


AUDIO_MODES = {'Mentre hi hagi una targeta': 'presence', 'Reproduir un cop': 'once', 'Segons després de sortir': 'after_exit'}

DISPLAY_MODES = {'Mantenir la imatge': 'persistent', 'Mentre la targeta sigui a la zona': 'presence', 'Segons després de retirar-la': 'after_exit'}


class ZoneEditor:
    def __init__(self, window, config, get_cards, get_project, on_change, default_card=None):
        self.window = window
        self.config = config
        self.get_cards = get_cards
        self.get_project = get_project
        self.on_change = on_change
        self.default_card = default_card
        self.current_id = None
        self.cells = set()
        self.dirty = False
        self.loading = True
        self.thumbnail = None
        self.geometry = (0, 0, 1)
        self.visited = set()
        self.name = tk.StringVar()
        self.image_path = tk.StringVar()
        self.enabled = tk.BooleanVar(value=True)
        self.display_mode = tk.StringVar(value='Mentre la targeta sigui a la zona')
        self.duration_s = tk.StringVar(value='3')
        self.audio_path = tk.StringVar()
        self.audio_gain = tk.StringVar(value='0.8')
        self.audio_fade_in_s = tk.StringVar(value='0.5')
        self.audio_fade_out_s = tk.StringVar(value='1')
        self.audio_loop = tk.BooleanVar(value=True)
        self.audio_mode = tk.StringVar(value='Mentre hi hagi una targeta')
        self.audio_duration_s = tk.StringVar(value='3')
        self.allow_overlap = tk.BooleanVar(value=False)
        self.priority = tk.StringVar(value='10')
        self.cards = [tk.BooleanVar(value=False) for _ in range(16)]
        self.notice = tk.StringVar()
        self.selection_info = tk.StringVar()
        self.calibration_info = tk.StringVar()
        self.runtime_info = tk.StringVar(value='Última zona activada: cap')
        self._build()
        for var in (self.name, self.image_path, self.enabled, self.display_mode, self.duration_s, self.audio_path, self.audio_gain, self.audio_fade_in_s,
                    self.audio_fade_out_s, self.audio_loop, self.audio_mode, self.audio_duration_s,
                    self.allow_overlap, self.priority, *self.cards):
            var.trace_add('write', self._changed)
        self.set_map(config)

    def _build(self):
        ttk.Label(self.window, textvariable=self.calibration_info, wraplength=1000).pack(fill='x', padx=10, pady=7)
        runtime=ttk.Frame(self.window);runtime.pack(fill='x',padx=10)
        ttk.Label(runtime,textvariable=self.runtime_info,wraplength=800).pack(side='left',fill='x',expand=True)
        ttk.Button(runtime,text='CALIBRAR TERRA',command=lambda:self.on_calibrate() if hasattr(self,'on_calibrate') else None).pack(side='right',padx=4)
        ttk.Button(runtime,text='TORNAR ALS VISUALS',command=lambda:self.on_release() if hasattr(self,'on_release') else None).pack(side='right')
        body = ttk.Frame(self.window)
        body.pack(fill='both', expand=True, padx=10, pady=3)
        left = ttk.Frame(body, width=170)
        left.pack(side='left', fill='y', padx=(0, 8))
        ttk.Label(left, text='ZONES').pack(anchor='w', pady=4)
        self.list = ttk.Treeview(left, columns=('name',), show='headings', height=12, selectmode='browse')
        self.list.heading('name', text='Nom');self.list.column('name', width=160)
        self.list.pack(fill='both', expand=True)
        self.list.bind('<<TreeviewSelect>>', self.select_zone)
        ttk.Button(left, text='NOVA ZONA', command=self.new_zone).pack(fill='x', pady=5)
        ttk.Button(left, text='ELIMINAR ZONA', command=self.delete_zone).pack(fill='x', pady=2)
        right = ttk.Frame(body, width=310)
        right.pack(side='right', fill='y', padx=(8, 0))
        ttk.Label(right, text='Nom de la zona').pack(anchor='w')
        ttk.Entry(right, textvariable=self.name, width=34).pack(fill='x', pady=4)
        ttk.Checkbutton(right, text='Zona habilitada', variable=self.enabled).pack(anchor='w', pady=4)
        ttk.Label(right, text='Targetes autoritzades (01–16 / IDs 0–15)').pack(anchor='w', pady=(7, 3))
        targets = ttk.Frame(right);targets.pack(fill='x')
        for i, var in enumerate(self.cards):
            ttk.Checkbutton(targets, text=f'{i+1:02d}', variable=var).grid(row=i//4, column=i%4, sticky='w', padx=3, pady=2)
        ttk.Label(right, text='Imatge JPG / PNG').pack(anchor='w', pady=(10, 3))
        ttk.Entry(right, textvariable=self.image_path, state='readonly', width=34).pack(fill='x')
        image_buttons = ttk.Frame(right);image_buttons.pack(fill='x', pady=4)
        ttk.Button(image_buttons, text='TRIAR IMATGE…', command=self.choose_image).pack(side='left')
        ttk.Button(image_buttons, text='SENSE IMATGE', command=self.remove_image).pack(side='left', padx=3)
        ttk.Label(right,text='Durada de la imatge').pack(anchor='w',pady=(5,2))
        mode=ttk.Combobox(right,textvariable=self.display_mode,values=tuple(DISPLAY_MODES),state='readonly',width=32)
        mode.pack(fill='x');mode.bind('<<ComboboxSelected>>',lambda event:self.update_duration_state())
        seconds=ttk.Frame(right);seconds.pack(fill='x',pady=3)
        ttk.Label(seconds,text='Segons després de retirar-la:').pack(side='left')
        self.duration_entry=ttk.Spinbox(seconds,textvariable=self.duration_s,from_=.1,to=86400,increment=.5,width=7)
        self.duration_entry.pack(side='right');self.update_duration_state()
        self.build_audio_controls(right)
        self.image_preview = tk.Label(right, bg='#171411', fg='#e6d0b5', width=32, height=8, wraplength=265)
        self.image_preview.pack(fill='both', expand=True, pady=5)
        ttk.Button(right, text='DESAR ZONA AL MAPA', command=self.save_zone).pack(side='bottom',before=self.image_preview,fill='x', pady=6)
        center = ttk.Frame(body);center.pack(fill='both', expand=True)
        self.canvas = tk.Canvas(center, bg='#171411', highlightthickness=0, width=440, height=440)
        self.canvas.pack(fill='both', expand=True)
        self.canvas.bind('<Configure>', lambda event: self.draw())
        self.canvas.bind('<ButtonPress-1>', self.press)
        self.canvas.bind('<B1-Motion>', self.drag)
        ttk.Label(center, textvariable=self.selection_info).pack(fill='x', pady=5)
        ttk.Label(self.window, textvariable=self.notice, wraplength=1000).pack(side='bottom',before=body,fill='x', padx=10, pady=(4, 8))

    def _changed(self, *args):
        if not self.loading:
            self.dirty = True
            self.notice.set('Canvis sense aplicar: prem DESAR ZONA AL MAPA; després desa el projecte.')
            self.draw()

    def confirm_discard(self):
        return not self.dirty or messagebox.askyesno('Edició de zona', 'Hi ha canvis de zona sense aplicar. Vols descartar-los?', parent=self.window)

    def set_map(self, config):
        selected = self.current_id
        self.config = config
        self.loading = True
        for item in self.list.get_children():self.list.delete(item)
        for zone in config.zones:
            self.list.insert('', 'end', iid=zone.id, values=(zone.name + (' · ♪' if zone.audio_path else '') + (' · ▣' if zone.image_path else '') + ('' if zone.enabled else ' · desactivada'),))
        calibration = 'Calibració matemàtica vàlida · pendent de prova física' if config.calibration else 'SENSE CALIBRACIÓ: el mapa no està alineat amb el terra real'
        self.calibration_info.set(calibration + ' · Sense calibració no s’activen zones en directe.')
        self.loading = False
        if selected and any(zone.id == selected for zone in config.zones):
            self._load_zone(selected)
        else:
            self._new_draft()

    def _new_draft(self):
        self.loading = True
        self.current_id = None;self.cells = set()
        self.name.set('');self.image_path.set('');self.enabled.set(True)
        self.audio_path.set('');self.audio_gain.set('0.8');self.audio_fade_in_s.set('0.5');self.audio_fade_out_s.set('1')
        self.audio_loop.set(True);self.audio_mode.set('Mentre hi hagi una targeta');self.audio_duration_s.set('3')
        self.allow_overlap.set(False);self.priority.set('10');self.update_audio_duration_state()
        self.display_mode.set('Mentre la targeta sigui a la zona');self.duration_s.set('3');self.update_duration_state()
        for i, var in enumerate(self.cards):var.set(i == self.default_card)
        for item in self.list.selection():self.list.selection_remove(item)
        self.loading = False;self.dirty = False
        self.notice.set('Selecciona caselles dins del terra calibrat i configura una zona nova.')
        self.update_thumbnail();self.draw()

    def set_default_card(self, card):
        self.default_card=card
        if self.current_id is None and not self.dirty:
            self.loading=True
            for i,var in enumerate(self.cards):var.set(i==card)
            self.loading=False

    def new_zone(self):
        if self.confirm_discard():self._new_draft()

    def _load_zone(self, id):
        zone = next(zone for zone in self.config.zones if zone.id == id)
        self.loading = True
        self.current_id = id;self.cells = set(zone.cells)
        self.name.set(zone.name);self.image_path.set(zone.image_path or '');self.enabled.set(zone.enabled)
        for key in ('audio_gain','audio_fade_in_s','audio_fade_out_s','audio_duration_s','audio_loop','allow_overlap','priority'):
            getattr(self,key).set(getattr(zone,key))
        self.audio_path.set(zone.audio_path or '')
        self.audio_mode.set(next(label for label,value in AUDIO_MODES.items() if value==zone.audio_mode))
        self.update_audio_duration_state()
        self.display_mode.set(next(label for label,value in DISPLAY_MODES.items() if value==zone.display_mode))
        self.duration_s.set(str(zone.duration_s));self.update_duration_state()
        for i, var in enumerate(self.cards):var.set(i in zone.authorized_cards)
        self.list.selection_set(id);self.list.see(id)
        self.loading = False;self.dirty = False
        self.notice.set('Zona carregada. Els canvis s’apliquen amb DESAR ZONA AL MAPA.')
        self.update_thumbnail();self.draw()

    def select_zone(self, event=None):
        if self.loading or not self.list.selection():return
        selected = self.list.selection()[0]
        if selected == self.current_id:return
        if not self.confirm_discard():
            self.loading = True
            self.list.selection_remove(selected)
            if self.current_id:self.list.selection_set(self.current_id)
            self.loading = False
            return
        self._load_zone(selected)

    def draw(self):
        width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
        ratio=getattr(self.config.calibration,'aspect_ratio',1.)
        map_height=max(1,min(height-28,(width-28)/ratio));size=map_height*ratio
        self.map_height=map_height
        ox, oy = (width-size)/2, (height-map_height)/2
        self.geometry = (ox, oy, size)
        self.canvas.delete('all')
        colors = ('#506c55', '#715876', '#416776', '#86633b', '#6c7041', '#754d49')
        owners = {}
        for index, zone in enumerate(self.config.zones):
            if zone.id == self.current_id:continue
            for cell in zone.cells:
                if zone.enabled or cell not in owners:owners[cell] = colors[index % len(colors)] if zone.enabled else '#34302e'
        for row in range(self.config.grid.rows):
            for column in range(self.config.grid.columns):
                cell = row, column
                if not self.config.grid.eligible(cell):continue
                polygon = _cell_polygon(row, column, self.config.grid)
                points = [value for x, y in polygon for value in (ox+x*size, oy+y*map_height)]
                if len(points) < 6:continue
                selected = cell in self.cells
                self.canvas.create_polygon(points, fill='#ba8548' if selected else owners.get(cell, '#2d241e'),
                                           outline='#ffe1a4' if selected else '#76604d', width=2 if selected else 1)
        getattr(self.canvas,'create_oval' if self.config.grid.shape=='circle' else 'create_rectangle')(ox, oy, ox+size, oy+map_height, outline='#e1b887', width=2)
        self.selection_info.set(f'{len(self.cells)} caselles seleccionades · Clic / arrossega per afegir o treure')

    def cell_at_event(self, event):
        ox, oy, size = self.geometry
        return self.config.grid.cell_at(((event.x-ox)/size, (event.y-oy)/getattr(self,'map_height',size)))

    def press(self, event):
        self.visited = set();self.drag(event)

    def drag(self, event):
        cell = self.cell_at_event(event)
        if cell is None or cell in self.visited:return
        self.visited.add(cell)
        if self.enabled.get() and any(zone.enabled and zone.id != self.current_id and cell in zone.cells and not (self.allow_overlap.get() or zone.allow_overlap) for zone in self.config.zones):
            self.notice.set('Aquesta casella ja té una zona. Activa «Permetre solapament» per afegir-hi una capa.');return
        if cell in self.cells:self.cells.remove(cell)
        else:self.cells.add(cell)
        self._changed()

    def build_audio_controls(self, parent):
        section = ttk.LabelFrame(parent, text='So de la zona', padding=7)
        section.pack(fill='x', pady=8)
        ttk.Entry(section, textvariable=self.audio_path, state='readonly', width=28).pack(fill='x')
        ttk.Button(section, text='Triar so WAV / OGG…', command=self.choose_audio).pack(fill='x', pady=3)
        ttk.Button(section, text='Sense so', command=lambda:self.audio_path.set('')).pack(fill='x')
        ttk.Label(section, text='Clips de fins a 30 s · Bucle disponible', wraplength=230).pack(anchor='w', pady=4)
        for title, variable, maximum in [('Volum (0–1)', self.audio_gain, 1),
                ('Fade in (s)', self.audio_fade_in_s, 10), ('Fade out en sortir (s)', self.audio_fade_out_s, 10)]:
            row = ttk.Frame(section);row.pack(fill='x', pady=2)
            ttk.Label(row, text=title).pack(side='left')
            ttk.Spinbox(row, textvariable=variable, from_=0, to=maximum, increment=.1, width=6).pack(side='right')
        ttk.Checkbutton(section, text='Repetir en bucle', variable=self.audio_loop).pack(anchor='w')
        mode = ttk.Combobox(section, textvariable=self.audio_mode, values=tuple(AUDIO_MODES), state='readonly', width=28)
        mode.pack(fill='x', pady=4)
        mode.bind('<<ComboboxSelected>>', lambda event:self.update_audio_duration_state())
        row = ttk.Frame(section);row.pack(fill='x')
        ttk.Label(row, text='Segons després de sortir').pack(side='left')
        self.audio_seconds_entry = ttk.Spinbox(row, textvariable=self.audio_duration_s, from_=.1, to=86400, width=6)
        self.audio_seconds_entry.pack(side='right');self.update_audio_duration_state()
        ttk.Button(section, text='Activar àudio local', command=self.enable_audio).pack(fill='x', pady=5)
        ttk.Checkbutton(parent, text='Permetre solapament de zones', variable=self.allow_overlap).pack(anchor='w', pady=4)
        row = ttk.Frame(parent);row.pack(fill='x', pady=3)
        ttk.Label(row, text='Prioritat d’imatge').pack(side='left')
        ttk.Spinbox(row, textvariable=self.priority, from_=1, to=1000, width=5).pack(side='right')

    def update_audio_duration_state(self):
        if hasattr(self,'audio_seconds_entry'):
            self.audio_seconds_entry.configure(state='normal' if AUDIO_MODES.get(self.audio_mode.get())=='after_exit' else 'disabled')

    def enable_audio(self):
        callback = getattr(self, 'on_enable_audio', None)
        if callback is not None:
            callback();self.notice.set('Activant l’àudio local. Consulta l’estat a la finestra principal o a Àudio local.')
        else:self.notice.set('Activa el dispositiu des de les eines d’àudio local.')

    def choose_audio(self):
        path = filedialog.askopenfilename(parent=self.window, filetypes=[('So WAV PCM / OGG', '*.wav *.ogg')])
        if not path:return
        project = self.get_project()
        self.audio_path.set(image_reference(path, project) if project else str(Path(path).resolve()))
        self.allow_overlap.set(True)

    def audio_values(self):
        values = {key:float(getattr(self,key).get().replace(',', '.')) for key in
                  ('audio_gain','audio_fade_in_s','audio_fade_out_s','audio_duration_s')}
        return dict(values, audio_path=self.audio_path.get() or None, audio_loop=self.audio_loop.get(),
                    audio_mode=AUDIO_MODES[self.audio_mode.get()], allow_overlap=self.allow_overlap.get(),
                    priority=int(self.priority.get()))

    def choose_image(self):
        path = filedialog.askopenfilename(parent=self.window, filetypes=[('Imatges JPG / PNG', '*.jpg *.jpeg *.png')])
        if not path:return
        project = self.get_project()
        self.image_path.set(image_reference(path, project) if project else str(Path(path).resolve()))
        self.update_thumbnail()

    def remove_image(self):
        self.image_path.set('');self.update_thumbnail()

    def update_thumbnail(self):
        self.thumbnail = None
        check = check_image_asset(self.image_path.get() or None, self.get_project())
        labels = {'not_assigned': 'Sense imatge assignada', 'missing': 'Falta el fitxer d’imatge',
                  'unresolved': 'No es pot resoldre la ruta sense projecte', 'unsupported': 'Format no admès',
                  'unreadable': 'No es pot llegir el fitxer'}
        if check.status != 'exists':
            self.image_preview.configure(image='', text=labels.get(check.status, check.status), width=32, height=8);return
        try:
            with Image.open(check.path) as source:
                image = ImageOps.exif_transpose(source).convert('RGB');image.thumbnail((260, 160))
            self.thumbnail = ImageTk.PhotoImage(image)
            self.image_preview.configure(image=self.thumbnail, text='', width=260, height=160)
        except (OSError, ValueError, Image.DecompressionBombError) as exc:
            self.image_preview.configure(image='', text='Imatge no vàlida: '+str(exc), width=32, height=8)

    def update_duration_state(self):
        self.duration_entry.configure(state='normal' if DISPLAY_MODES.get(self.display_mode.get())=='after_exit' else 'disabled')

    def save_zone(self):
        try:
            if not self.name.get().strip():raise ValueError('Escriu un nom per a la zona.')
            if not self.cells:raise ValueError('Selecciona una o diverses caselles dins del terra calibrat.')
            zone = Zone(self.current_id or uuid4().hex, self.name.get(), self.cells,
                        {i for i, var in enumerate(self.cards) if var.get()}, self.image_path.get() or None, self.enabled.get(),
                        DISPLAY_MODES[self.display_mode.get()],float(self.duration_s.get().replace(',', '.')), **self.audio_values())
            zones = [zone if existing.id == zone.id else existing for existing in self.config.zones]
            if not any(existing.id == zone.id for existing in self.config.zones):zones.append(zone)
            config = replace(self.config, zones=tuple(zones))
        except ValueError as exc:
            messagebox.showerror('Zona no vàlida', str(exc), parent=self.window);return False
        self.current_id = zone.id
        self.on_change(config);self.set_map(config)
        self.notice.set('Zona aplicada al mapa. Desa el projecte per conservar-la al disc.')
        return True

    def delete_zone(self):
        if self.current_id is None:
            self.notice.set('Selecciona una zona desada per eliminar-la.');return
        config = replace(self.config, zones=tuple(zone for zone in self.config.zones if zone.id != self.current_id))
        self.current_id = None
        self.on_change(config);self.set_map(config)
        self.notice.set('Zona eliminada del mapa. Desa el projecte per conservar el canvi.')
