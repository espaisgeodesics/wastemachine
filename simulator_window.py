"""Separate operator window; never calls application MIDI or visual actions."""
import math
import time
import tkinter as tk
from tkinter import ttk, messagebox

from participant_editor import ParticipantEditor
from participant_simulator import SOURCE_ID, SimulatorSession


class SimulatorWindow(ttk.Frame):
    def __init__(self, parent, session):
        super().__init__(parent, padding=8)
        self.session = session
        self.timer = None
        self.closed = False
        self.dragging = None
        self.angle = tk.DoubleVar(value=0)
        self.available = tk.BooleanVar(value=session.available)
        self.status = tk.StringVar(value='Tria una persona a la taula o al mapa; arrossega-la per moure-la.')
        self.pack(fill='both', expand=True)
        ttk.Label(self, text='SIMULADOR · cinc participants · sessió de proves independent',
                  font=('Segoe UI', 12, 'bold')).pack(anchor='w')
        ttk.Label(self, text='Coordenades virtuals de càmera. No modifica el projecte, la càmera real, MIDI ni la projecció.').pack(anchor='w')
        controls = ttk.Frame(self)
        controls.pack(fill='x', pady=5)
        ttk.Checkbutton(controls, text='Font disponible', variable=self.available, command=self.change_source).pack(side='left')
        ttk.Label(controls, text='Gir (graus)').pack(side='left', padx=(12, 2))
        ttk.Spinbox(controls, from_=0, to=359, textvariable=self.angle, width=7).pack(side='left')
        for label, command in (('APLICAR GIR', self.rotate), ('OCULTAR', lambda:self.visibility(False)),
                               ('MOSTRAR', lambda:self.visibility(True)), ('REINICIAR PROVA', self.reset)):
            ttk.Button(controls, text=label, command=command).pack(side='left', padx=3)
        notebook = ttk.Notebook(self)
        notebook.pack(fill='both', expand=True)
        map_tab = ttk.Frame(notebook)
        registry_tab = ttk.Frame(notebook)
        notebook.add(map_tab, text='Mapa i moviment')
        notebook.add(registry_tab, text='Participants i esdeveniments')
        self.canvas = tk.Canvas(map_tab, width=700, height=420, background='#171B24', highlightthickness=0)
        self.canvas.pack(fill='both', expand=True)
        self.canvas.bind('<Button-1>', self.pick)
        self.canvas.bind('<B1-Motion>', self.drag)
        self.canvas.bind('<ButtonRelease-1>', lambda event:setattr(self, 'dragging', None))
        self.canvas.bind('<Configure>', lambda event:self.draw())
        ttk.Label(map_tab, textvariable=self.status).pack(anchor='w', pady=3)
        # Existing editor, contracts and event view; only the isolated session is supplied.
        self.editor = ParticipantEditor(registry_tab, lambda:self.session.registry, lambda:self.session.tracker.snapshot(),
                                        lambda:self.session.tracker.sources(), lambda:self.session.events.snapshot(),
                                        self.retire, lambda:SOURCE_ID, session_only=True)
        self.editor.table.bind('<<TreeviewSelect>>', self.selection_changed, add='+')
        self.bind('<Destroy>', self.destroyed, add='+')
        self.pulse()

    def selected(self):
        pid = self.editor.selected_id
        if pid not in self.session.registry.snapshot():
            self.status.set('Selecciona primer un participant.')
            return None
        return pid

    def selection_changed(self, event=None):
        pose = self.session.poses().get(self.editor.selected_id)
        if pose is not None:
            self.angle.set(round(pose.orientation*360, 1))
        self.draw()

    def change_source(self):
        self.session.available = self.available.get()
        self.status.set('Font virtual disponible.' if self.session.available else 'Avaria virtual: cap persona no s’elimina.')
        self.draw()

    def reset(self):
        if not self.editor.discard():
            return
        if not messagebox.askyesno('Simulador', 'Reiniciar la prova amb cinc participants nous i buidar el registre virtual?', parent=self):
            return
        self.session.reset()
        self.available.set(True)
        self.angle.set(0)
        self.dragging = None
        self.editor.reset()
        self.editor.refresh_rows()
        self.status.set('Nova sessió virtual preparada. El projecte real es conserva.')
        self.draw()

    def rotate(self):
        pid = self.selected()
        if pid is None:
            return
        try:
            degrees = self.angle.get()
            if not math.isfinite(degrees):
                raise ValueError('El gir ha de ser finit')
            self.session.set_pose(pid, orientation=(degrees % 360) / 360)
            self.status.set(f'Gir virtual: {degrees % 360:.1f}°')
            self.draw()
        except (ValueError, tk.TclError) as exc:
            messagebox.showerror('Simulador', str(exc), parent=self)

    def visibility(self, visible):
        pid = self.selected()
        if pid is not None:
            self.session.set_pose(pid, visible=visible)
            self.status.set('Marcador mostrat; una persona retirada continua retirada.' if visible else
                            'Marcador ocult; es confirmarà absència després del llindar, sense eliminar la persona.')
            self.draw()

    def retire(self, pid, retired):
        self.session.set_retired(pid, retired, time.monotonic())
        self.draw()

    def bounds(self):
        return 25., 20., max(1., self.canvas.winfo_width()-50.), max(1., self.canvas.winfo_height()-40.)

    def pick(self, event):
        self.dragging = None
        x, y, width, height = self.bounds()
        poses = self.session.poses()
        nearest = min(poses, key=lambda pid:(x+poses[pid].position[0]*width-event.x)**2 +
                                           (y+poses[pid].position[1]*height-event.y)**2, default=None)
        if nearest is None:
            return
        pose = poses[nearest]
        if math.hypot(x+pose.position[0]*width-event.x, y+pose.position[1]*height-event.y) > 24:
            return
        self.editor.table.selection_set(nearest)
        self.editor.select()
        if self.editor.selected_id == nearest:
            self.dragging = nearest
            self.angle.set(round(pose.orientation*360, 1))
            self.status.set(f'Participant seleccionat: {self.session.registry.snapshot()[nearest].name or nearest}')
        self.draw()

    def drag(self, event):
        pid = self.editor.selected_id
        if pid is None or pid != self.dragging or pid not in self.session.registry.snapshot():
            return
        x, y, width, height = self.bounds()
        point = max(0., min(1., (event.x-x)/width)), max(0., min(1., (event.y-y)/height))
        self.session.set_pose(pid, position=point)
        self.status.set(f'Posició virtual: X {point[0]:.3f} · Y {point[1]:.3f}')
        self.draw()

    def draw(self):
        if not hasattr(self, 'editor'):
            return
        self.canvas.delete('all')
        x, y, width, height = self.bounds()
        self.canvas.create_rectangle(x, y, x+width, y+height, outline='#64748B')
        for i in range(1, 8):
            self.canvas.create_line(x+width*i/8, y, x+width*i/8, y+height, fill='#293443')
            self.canvas.create_line(x, y+height*i/8, x+width, y+height*i/8, fill='#293443')
        self.canvas.create_text(x+4, y+4, anchor='nw', text='SUPERFÍCIE VIRTUAL · no calibrada', fill='#AABBCD')
        states = self.session.registry.states(self.session.tracker.snapshot())
        for pid, pose in self.session.poses().items():
            binding = states[pid].binding
            px, py = x+pose.position[0]*width, y+pose.position[1]*height
            dim = not pose.visible or states[pid].presence == 'retired' or not self.session.available
            color = '#667080' if dim else binding.color
            self.canvas.create_oval(px-12, py-12, px+12, py+12, fill=color,
                                    outline='white' if pid == self.editor.selected_id else color, width=2)
            angle = pose.orientation*math.tau
            self.canvas.create_line(px, py, px+22*math.cos(angle), py+22*math.sin(angle), fill=color, width=2)
            self.canvas.create_text(px, py+25, text=f'{binding.name or "(sense nom)"} · ID {binding.marker_id}', fill=color)
            if dim:
                self.canvas.create_line(px-9, py-9, px+9, py+9, fill='white', width=2)

    def pulse(self):
        if self.closed:
            return
        try:
            self.session.advance(time.monotonic())
            self.draw()
        except ValueError as exc:
            self.status.set(str(exc))
        self.timer = self.after(100, self.pulse)

    def destroyed(self, event):
        if event.widget is self:
            self.closed = True
            if self.timer is not None:
                self.after_cancel(self.timer)
                self.timer = None
