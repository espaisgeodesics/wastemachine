"""Per-card Kaoss configuration and live MIDI, using the existing XY engine."""
from dataclasses import replace
import time
import tkinter as tk
from tkinter import ttk, messagebox

from atmo_ambience import AMBIENCES, PARAMETERS, TARGETS, ambience_preset, ambience_settings, effect_channels, mapped_cc
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
            if config.mode=='Efectes':ambience_settings(card)
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
        self.fx_values = {}
        self.fx_revision = 0
        self.pending_restore = {}

    def send(self, command):
        if self.app.muted and command.kind != 'note_off': return False
        return self.app.send_rule_midi(command)

    def send_for_marker(self, marker, command):
        config=self.engine.configs[marker]
        if config.mode!='Efectes':return self.send(command)
        if command.kind!='cc' or self.app.muted:return False
        card=self.app.cards[marker]
        value,neutral=mapped_cc(card,command.number,command.value)
        channels=effect_channels(self.app.cards,marker)
        accepted=bool(channels)
        for channel in sorted(channels):
            try:ok=self.app.send_rule_midi(replace(command,channel=channel,value=value)) is not False
            except Exception:ok=False
            if ok:
                self.fx_revision+=1
                self.fx_values.setdefault(marker,{})[(channel,command.number)]=(value,neutral,self.fx_revision)
            accepted=accepted and ok
        return accepted

    def restore(self, marker, force=False):
        if not force and ambience_settings(self.app.cards[marker])['kaoss_release']=='hold':return True
        from rule_outputs import MidiCommand
        values=self.fx_values.get(marker,{})
        for route,record in list(values.items()):
            others=[items[route] for id,items in self.fx_values.items() if id!=marker and route in items]
            value=max(others,key=lambda item:item[2])[0] if others else record[1]
            try:accepted=self.app.send_rule_midi(MidiCommand('cc',route[0],route[1],value)) is not False
            except Exception:accepted=False
            if accepted:values.pop(route,None)
        if not values:
            self.fx_values.pop(marker,None);self.pending_restore.pop(marker,None);return True
        self.pending_restore[marker]=force;return False

    def prepare(self, cards, rules):
        configs = live_configs(cards, rules)
        if configs != self.engine.configs and not self.stop():
            raise ValueError('No s’han pogut alliberar les notes o controls XY. Reconnecta MIDI abans de canviar la configuració.')
        return configs

    def configure(self, cards, rules):
        configs = self.prepare(cards, rules)
        if configs != self.engine.configs:self.engine = KaossEngine(configs)

    def observe(self, marker, x, y, rotation):
        if self.app.muted:return
        self.engine.observe(marker,x,y,rotation,time.monotonic())

    def tick(self):
        for marker,force in list(self.pending_restore.items()):self.restore(marker,force)
        previous=set(self.engine.voices)
        self.engine.tick(time.monotonic(),self.send,self.app.bpm,self.send_for_marker)
        for marker in previous-set(self.engine.voices):
            if marker in self.fx_values:self.restore(marker)

    def release(self, marker):
        if marker in self.fx_values:self.restore(marker)
        voice=self.engine.voices.get(marker)
        if voice is not None:voice.cancelled=True;self.tick()

    def stop(self):
        reset=True
        for marker in list(self.fx_values):reset=self.restore(marker,True) and reset
        return self.engine.stop(self.send,self.send_for_marker) and reset

    def invalidate_editors(self):self.generation += 1


def default_config(app, index):
    used = {card.get('channel', 1) for i, card in enumerate(app.cards)
            if i != index and card.get('function') in MIDI_FUNCTIONS | {CHAOS_FUNCTION}}
    used.update(action.channel for rule in app.rule_config.rules if rule.enabled
                for action in rule.actions if action.kind in ('note', 'cc'))
    channel = next((channel for channel in range(2, 17) if channel not in used),
                   1 if 1 not in used else None)
    return ambience_preset('Obert / aire',channel or 1)[0]


