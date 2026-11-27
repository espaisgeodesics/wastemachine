"""Current ATMO entry widgets and zone editor, shared by the desktop application."""
import tkinter as tk
from tkinter import ttk, messagebox
from spatial_zone_editor import ZoneEditor, DISPLAY_MODES
from atmo_runtime import BG, PANEL, SURFACE, TEXT, MUTED, CYAN, PURPLE, FOREST, LEAF
MODES=("Joc","Música","Exposició","Instal·lació immersiva")

def label(parent, text, size=11, color=TEXT, bold=False, **kwargs):
    return tk.Label(parent,text=text,bg=parent.cget("bg"),fg=color,
                    font=("Segoe UI",size,"bold" if bold else "normal"),**kwargs)

def btn(parent,text,command,accent=False):
    return tk.Button(parent,text=text,command=command,bg=LEAF if accent else FOREST,
                     fg="#07182a" if accent else TEXT,activebackground=CYAN,
                     activeforeground="#07182a",font=("Segoe UI",10,"bold"),
                     relief="flat",padx=12,pady=9,cursor="hand2")

class AtmoZoneEditor(ZoneEditor):
    """Original editing controller with ATMO widgets; no duplicate zone model."""

    def _build(self):
        host = self.window
        header = tk.Frame(host, bg=PANEL)
        header.pack(fill="x", padx=12, pady=(8, 4))
        label(header, "ZONES DEL MAPA", 12, CYAN, True).pack(side="left")
        btn(header, "Nova zona", self.new_zone).pack(side="right", padx=3)
        btn(header, "Eliminar zona", self.delete_zone).pack(side="right", padx=3)
        tools=tk.Frame(host,bg=PANEL)
        tools.pack(fill="x",padx=12)
        btn(tools,"Calibrar terra",lambda:self.on_calibrate()).pack(side="left",padx=3)
        btn(tools,"Tornar als visuals",lambda:self.on_release()).pack(side="left",padx=3)
        body = tk.Frame(host, bg=PANEL)
        body.pack(fill="both", expand=True, padx=12, pady=4)
        left = tk.Frame(body, bg=PANEL, width=155)
        left.pack(side="left", fill="y", padx=(0, 8))
        self.list = ttk.Treeview(left, columns=("name",), show="headings",
                                 height=8, selectmode="browse", style="Atmo.Treeview")
        self.list.heading("name", text="Zones")
        self.list.column("name", width=145, minwidth=80)
        self.list.pack(fill="both", expand=True)
        self.list.bind("<<TreeviewSelect>>", self.select_zone)
        center = tk.Frame(body, bg=PANEL)
        center.pack(side="left", fill="both", expand=True)
        self.canvas = tk.Canvas(center, bg="#101c30", highlightthickness=0,
                                width=400, height=400)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda event: self.draw())
        self.canvas.bind("<ButtonPress-1>", self.press)
        self.canvas.bind("<B1-Motion>", self.drag)
        tk.Label(center, textvariable=self.selection_info, bg=PANEL, fg=MUTED,
                 wraplength=380, font=("Segoe UI", 9)).pack(fill="x", pady=4)
        # Only the properties scroll; Apply remains visible on small windows.
        right = tk.Frame(body, bg=PANEL, width=280)
        right.pack(side="right", fill="y", padx=(8, 0))
        right.pack_propagate(False)
        btn(right, "Aplicar zona al mapa", self.save_zone, True).pack(side="bottom", fill="x", pady=4)
        scroll = tk.Canvas(right, bg=PANEL, highlightthickness=0, width=258)
        bar = ttk.Scrollbar(right, orient="vertical", command=scroll.yview)
        bar.pack(side="right", fill="y")
        scroll.pack(side="left", fill="both", expand=True)
        scroll.configure(yscrollcommand=bar.set)
        form = tk.Frame(scroll, bg=PANEL)
        item = scroll.create_window((0, 0), window=form, anchor="nw")
        form.bind("<Configure>", lambda event: scroll.configure(scrollregion=scroll.bbox("all")))
        scroll.bind("<Configure>", lambda event: scroll.itemconfigure(item, width=event.width))

        label(form, "Nom de la zona", 10).pack(anchor="w")
        tk.Entry(form, textvariable=self.name, bg=SURFACE, fg=TEXT,
                 insertbackground=TEXT, relief="flat").pack(fill="x", pady=5)
        def check(parent, text, variable):
            return tk.Checkbutton(parent, text=text, variable=variable, bg=PANEL,
                                  fg=TEXT, selectcolor=SURFACE, activebackground=PANEL,
                                  activeforeground=TEXT, font=("Segoe UI", 9))
        check(form, "Zona habilitada", self.enabled).pack(anchor="w")
        label(form, "Targetes autoritzades · 01–16", 10, CYAN).pack(anchor="w", pady=(10, 3))
        targets = tk.Frame(form, bg=PANEL)
        targets.pack(fill="x")
        for i, var in enumerate(self.cards):
            check(targets, f"{i+1:02d}", var).grid(row=i//4, column=i%4, sticky="w")
        label(form, "Imatge JPG / PNG", 10, CYAN).pack(anchor="w", pady=(10, 3))
        tk.Entry(form, textvariable=self.image_path, state="readonly",
                 readonlybackground=SURFACE, fg=TEXT).pack(fill="x")
        btn(form, "Triar imatge…", self.choose_image).pack(fill="x", pady=3)
        btn(form, "Sense imatge", self.remove_image).pack(fill="x", pady=3)
        label(form, "Durada de la imatge", 10).pack(anchor="w", pady=(10, 3))
        mode = ttk.Combobox(form, textvariable=self.display_mode,
                            values=tuple(DISPLAY_MODES), state="readonly", width=29)
        mode.pack(fill="x")
        mode.bind("<<ComboboxSelected>>", lambda event: self.update_duration_state())
        label(form, "Segons després de retirar-la", 9, MUTED).pack(anchor="w", pady=(5, 0))
        self.duration_entry = ttk.Spinbox(form, textvariable=self.duration_s,
                                          from_=.1, to=86400, increment=.5, width=8)
        self.duration_entry.pack(anchor="w", pady=4)
        self.update_duration_state()
        self.build_audio_controls(form)
        self.image_preview = tk.Label(form, bg=PANEL, fg=TEXT, width=32,
                                      height=8, wraplength=240)
        self.image_preview.pack(fill="x", pady=5)
        for variable in (self.calibration_info, self.runtime_info, self.notice):
            tk.Label(host, textvariable=variable, bg=PANEL, fg=MUTED,
                     wraplength=900, justify="left", font=("Segoe UI", 9)).pack(fill="x", padx=12, pady=2)

    def draw(self):
        # Keep the blue ATMO grid. Original hit testing rejects points outside
        # the floor circle and original validation rejects active overlaps.
        c = self.canvas
        c.delete("all")
        width, height = max(1, c.winfo_width()), max(1, c.winfo_height())
        ratio=getattr(self.config.calibration,'aspect_ratio',1.)
        map_height=max(1,min(height-40,(width-40)/ratio));size=map_height*ratio
        self.map_height=map_height
        ox, oy = (width-size)/2, (height-map_height)/2
        self.geometry = (ox, oy, size)
        grid = self.config.grid
        palette = ("#277f91", "#8565bb", "#bc7e4b", "#5c9c79", "#a75c8b", "#8b9d4b")
        owners = {}
        for i, zone in enumerate(self.config.zones):
            if zone.id == self.current_id:
                continue
            for cell in zone.cells:
                if zone.enabled or cell not in owners:
                    owners[cell] = palette[i % len(palette)] if zone.enabled else SURFACE
        colors={zone.id:palette[i % len(palette)] if zone.enabled else SURFACE for i,zone in enumerate(self.config.zones)}
        owners={cell:colors[zone.id] for cell,zone in self.config._owners.items() if zone.id!=self.current_id}
        audio_cells={cell for zone in self.config.zones if zone.enabled and zone.audio_path for cell in zone.cells}
        for row in range(grid.rows):
            for col in range(grid.columns):
                cell = row, col
                selected = cell in self.cells
                fill = CYAN if selected else owners.get(cell, "#223b59" if grid.eligible(cell) else "#101c30")
                c.create_rectangle(ox+col*size/grid.columns, oy+row*map_height/grid.rows,
                                   ox+(col+1)*size/grid.columns, oy+(row+1)*map_height/grid.rows,
                                   fill=fill, outline=TEXT if selected else "#3c5674",
                                   width=2 if selected else 1)
                if cell in audio_cells:
                    c.create_text(ox+(col+.75)*size/grid.columns,oy+(row+.25)*map_height/grid.rows,
                                  text='♪',fill=TEXT,font=('Segoe UI',9,'bold'))
        getattr(c,'create_oval' if grid.shape=='circle' else 'create_rectangle')(ox, oy, ox+size, oy+map_height, outline=CYAN, width=2)
        c.create_text(width/2, 10, text=f"{grid.rows} × {grid.columns} · {len(self.config.zones)} zones",
                      fill=MUTED, font=("Segoe UI", 9))
        self.selection_info.set(f"{len(self.cells)} caselles seleccionades · Clic / arrossega per afegir o treure")

    def delete_zone(self):
        if self.current_id is None:
            self.notice.set("Selecciona una zona desada per eliminar-la.")
            return
        if messagebox.askyesno("Eliminar zona", "Vols eliminar aquesta zona i els seus canvis pendents?",
                               parent=self.window):
            super().delete_zone()


