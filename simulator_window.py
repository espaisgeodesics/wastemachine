"""Separate operator window; never calls application MIDI or visual actions."""
import math
import time
import tkinter as tk
from tkinter import ttk, messagebox

from participant_editor import ParticipantEditor
from participant_simulator import SOURCE_ID, SimulatorSession
from experience_rules import RulesConfig
from rule_editor import RuleEditor
from dataclasses import replace
from PIL import Image, ImageTk


class SimulatorWindow(ttk.Frame):
    def __init__(self, parent, session, spatial_config=None, rules_config=None, project_file=None, participants=None):
        super().__init__(parent, padding=8)
        self.session = session
        self.spatial_config = spatial_config
        self.rules_config = rules_config
        self.project_file = project_file or (lambda:None)
        self.participants = participants
        self.rules_window = None
        self.rules_editor = None
        self.preview_token = None
        self.preview_size=None
        self.timer = None
        self.closed = False
        self.dragging = None
        self.angle = tk.DoubleVar(value=0)
        self.available = tk.BooleanVar(value=session.available)
        self.status = tk.StringVar(value='Tria una persona a la taula o al mapa; arrossega-la per moure-la.')
        self.zone_summary = tk.StringVar(value=f'Zones de prova: {len(session.spatial.config.zones)} · calibració virtual')
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
        zone_controls = ttk.Frame(self)
        zone_controls.pack(fill='x', pady=(0, 4))
        ttk.Button(zone_controls, text='CARREGAR ZONES I REGLES DEL PROJECTE', command=self.load_zones).pack(side='left')
        ttk.Button(zone_controls, text='REGLES DE PROVA...', command=self.open_rules).pack(side='left', padx=4)
        ttk.Label(zone_controls, textvariable=self.zone_summary).pack(side='left', padx=8)
        notebook = ttk.Notebook(self)
        notebook.pack(fill='both', expand=True)
        map_tab = ttk.Frame(notebook)
        registry_tab = ttk.Frame(notebook)
        notebook.add(map_tab, text='Mapa i moviment')
        notebook.add(registry_tab, text='Participants i esdeveniments')
        self.output_tab=ttk.Frame(notebook);notebook.add(self.output_tab,text='Sortida de prova')
        self.output_label=tk.Label(self.output_tab,bg='black');self.output_label.pack(fill='both',expand=True)
        self.output_status=tk.StringVar();ttk.Label(self.output_tab,textvariable=self.output_status).pack(anchor='w')
        self.output_midi=ttk.Treeview(self.output_tab,columns=('kind','channel','number','value'),show='headings',height=4)
        for key,label in (('kind','MIDI simulat'),('channel','Canal'),('number','Nota / CC'),('value','Valor')):
            self.output_midi.heading(key,text=label);self.output_midi.column(key,width=100)
        self.output_midi.pack(fill='x');self.midi_preview=()
        self.output_audio=ttk.Treeview(self.output_tab,columns=('group','marker','file','gain','fade'),show='headings',height=4)
        for key,label in (('group','Àudio simulat (sense so)'),('marker','ID'),('file','Clip'),('gain','Volum %'),('fade','Fade')):
            self.output_audio.heading(key,text=label);self.output_audio.column(key,width=90 if key!='file' else 180)
        self.output_audio.pack(fill='x')
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
                                        self.retire, lambda:SOURCE_ID, session_only=True,
                                        zones=lambda:self.session.spatial.snapshot())
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

    def load_zones(self):
        if self.rules_editor is not None and not self.rules_editor.discard():return
        if self.spatial_config is None:
            self.status.set('No hi ha cap projecte disponible per copiar-ne les zones.')
            return
        rules = self.rules_config() if self.rules_config else RulesConfig()
        real = self.participants().snapshot() if self.participants else {}
        mapped=[]
        for rule in rules.rules:
            source=rule.source_id
            if source and source != SOURCE_ID:
                if not source.startswith('camera:'):
                    messagebox.showerror('Regles de prova',f'Font no disponible al simulador: {source}',parent=self);return
                source=SOURCE_ID
            participant=rule.participant_id
            if participant:
                person=real.get(participant)
                virtual=self.session.registry.participant_for(SOURCE_ID,person.marker_id) if person else None
                if virtual is None:
                    messagebox.showerror('Regles de prova','No hi ha una persona virtual amb el marcador de la regla.',parent=self);return
                participant=virtual.participant_id
            mapped.append(replace(rule,source_id=source,participant_id=participant))
        self.session.configure_spatial(self.spatial_config())
        self.session.configure_rules(RulesConfig(tuple(mapped)),self.project_file())
        if self.rules_editor is not None:self.rules_editor.reload()
        self.zone_summary.set(f'Zones de prova: {len(self.session.spatial.config.zones)} · calibració virtual')
        self.status.set('Còpia de zones i regles carregada. Només executa sortides de prova.')
        self.editor.refresh_rows()
        self.draw()

    def open_rules(self):
        if self.rules_window is not None and self.rules_window.winfo_exists():self.rules_window.lift();return
        window=self.rules_window=tk.Toplevel(self);window.title('REGLES DE PROVA · sessió virtual');window.geometry(f'940x{min(840,max(500,self.winfo_screenheight()-100))}')
        self.rules_editor=RuleEditor(window,lambda:self.session.rule_engine.config,
          lambda config:self.session.configure_rules(config,self.session.rule_project),
          lambda rid:self.session.manual_rule(rid,time.monotonic()),lambda:self.session.rule_outputs.clear_visuals(),
          lambda:self.session.rule_outputs.log_snapshot(),session_only=True,
          zones=lambda:self.session.spatial.config.zones,participants=lambda:self.session.registry.snapshot().values())
        def close():
            if self.rules_editor.discard():window.destroy();self.rules_window=None;self.rules_editor=None
        window.protocol('WM_DELETE_WINDOW',close)

    def reset(self):
        if not self.editor.discard():
            return
        if self.rules_editor is not None and not self.rules_editor.discard():return
        if not messagebox.askyesno('Simulador', 'Reiniciar la prova amb cinc participants nous i buidar el registre virtual?', parent=self):
            return
        self.session.reset()
        self.available.set(True)
        self.angle.set(0)
        self.dragging = None
        self.editor.reset()
        self.editor.refresh_rows()
        if self.rules_editor is not None:self.rules_editor.reload()
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
        width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
        side = max(1., min(width-50., height-40.))
        return (width-side)/2, (height-side)/2, side, side

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
        config = self.session.spatial.config
        for zone in config.zones:
            if not zone.enabled:
                continue
            for row, column in sorted(zone.cells):
                self.canvas.create_rectangle(x+width*column/config.grid.columns, y+height*row/config.grid.rows,
                                             x+width*(column+1)/config.grid.columns, y+height*(row+1)/config.grid.rows,
                                             fill='#263D50', outline='#5C839A')
            row, column = min(zone.cells)
            self.canvas.create_text(x+width*(column+.5)/config.grid.columns, y+height*(row+.5)/config.grid.rows,
                                    text=zone.name, fill='#CDDCEA')
        self.canvas.create_oval(x, y, x+width, y+height, outline='#AABBCD')
        self.canvas.create_text(x, y-10, anchor='w', text='SUPERFÍCIE VIRTUAL · calibració sintètica', fill='#AABBCD')
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
            winner=self.session.rule_outputs.winner()
            size=max(1,min(640,self.output_label.winfo_width())),max(1,min(360,self.output_label.winfo_height()))
            if winner is not self.preview_token or size!=self.preview_size:
                frame=self.session.rule_outputs.frame(size)
                image=Image.new('RGB',size,'black') if frame is None else Image.fromarray(frame[:,:,::-1])
                self.output_photo=ImageTk.PhotoImage(image,master=self.output_label)
                self.output_label.config(image=self.output_photo)
                self.preview_token=winner
                self.preview_size=size
            self.output_status.set(('Propietari: '+winner.request.rule.name if winner else 'Sense ordre visual de prova')+
                                  f' · MIDI simulat: {len(self.session.midi_commands)} missatges')
            commands=tuple(self.session.midi_commands)[-12:]
            if commands!=self.midi_preview:
                for iid in self.output_midi.get_children():self.output_midi.delete(iid)
                for i,command in enumerate(commands):self.output_midi.insert('','end',iid=str(i),values=(command.kind,command.channel,command.number,command.value))
                if commands:self.output_midi.see(str(len(commands)-1))
                self.midi_preview=commands
            voices={str(voice.slot):voice for voice in self.session.audio.snapshot()}
            for iid in self.output_audio.get_children():
                if iid not in voices:self.output_audio.delete(iid)
            for iid,voice in voices.items():
                from pathlib import Path
                values=voice.group,voice.marker_id if voice.marker_id is not None else '—',Path(voice.path).name,round(voice.gain*100),'Sí' if voice.fading else 'No'
                if self.output_audio.exists(iid):self.output_audio.item(iid,values=values)
                else:self.output_audio.insert('','end',iid=iid,values=values)
        except ValueError as exc:
            self.status.set(str(exc))
        self.timer = self.after(100, self.pulse)

    def discard(self):
        return self.editor.discard() and (self.rules_editor is None or self.rules_editor.discard())

    def destroyed(self, event):
        if event.widget is self:
            self.closed = True
            self.session.rule_outputs.stop_midi(self.session.send_rule_midi)
            self.session.audio.stop_all()
            if self.timer is not None:
                self.after_cancel(self.timer)
                self.timer = None
