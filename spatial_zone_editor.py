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
        reference = zone.image_path
        if reference:
            path = Path(reference)
            if not path.is_absolute():
                if old_project is None:
                    raise ValueError('No es pot resoldre una imatge relativa sense projecte d’origen.')
                path = Path(old_project).resolve().parent / path
            reference = image_reference(path, new_project)
        zones.append(replace(zone, image_path=reference))
    return replace(config, zones=tuple(zones))


@lru_cache(maxsize=4096)
def _cell_polygon(row, column, grid):
    # Clip an approximation of the circle to the cell rectangle.
    from math import cos, sin, tau
    points = [(.5 + .5*cos(i*tau/96), .5 + .5*sin(i*tau/96)) for i in range(96)]
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
        self.cards = [tk.BooleanVar(value=False) for _ in range(16)]
        self.notice = tk.StringVar()
        self.selection_info = tk.StringVar()
        self.calibration_info = tk.StringVar()
        self._build()
        for var in (self.name, self.image_path, self.enabled, *self.cards):
            var.trace_add('write', self._changed)
        self.set_map(config)

    def _build(self):
        ttk.Label(self.window, textvariable=self.calibration_info, wraplength=1000).pack(fill='x', padx=10, pady=7)
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
        self.image_preview = tk.Label(right, bg='#171411', fg='#e6d0b5', width=32, height=8, wraplength=265)
        self.image_preview.pack(fill='both', expand=True, pady=5)
        ttk.Button(right, text='DESAR ZONA AL MAPA', command=self.save_zone).pack(fill='x', pady=6)
        center = ttk.Frame(body);center.pack(fill='both', expand=True)
        self.canvas = tk.Canvas(center, bg='#171411', highlightthickness=0, width=440, height=440)
        self.canvas.pack(fill='both', expand=True)
        self.canvas.bind('<Configure>', lambda event: self.draw())
        self.canvas.bind('<ButtonPress-1>', self.press)
        self.canvas.bind('<B1-Motion>', self.drag)
        ttk.Label(center, textvariable=self.selection_info).pack(fill='x', pady=5)
        ttk.Label(self.window, textvariable=self.notice, wraplength=1000).pack(fill='x', padx=10, pady=(4, 8))

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
            self.list.insert('', 'end', iid=zone.id, values=(zone.name + ('' if zone.enabled else ' · desactivada'),))
        calibration = 'Calibració matemàtica vàlida · pendent de prova física' if config.calibration else 'SENSE CALIBRACIÓ: el mapa no està alineat amb el terra real'
        self.calibration_info.set(calibration + ' · Fase 2: edició; encara no activa imatges al projector.')
        self.loading = False
        if selected and any(zone.id == selected for zone in config.zones):
            self._load_zone(selected)
        else:
            self._new_draft()

    def _new_draft(self):
        self.loading = True
        self.current_id = None;self.cells = set()
        self.name.set('');self.image_path.set('');self.enabled.set(True)
        for i, var in enumerate(self.cards):var.set(i == self.default_card)
        for item in self.list.selection():self.list.selection_remove(item)
        self.loading = False;self.dirty = False
        self.notice.set('Selecciona caselles dins del cercle i configura una zona nova.')
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
        size = max(1, min(width, height)-28)
        ox, oy = (width-size)/2, (height-size)/2
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
                points = [value for x, y in polygon for value in (ox+x*size, oy+y*size)]
                if len(points) < 6:continue
                selected = cell in self.cells
                self.canvas.create_polygon(points, fill='#ba8548' if selected else owners.get(cell, '#2d241e'),
                                           outline='#ffe1a4' if selected else '#76604d', width=2 if selected else 1)
        self.canvas.create_oval(ox, oy, ox+size, oy+size, outline='#e1b887', width=2)
        self.selection_info.set(f'{len(self.cells)} caselles seleccionades · Clic / arrossega per afegir o treure')

    def cell_at_event(self, event):
        ox, oy, size = self.geometry
        return self.config.grid.cell_at(((event.x-ox)/size, (event.y-oy)/size))

    def press(self, event):
        self.visited = set();self.drag(event)

    def drag(self, event):
        cell = self.cell_at_event(event)
        if cell is None or cell in self.visited:return
        self.visited.add(cell)
        if self.enabled.get() and any(zone.enabled and zone.id != self.current_id and cell in zone.cells for zone in self.config.zones):
            self.notice.set('Aquesta casella ja pertany a una altra zona habilitada.');return
        if cell in self.cells:self.cells.remove(cell)
        else:self.cells.add(cell)
        self._changed()

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

    def save_zone(self):
        try:
            if not self.name.get().strip():raise ValueError('Escriu un nom per a la zona.')
            if not self.cells:raise ValueError('Selecciona una o diverses caselles dins del cercle.')
            if self.enabled.get() and any(zone.enabled and zone.id!=self.current_id and zone.cells.intersection(self.cells) for zone in self.config.zones):raise ValueError('Hi ha caselles que ja pertanyen a una altra zona habilitada.')
            zone = Zone(self.current_id or uuid4().hex, self.name.get(), self.cells,
                        {i for i, var in enumerate(self.cards) if var.get()}, self.image_path.get() or None, self.enabled.get())
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
