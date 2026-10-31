"""Operator form for declarative rules and multiple actions; no code editor."""
import tkinter as tk
from tkinter import ttk, filedialog, colorchooser, messagebox
from uuid import uuid4

from experience_rules import ExperienceRule, RuleAction, RulesConfig, TRIGGERS, ACTION_KINDS

TRIGGER_NAMES = dict(zip(TRIGGERS, ('Entrada de zona', 'Sortida de zona', 'Aparició', 'Absència confirmada', 'Ordre manual')))
ACTION_NAMES = dict(zip(ACTION_KINDS, ('Color', 'Imatge', 'Nota MIDI', 'MIDI CC', 'Alliberar grup visual')))


class RuleEditor(ttk.Frame):
    def __init__(self, parent, config, apply, manual, release, log, session_only=False, zones=None, participants=None):
        super().__init__(parent, padding=10)
        self.config = config
        self.apply_config = apply
        self.manual = manual
        self.release = release
        self.log = log
        self.zones = zones or (lambda:())
        self.participants = participants or (lambda:())
        self.lookups = {}
        self.widgets = {}
        self.pid = None
        self.actions = []
        self.action_index = None
        self.dirty = False
        self.action_dirty = False
        self.loading = False
        self.timer = None
        self.pack(fill='both', expand=True)
        canvas=tk.Canvas(self,highlightthickness=0,bg='#151210')
        scrollbar=ttk.Scrollbar(self,orient='vertical',command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set);scrollbar.pack(side='right',fill='y');canvas.pack(side='left',fill='both',expand=True)
        body=ttk.Frame(canvas);item=canvas.create_window(0,0,window=body,anchor='nw')
        body.bind('<Configure>',lambda event:canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>',lambda event:canvas.itemconfigure(item,width=event.width))
        ttk.Label(body, text='REGLES DE PROVA' if session_only else 'REGLES DE L’EXPERIÈNCIA', font=('Segoe UI', 12, 'bold')).pack(anchor='w')
        ttk.Label(body, text=('Sessió virtual: aplicar reinicia les sortides de prova; no envia MIDI real.' if session_only else
                             'Aplicar reinicia les sortides de regles. EXECUTAR envia les accions reals. Desa el projecte per conservar-les.')).pack(anchor='w')
        self.table = ttk.Treeview(body, columns=('name', 'trigger', 'priority', 'enabled'), show='headings', height=4, selectmode='browse')
        for key, label in (('name','Nom'),('trigger','Quan passa'),('priority','Prioritat'),('enabled','Activa')):
            self.table.heading(key,text=label);self.table.column(key,width=180 if key in ('name','trigger') else 80)
        self.table.pack(fill='x',pady=6);self.table.bind('<<TreeviewSelect>>',self.select)
        self.fields = {}
        form=ttk.Frame(body);form.pack(fill='x')
        specs=(('name','Nom','',None),('trigger','Quan passa',TRIGGER_NAMES['zone_entered'],list(TRIGGER_NAMES.values())),
               ('priority','Prioritat','10',None),('group','Grup visual','escena',None),
               ('source_id','Font (buit = totes)','',None),('marker_id','ID (buit = tots)','',None),
               ('participant_id','Participant (buit = tots)','',[]),('zone_id','Zona (buit = totes)','',[]),
               ('reason','Motiu de sortida','movement',['movement','missing','any']))
        for i,(key,label,value,choices) in enumerate(specs):
            var=self.fields[key]=tk.StringVar(value=value)
            row,col=divmod(i,3)
            ttk.Label(form,text=label).grid(row=row*2,column=col,sticky='w',padx=4)
            widget=ttk.Combobox(form,textvariable=var,values=choices,state='normal' if key in ('participant_id','zone_id') else 'readonly') if choices is not None else ttk.Entry(form,textvariable=var)
            self.widgets[key]=widget
            widget.grid(row=row*2+1,column=col,sticky='ew',padx=4,pady=(0,4));form.columnconfigure(col,weight=1)
            var.trace_add('write',self.changed)
        self.enabled=tk.BooleanVar(value=True);self.enabled.trace_add('write',self.changed)
        ttk.Checkbutton(body,text='Regla activa',variable=self.enabled).pack(anchor='w')
        ttk.Label(body,text='Accions (afegeix-les a la llista abans d’aplicar la regla)').pack(anchor='w',pady=(5,0))
        self.action_table=ttk.Treeview(body,columns=('kind','value'),show='headings',height=3,selectmode='browse')
        self.action_table.heading('kind',text='Acció');self.action_table.heading('value',text='Paràmetres')
        self.action_table.pack(fill='x');self.action_table.bind('<<TreeviewSelect>>',self.select_action)
        action_form=ttk.Frame(body);action_form.pack(fill='x',pady=4)
        self.af={}
        self.af_widgets={}
        for i,(key,label,value) in enumerate((('kind','Acció','Color'),('value','Color / imatge / valor CC','#FFFFFF'),
                                             ('channel','Canal MIDI','16'),('number','Nota / CC','60'),
                                             ('velocity','Velocitat','90'),('duration_s','Durada s (0 = persistent)','0'))):
            var=self.af[key]=tk.StringVar(value=value)
            row,col=divmod(i,3)
            ttk.Label(action_form,text=label).grid(row=row*2,column=col,sticky='w',padx=4)
            widget=ttk.Combobox(action_form,textvariable=var,values=list(ACTION_NAMES.values()),state='readonly') if key=='kind' else ttk.Entry(action_form,textvariable=var)
            self.af_widgets[key]=widget
            widget.grid(row=row*2+1,column=col,sticky='ew',padx=4);action_form.columnconfigure(col,weight=1)
            var.trace_add('write',self.action_changed)
        self.af['kind'].trace_add('write',self.update_action_fields)
        buttons=ttk.Frame(body);buttons.pack(fill='x',pady=4)
        for label,callback in (('AFEGIR ACCIÓ',lambda:self.put_action(False)),('CANVIAR ACCIÓ',lambda:self.put_action(True)),
                               ('TREURE ACCIÓ',self.remove_action),('IMATGE...',self.choose_image),('COLOR...',self.choose_color)):
            ttk.Button(buttons,text=label,command=callback).pack(side='left',padx=2)
        buttons=ttk.Frame(body);buttons.pack(fill='x',pady=4)
        for label,callback in (('NOVA',self.new),('APLICAR REGLA',self.apply_rule),('ELIMINAR',self.remove_rule),
                               ('EXECUTAR',self.execute),('ALLIBERAR SORTIDA',self.release)):
            ttk.Button(buttons,text=label,command=callback).pack(side='left',padx=2)
        self.notice=tk.StringVar();ttk.Label(body,textvariable=self.notice,wraplength=850).pack(anchor='w')
        ttk.Label(body,text='MIDI: canals diferents dels de les targetes. Motiu: movement = moviment, missing = pèrdua, any = inclou revalidació.',wraplength=850).pack(anchor='w')
        self.diagnostics=tk.StringVar();ttk.Label(body,textvariable=self.diagnostics,wraplength=850).pack(anchor='w',pady=4)
        self.bind('<Destroy>',self.destroyed,add='+')
        self.reload();self.refresh()

    def changed(self,*args):
        if not self.loading:self.dirty=True

    def action_changed(self,*args):
        if not self.loading:self.dirty=True;self.action_dirty=True

    def update_action_fields(self,*args):
        active={'Color':{'value','duration_s'},'Imatge':{'value','duration_s'},
                'Nota MIDI':{'channel','number','velocity','duration_s'},'MIDI CC':{'value','channel','number'}}.get(self.af['kind'].get(),set())
        for key,widget in self.af_widgets.items():
            if key!='kind':widget.state(['!disabled'] if key in active else ['disabled'])

    def discard(self):
        return not self.dirty or messagebox.askyesno('Regles','Descartar els canvis del formulari sense aplicar?',parent=self)

    def reload(self):
        self.lookups={'zone_id':{f'{z.name} · {z.id}':z.id for z in self.zones()},
                      'participant_id':{f'{p.name or "(sense nom)"} · {p.participant_id}':p.participant_id for p in self.participants()}}
        for key,lookup in self.lookups.items():self.widgets[key].configure(values=['']+list(lookup))
        self.loading=True;self.pid=None;self.action_index=None;self.actions=[]
        defaults={'name':'','trigger':'Entrada de zona','priority':'10','group':'escena','source_id':'','marker_id':'','participant_id':'','zone_id':'','reason':'movement'}
        for key,value in defaults.items():self.fields[key].set(value)
        for key,value in {'kind':'Color','value':'#FFFFFF','channel':'16','number':'60','velocity':'90','duration_s':'0'}.items():self.af[key].set(value)
        self.enabled.set(True)
        self.dirty=False;self.action_dirty=False;self.loading=False
        self.refresh_tables();self.notice.set('Les accions visuals persisteixen amb durada 0. Una nota necessita entre 0,05 i 60 s.')

    def refresh_tables(self):
        for iid in self.table.get_children():self.table.delete(iid)
        for rule in self.config().rules:
            self.table.insert('','end',iid=rule.rule_id,values=(rule.name,TRIGGER_NAMES[rule.trigger],rule.priority,'Sí' if rule.enabled else 'No'))
        for iid in self.action_table.get_children():self.action_table.delete(iid)
        for i,action in enumerate(self.actions):
            detail=('Grup visual de la regla' if action.kind=='release_visual' else action.value) if action.kind not in ('note','cc') else f'Canal {action.channel} · {action.number} · {action.value if action.kind=="cc" else str(action.duration_s)+" s"}'
            self.action_table.insert('','end',iid=str(i),values=(ACTION_NAMES[action.kind],detail))

    def new(self):
        if self.discard():self.reload()

    def select(self,event=None):
        selection=self.table.selection()
        if not selection or selection[0]==self.pid:return
        if not self.discard():
            if self.pid and self.table.exists(self.pid):self.table.selection_set(self.pid)
            else:self.table.selection_remove(*selection)
            return
        rule=next(r for r in self.config().rules if r.rule_id==selection[0])
        self.loading=True;self.pid=rule.rule_id;self.actions=list(rule.actions);self.action_index=None
        for key,var in self.fields.items():
            value=getattr(rule,key)
            if key in self.lookups:value=next((label for label,rid in self.lookups[key].items() if rid==value),value)
            var.set(TRIGGER_NAMES[value] if key=='trigger' else '' if value is None else str(value))
        self.enabled.set(rule.enabled);self.loading=False;self.dirty=False;self.action_dirty=False
        self.refresh_tables()

    def select_action(self,event=None):
        selection=self.action_table.selection()
        if not selection:return
        if self.action_dirty:
            if self.action_index is not None and int(selection[0])==self.action_index:return
            if not messagebox.askyesno('Regles','Descartar els paràmetres d’acció pendents?',parent=self):
                if self.action_index is not None:self.action_table.selection_set(str(self.action_index))
                else:self.action_table.selection_remove(*selection)
                return
        self.action_index=int(selection[0]);action=self.actions[self.action_index];self.loading=True
        for key,var in self.af.items():var.set(ACTION_NAMES[action.kind] if key=='kind' else str(getattr(action,key)))
        self.loading=False;self.action_dirty=False

    def put_action(self,replace_existing):
        try:
            values={k:v.get() for k,v in self.af.items()}
            values['kind']=next(k for k,v in ACTION_NAMES.items() if v==values['kind'])
            active={'color':{'value','duration_s'},'image':{'value','duration_s'},'note':{'channel','number','velocity','duration_s'},'cc':{'value','channel','number'},'release_visual':set()}[values['kind']]|{'kind'}
            values={k:v for k,v in values.items() if k in active}
            for key in ('channel','number','velocity'):
                if key in values:values[key]=int(values[key])
            if 'duration_s' in values:values['duration_s']=float(values['duration_s'])
            action=RuleAction(**values)
            if replace_existing:
                if self.action_index is None:raise ValueError('Selecciona una acció de la llista')
                self.actions[self.action_index]=action
            else:
                if len(self.actions)>=8:raise ValueError('Màxim vuit accions per regla')
                self.actions.append(action)
            self.dirty=True;self.action_dirty=False;self.action_index=None;self.refresh_tables();self.notice.set('Acció afegida. Prem APLICAR REGLA.')
        except (ValueError,StopIteration) as exc:messagebox.showerror('Regles',str(exc),parent=self)

    def remove_action(self):
        if self.action_index is not None:
            self.actions.pop(self.action_index);self.action_index=None;self.dirty=True;self.refresh_tables()

    def choose_image(self):
        path=filedialog.askopenfilename(parent=self,filetypes=[('Imatges','*.jpg *.jpeg *.png')])
        if path:self.af['kind'].set('Imatge');self.af['value'].set(path)

    def choose_color(self):
        color=colorchooser.askcolor(parent=self)[1]
        if color:self.af['kind'].set('Color');self.af['value'].set(color.upper())

    def apply_rule(self):
        try:
            if self.action_dirty:raise ValueError('Prem AFEGIR ACCIÓ o CANVIAR ACCIÓ abans d’aplicar la regla.')
            values={k:v.get().strip() for k,v in self.fields.items()}
            for key,lookup in self.lookups.items():values[key]=lookup.get(values[key],values[key])
            values['trigger']=next(k for k,v in TRIGGER_NAMES.items() if v==values['trigger'])
            values['priority']=int(values['priority']);values['marker_id']=int(values['marker_id']) if values['marker_id'] else None
            rule=ExperienceRule(self.pid or uuid4().hex,actions=tuple(self.actions),enabled=self.enabled.get(),**values)
            rules=[r for r in self.config().rules if r.rule_id!=rule.rule_id]+[rule]
            self.apply_config(RulesConfig(tuple(rules)))
            self.pid=rule.rule_id;self.dirty=False;self.refresh_tables();self.notice.set('Regla aplicada. EXECUTAR prova les accions; altrament espera l’esdeveniment.')
            return True
        except (ValueError,StopIteration) as exc:
            messagebox.showerror('Regles',str(exc),parent=self);return False

    def remove_rule(self):
        if self.pid and messagebox.askyesno('Regles','Eliminar aquesta regla?',parent=self):
            self.apply_config(RulesConfig(tuple(r for r in self.config().rules if r.rule_id!=self.pid)));self.reload()

    def execute(self):
        if self.dirty:
            messagebox.showwarning('Regles','Aplica els canvis abans d’executar.',parent=self);return
        if self.pid:self.manual(self.pid)

    def refresh(self):
        entries=list(self.log())[-3:]
        self.diagnostics.set('\n'.join(f'{name} · {kind}: {result}' for _,name,kind,result in entries))
        self.timer=self.after(250,self.refresh)

    def destroyed(self,event):
        if event.widget is self and self.timer is not None:self.after_cancel(self.timer);self.timer=None