class CardKaossEditor(ttk.Frame):
    def __init__(self, window, app):
        super().__init__(window,padding=0);self.pack(fill='both',expand=True)
        ttk.Button(self,text='Aplicar ambients a la targeta',command=self.apply,style='Accent.TButton').pack(side='bottom',fill='x',padx=12,pady=8)
        holder=ttk.Frame(self);holder.pack(fill='both',expand=True)
        canvas=tk.Canvas(holder,bg='#0b1224',highlightthickness=0)
        bar=ttk.Scrollbar(holder,orient='vertical',command=canvas.yview);bar.pack(side='right',fill='y')
        canvas.pack(fill='both',expand=True);canvas.configure(yscrollcommand=bar.set)
        body=ttk.Frame(canvas,padding=12);item=canvas.create_window((0,0),window=body,anchor='nw')
        body.bind('<Configure>',lambda event:canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>',lambda event:canvas.itemconfigure(item,width=event.width))
        self.window,self.app=window,app;self.index=int(app.card_id.get())-1
        self.generation=app.live_kaoss.generation
        card=app.cards[self.index]
        config=KaossConfig.from_dict(card['kaoss']) if card.get('kaoss',{}).get('mode')=='Efectes' else default_config(app,self.index)
        metadata=ambience_settings(card) if card.get('kaoss',{}).get('mode')=='Efectes' else ambience_preset('Obert / aire',config.channel)[1]
        ttk.Label(body,text=f'Ambients XY · Targeta {self.index+1:02d}',font=('Segoe UI',14,'bold')).pack(anchor='w')
        ttk.Label(body,text='Modifica instruments que ja sonen a Cakewalk. No genera notes.\nAssigna els CC a efectes del sintetitzador o d’un bus amb MIDI Learn / ACT. No processa els WAV locals.',wraplength=800).pack(anchor='w',pady=8)
        head=ttk.Frame(body);head.pack(fill='x')
        self.preset_name=tk.StringVar(value=metadata['kaoss_ambience'])
        ttk.Combobox(head,textvariable=self.preset_name,values=AMBIENCES,state='readonly').pack(side='left')
        ttk.Button(head,text='Carregar ambient',command=self.load_preset).pack(side='left',padx=8)
        self.target=tk.StringVar(value=next(label for label,value in TARGETS.items() if value==metadata['kaoss_target']))
        ttk.Combobox(body,textvariable=self.target,values=tuple(TARGETS),state='readonly',width=48).pack(anchor='w',pady=6)
        targets=ttk.Frame(body);targets.pack(fill='x');self.target_cards=[]
        from atmo_ambience import SOUND_FUNCTIONS
        for i,c in enumerate(app.cards):
            variable=tk.BooleanVar(value=i in metadata['kaoss_targets']);self.target_cards.append(variable)
            ttk.Checkbutton(targets,text=f'T{i+1:02d} · canal {c["channel"]}',variable=variable,state='normal' if i!=self.index and c.get('function') in SOUND_FUNCTIONS else 'disabled').grid(row=i//4,column=i%4,sticky='w',padx=3)
        channel=ttk.Frame(body);channel.pack(fill='x',pady=4)
        ttk.Label(channel,text='Canal MIDI (només destinació concreta)').pack(side='left')
        self.channel=tk.StringVar(value=str(config.channel));ttk.Spinbox(channel,textvariable=self.channel,from_=1,to=16,width=5).pack(side='left',padx=7)
        self.variables={};self.ranges={};self.neutral={};self.parameter_names={}
        form=ttk.Frame(body);form.pack(fill='x',pady=8)
        for row,(axis,key,title) in enumerate((('x','x_cc','X · esquerra / dreta'),('y','y_cc','Y · baix / dalt'),('rotation','rotation_cc','Gir'))):
            ttk.Label(form,text=title).grid(row=row,column=0,sticky='w')
            cc=getattr(config,key);name=next((label for label,value in PARAMETERS.items() if value==cc),'Personalitzat')
            selection=tk.StringVar(value=name);self.parameter_names[axis]=selection
            combo=ttk.Combobox(form,textvariable=selection,values=tuple(PARAMETERS),state='readonly',width=22);combo.grid(row=row,column=1,padx=4,pady=4)
            variable=tk.StringVar(value=str(cc));self.variables[key]=variable
            ttk.Spinbox(form,textvariable=variable,from_=0,to=119,width=4).grid(row=row,column=2)
            combo.bind('<<ComboboxSelected>>',lambda event,a=axis,k=key:self.select_parameter(a,k))
            self.ranges[axis]=[tk.StringVar(value=str(n)) for n in metadata['kaoss_ranges'][axis]]
            self.neutral[axis]=tk.StringVar(value=str(metadata['kaoss_neutral'][axis]))
            for col,var in enumerate(self.ranges[axis]+[self.neutral[axis]],3):ttk.Spinbox(form,textvariable=var,from_=0,to=127,width=4).grid(row=row,column=col,padx=3)
        for column,title in ((2,'CC'),(3,'Mín.'),(4,'Màx.'),(5,'Neutre')):ttk.Label(form,text=title).grid(row=3,column=column)
        options=ttk.Frame(body);options.pack(fill='x')
        for i,(key,title) in enumerate((('rotation_enabled','Activar gir'),('invert_x','Invertir X'),('invert_y','Invertir Y'),('invert_rotation','Invertir gir'))):
            var=tk.BooleanVar(value=getattr(config,key));self.variables[key]=var;ttk.Checkbutton(options,text=title,variable=var).grid(row=0,column=i,padx=5)
        for key,title in (('smoothing_s','Suavització (0–2 s)'),('deadzone','Zona morta (0–0.2)'),('lost_timeout_s','Absència (0.05–2 s)')):
            row=ttk.Frame(body);row.pack(fill='x',pady=3);ttk.Label(row,text=title).pack(side='left')
            var=tk.StringVar(value=str(getattr(config,key)));self.variables[key]=var;ttk.Entry(row,textvariable=var,width=8).pack(side='right')
        self.release=tk.StringVar(value=metadata['kaoss_release'])
        ttk.Radiobutton(body,text='En retirar: tornar a neutre',variable=self.release,value='neutral').pack(anchor='w')
        ttk.Radiobutton(body,text='En retirar: mantenir ambient',variable=self.release,value='hold').pack(anchor='w')
        self.status=tk.StringVar(value='Els noms d’efecte no configuren automàticament Cakewalk: cal mapar els CC.')
        ttk.Label(body,textvariable=self.status,wraplength=800).pack(fill='x',pady=6)

    def select_parameter(self,axis,key):
        from atmo_ambience import neutral_cc
        cc=PARAMETERS[self.parameter_names[axis].get()]
        if cc is not None:self.variables[key].set(str(cc));self.neutral[axis].set(str(neutral_cc(cc)))

    def read(self):
        values=KaossConfig(mode='Efectes',channel=int(self.channel.get()),x_cc=74,y_cc=91,rotation_cc=12).to_dict()
        for key,var in self.variables.items():
            value=var.get();template=values[key]
            values[key]=value if isinstance(template,bool) else (int(value) if isinstance(template,int) else float(str(value).replace(',','.')))
        return KaossConfig.from_dict(values)

    def effect_settings(self):
        return ambience_settings(dict(kaoss=self.read().to_dict(),kaoss_target=TARGETS[self.target.get()],kaoss_targets=[i for i,var in enumerate(self.target_cards) if var.get()],kaoss_release=self.release.get(),kaoss_ambience=self.preset_name.get(),kaoss_ranges={a:[int(v.get()) for v in values] for a,values in self.ranges.items()},kaoss_neutral={a:int(v.get()) for a,v in self.neutral.items()}))

    def load_preset(self):
        try:
            config,meta=ambience_preset(self.preset_name.get(),int(self.channel.get()))
            for key,var in self.variables.items():var.set(getattr(config,key))
            for axis,key in (('x','x_cc'),('y','y_cc'),('rotation','rotation_cc')):
                cc=getattr(config,key);self.parameter_names[axis].set(next(label for label,value in PARAMETERS.items() if value==cc))
                for var,value in zip(self.ranges[axis],meta['kaoss_ranges'][axis]):var.set(str(value))
                self.neutral[axis].set(str(meta['kaoss_neutral'][axis]))
        except (ValueError,tk.TclError) as exc:self.error(exc)

    def apply(self):
        if self.generation!=self.app.live_kaoss.generation:self.error('El projecte ha canviat. Torna a obrir el formulari.');return False
        if int(self.app.card_id.get())-1!=self.index:self.error(f'Selecciona la targeta {self.index+1:02d}.');return False
        previous=self.app.kaoss_draft;previous_meta=getattr(self.app,'kaoss_effect_draft',None);channel=self.app.channel.get()
        try:
            self.app.kaoss_draft=self.read();self.app.kaoss_effect_draft=self.effect_settings()
            self.app.channel.set(self.app.kaoss_draft.channel);self.app.fun.set(CHAOS_FUNCTION)
            if not self.app.apply_card():
                self.app.kaoss_draft=previous;self.app.kaoss_effect_draft=previous_meta;self.app.channel.set(channel);return False
            self.status.set('Ambient aplicat. Mou la targeta per controlar els efectes mapats. Desa el projecte.');return True
        except (ValueError,tk.TclError) as exc:
            self.app.kaoss_draft=previous;self.app.kaoss_effect_draft=previous_meta;self.app.channel.set(channel);self.error(exc);return False

    def error(self,error):messagebox.showerror('ATMO ESFERA FX · Ambients XY',str(error),parent=self.window)
