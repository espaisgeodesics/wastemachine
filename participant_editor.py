"""Operator-only participant editor. Does not touch musical card assignments."""
import tkinter as tk
from tkinter import ttk, colorchooser, messagebox
from uuid import uuid4

from participants import ParticipantBinding


PRESENCE_LABELS = {
    'not_seen': 'Encara no vist', 'detected': 'Detectat',
    'temporarily_lost': 'Perdut temporalment', 'absent': 'Absent confirmat',
    'retired': 'Retirat de la sessió',
}
EVENT_LABELS = {
    'source_available': 'Font disponible', 'source_unavailable': 'Font no disponible',
    'marker_appeared': 'Aparició', 'marker_recovered': 'Recuperació',
    'marker_temporarily_lost': 'Pèrdua temporal', 'marker_absent': 'Absència confirmada',
    'marker_retired': 'Marcador retirat', 'participant_retired': 'Participant retirat',
    'participant_restored': 'Participant recuperat',
}


class ParticipantEditor(ttk.Frame):
    def __init__(self, parent, registry, markers, sources, events, retire, default_source):
        super().__init__(parent, padding=10)
        self.registry = registry
        self.markers = markers
        self.sources = sources
        self.events = events
        self.retire = retire
        self.default_source = default_source
        self.selected_id = None
        self.dirty = False
        self._loading = False
        self._timer = None
        self.name = tk.StringVar()
        self.color = tk.StringVar(value='#48B8E8')
        self.source = tk.StringVar(value=default_source())
        self.marker = tk.StringVar(value='0')
        self.notice = tk.StringVar()
        self.source_status = tk.StringVar()
        self.pack(fill='both', expand=True)
        ttk.Label(self, text='PARTICIPANTS · registre de sessió', font=('Segoe UI', 12, 'bold')).pack(anchor='w')
        ttk.Label(self, text='El nom del participant és independent del nom i la funció musical de la targeta.').pack(anchor='w')
        columns = ('name', 'color', 'source', 'marker', 'presence', 'position')
        self.table = ttk.Treeview(self, columns=columns, show='headings', height=7, selectmode='browse')
        for key, label, width in zip(columns, ('Nom', 'Color', 'Font', 'ID ArUco', 'Presència', 'Posició de càmera'),
                                     (130, 80, 100, 65, 150, 190)):
            self.table.heading(key, text=label)
            self.table.column(key, width=width, minwidth=50)
        self.table.pack(fill='both', expand=True, pady=8)
        self.table.bind('<<TreeviewSelect>>', self.select)
        form = ttk.Frame(self)
        form.pack(fill='x')
        for column, (label, variable, width) in enumerate((('Nom / àlies', self.name, 24), ('Color #RRGGBB', self.color, 12),
                                                           ('Font (càmera)', self.source, 16), ('ID ArUco (0–15)', self.marker, 9))):
            ttk.Label(form, text=label).grid(row=0, column=column, sticky='w', padx=3)
            if variable is self.marker:
                field = ttk.Combobox(form, textvariable=variable, values=list(range(16)), state='readonly', width=width)
            else:
                field = ttk.Entry(form, textvariable=variable, width=width)
            field.grid(row=1, column=column, sticky='ew', padx=3)
            variable.trace_add('write', self.changed)
        self.swatch = tk.Label(form, width=3, bg=self.color.get())
        self.swatch.grid(row=1, column=4, padx=5)
        ttk.Button(form, text='TRIAR COLOR', command=self.choose_color).grid(row=1, column=5)
        buttons = ttk.Frame(self)
        buttons.pack(fill='x', pady=8)
        for label, command in (('NOU', self.new), ('APLICAR PARTICIPANT', self.apply),
                               ('RETIRAR', lambda: self.set_retired(True)),
                               ('RECUPERAR', lambda: self.set_retired(False)), ('ELIMINAR', self.remove)):
            ttk.Button(buttons, text=label, command=command).pack(side='left', padx=2)
        ttk.Label(self, textvariable=self.notice, wraplength=800).pack(anchor='w')
        ttk.Label(self, textvariable=self.source_status, wraplength=800).pack(anchor='w', pady=4)
        ttk.Label(self, text='Retirar és una ordre de sessió: no atura la funció MIDI/visual de la targeta. Desa el projecte per conservar noms, colors i assignacions.',
                  wraplength=800).pack(anchor='w')
        ttk.Label(self, text='Esdeveniments recents (diagnòstic passiu)').pack(anchor='w', pady=(8, 2))
        self.event_table = ttk.Treeview(self, columns=('sequence', 'event', 'source', 'marker', 'participant'), show='headings', height=5)
        for key, label in (('sequence', '#'), ('event', 'Esdeveniment'), ('source', 'Font'), ('marker', 'ID'), ('participant', 'ID participant')):
            self.event_table.heading(key, text=label)
            self.event_table.column(key, width=70 if key in ('sequence', 'marker') else 180)
        self.event_table.pack(fill='both', expand=True)
        self.bind('<Destroy>', self.destroyed, add='+')
        self.reset()
        self.refresh()

    def changed(self, *args):
        if not self._loading:
            self.dirty = True
            self.notice.set('Canvis pendents: prem APLICAR PARTICIPANT.')

    def discard(self):
        return not self.dirty or messagebox.askyesno('Participants', 'Descartar els canvis del formulari sense aplicar?', parent=self)

    def reset(self):
        self._loading = True
        self.selected_id = None
        self.name.set('')
        self.color.set('#48B8E8')
        source = self.default_source()
        used = {p.marker_id for p in self.registry().snapshot().values() if p.source_id == source}
        self.source.set(source)
        self.marker.set(str(next((i for i in range(16) if i not in used), 0)))
        self.swatch.config(bg=self.color.get())
        self.dirty = False
        self._loading = False
        self.notice.set('Nou participant: indica nom, color i marcador. ID ArUco 0 correspon a la targeta 01.')
        for iid in self.table.selection():
            self.table.selection_remove(iid)

    def new(self):
        if self.discard():
            self.reset()

    def select(self, event=None):
        selection = self.table.selection()
        if not selection or selection[0] == self.selected_id:
            return
        if not self.discard():
            if self.selected_id:
                self.table.selection_set(self.selected_id)
            else:
                self.table.selection_remove(*selection)
            return
        binding = self.registry().snapshot().get(selection[0])
        if binding is None:
            return
        self._loading = True
        self.selected_id = binding.participant_id
        self.name.set(binding.name)
        self.color.set(binding.color)
        self.source.set(binding.source_id)
        self.marker.set(str(binding.marker_id))
        self.swatch.config(bg=binding.color)
        self.dirty = False
        self._loading = False
        self.notice.set('Participant seleccionat. Canviar-ne el marcador conserva l’identificador intern.')

    def choose_color(self):
        try:
            self.winfo_rgb(self.color.get())
            initial = self.color.get()
        except tk.TclError:
            initial = '#48B8E8'
        color = colorchooser.askcolor(initialcolor=initial, parent=self)[1]
        if color:
            self.color.set(color.upper())
            self.swatch.config(bg=color)

    def apply(self):
        try:
            binding = ParticipantBinding(self.selected_id or uuid4().hex, self.name.get().strip(),
                                         self.color.get().strip(), self.source.get().strip(), int(self.marker.get()))
            self.registry().upsert(binding)
        except (ValueError, tk.TclError) as exc:
            messagebox.showerror('Participants', str(exc), parent=self)
            return False
        self.selected_id = binding.participant_id
        self.dirty = False
        self.swatch.config(bg=binding.color)
        self.notice.set('Participant aplicat. Desa el projecte per conservar-lo.')
        self.refresh_rows()
        self.table.selection_set(binding.participant_id)
        return True

    def set_retired(self, retired):
        if self.dirty:
            messagebox.showwarning('Participants', 'Aplica els canvis del formulari abans de canviar l’estat de sessió.', parent=self)
            return
        if self.selected_id is not None:
            self.retire(self.selected_id, retired)
            self.dirty = False
            self.notice.set('Retirada de sessió aplicada.' if retired else 'Participant recuperat; es conserva la seva identitat.')
            self.refresh_rows()

    def remove(self):
        if self.selected_id is None:
            return
        if messagebox.askyesno('Participants', 'Eliminar aquesta vinculació del registre? La targeta continuarà funcionant.', parent=self):
            self.registry().remove(self.selected_id)
            self.reset()
            self.refresh_rows()

    def refresh_rows(self):
        states = self.registry().states(self.markers())
        for iid in self.table.get_children():
            if iid not in states:
                self.table.delete(iid)
        for pid, state in states.items():
            p, marker = state.binding, state.marker_state
            position = '—'
            if marker is not None:
                x, y = marker.last_observation.position
                position = f'{x:.3f}, {y:.3f}' + ('' if state.observed else ' (antiga)')
            values = (p.name or '(sense nom)', p.color, p.source_id, p.marker_id, PRESENCE_LABELS[state.presence], position)
            tag = 'p:' + pid
            self.table.tag_configure(tag, foreground=p.color)
            if self.table.exists(pid):
                self.table.item(pid, values=values, tags=(tag,))
            else:
                self.table.insert('', 'end', iid=pid, values=values, tags=(tag,))
        sources = self.sources()
        self.source_status.set('Fonts: ' + (' · '.join(f'{key}: {"disponible" if source.status == "ok" else "NO DISPONIBLE"}'
                                                     for key, source in sorted(sources.items())) or 'encara no observades'))
        events = self.events()[-30:]
        wanted = {str(e.sequence) for e in events}
        for iid in self.event_table.get_children():
            if iid not in wanted:
                self.event_table.delete(iid)
        for event in events:
            iid = str(event.sequence)
            values = (event.sequence, EVENT_LABELS.get(event.kind, event.kind), event.source_id,
                      event.marker_id if event.marker_id is not None else '—', event.participant_id or '—')
            if self.event_table.exists(iid):
                self.event_table.item(iid, values=values)
            else:
                self.event_table.insert('', 'end', iid=iid, values=values)

    def refresh(self):
        self.refresh_rows()
        self._timer = self.after(250, self.refresh)

    def destroyed(self, event):
        if event.widget is self and self._timer is not None:
            self.after_cancel(self._timer)
            self._timer = None
