"""Per-card Kaoss configuration and live MIDI, using the existing XY engine."""
from dataclasses import replace
from atmo_xy_control import BusXY, MidiFXOutput, bus_profile, CAKEWALK_PRESETS, LEGACY_CAKEWALK_PRESET
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
        self.output=MidiFXOutput(app)
        self.bus=BusXY(self.output.send)
        self.output_error=None

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
        bus_cards=BusXY.validate(cards,rules)
        legacy={i:c for i,c in configs.items() if i not in bus_cards}
        if (legacy != self.engine.configs or bus_cards != self.bus.cards) and not self.stop():
            raise ValueError('No s’han pogut alliberar els controls XY. Comprova la sortida MIDI abans de canviar la configuració.')
        return configs

    def configure(self, cards, rules):
        configs=self.prepare(cards,rules)
        bus_cards=BusXY.validate(cards,rules)
        legacy={i:c for i,c in configs.items() if i not in bus_cards}
        if legacy!=self.engine.configs:self.engine=KaossEngine(legacy)
        self.bus.configure(bus_cards)
        if not bus_cards:self.output.close()

    def observe(self, marker, x, y, rotation):
        if self.app.muted:return
        if marker in self.bus.cards:
            project=getattr(self.app,'musical_position',None)
            point=project(x,y) if callable(project) else (x,y)
            if point is None:self.bus.release(marker,time.monotonic());return
            self.bus.observe(marker,*point,rotation,time.monotonic())
        else:self.engine.observe(marker,x,y,rotation,time.monotonic())

    def tick(self):
        self.bus.tick(time.monotonic())
        if self.output.error and self.output.error!=self.output_error:
            status=getattr(self.app,'status',None)
            if hasattr(status,'set'):status.set('Control XY: '+self.output.error)
        self.output_error=self.output.error
        for marker,force in list(self.pending_restore.items()):self.restore(marker,force)
        previous=set(self.engine.voices)
        self.engine.tick(time.monotonic(),self.send,self.app.bpm,self.send_for_marker)
        for marker in previous-set(self.engine.voices):
            if marker in self.fx_values:self.restore(marker)

    def release(self, marker):
        if marker in self.bus.cards:self.bus.release(marker,time.monotonic());return
        if marker in self.fx_values:self.restore(marker)
        voice=self.engine.voices.get(marker)
        if voice is not None:voice.cancelled=True;self.tick()

    def stop(self):
        reset=self.bus.stop()
        for marker in list(self.fx_values):reset=self.restore(marker,True) and reset
        return self.engine.stop(self.send,self.send_for_marker) and reset

    def close(self):
        self.stop();self.output.close()

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
        self.bus_enabled=tk.BooleanVar(value=bool(card.get('kaoss_bus')))
        config=KaossConfig.from_dict(card['kaoss']) if card.get('kaoss',{}).get('mode')=='Efectes' else default_config(app,self.index)
        metadata=ambience_settings(card) if card.get('kaoss',{}).get('mode')=='Efectes' else ambience_preset('Obert / aire',config.channel)[1]
        ttk.Label(body,text=f'Ambients XY · Targeta {self.index+1:02d}',font=('Segoe UI',14,'bold')).pack(anchor='w')
        ttk.Label(body,text='Modifica instruments que ja sonen a Cakewalk. No genera notes.\nAssigna els CC amb Control remoto de Cakewalk. No processa els WAV locals.',wraplength=800).pack(anchor='w',pady=8)
        prepared=ttk.LabelFrame(body,text='Presets Cakewalk · assignables a qualsevol targeta',padding=8);prepared.pack(fill='x',pady=5)
        saved_name=metadata['kaoss_ambience']
        self.cakewalk_preset=tk.StringVar(value=saved_name if saved_name in CAKEWALK_PRESETS else 'Filtre + reverberació')
        self.cakewalk_box=ttk.Combobox(prepared,textvariable=self.cakewalk_preset,values=tuple(CAKEWALK_PRESETS),state='readonly',width=32)
        self.cakewalk_box.pack(anchor='w')
        ttk.Button(prepared,text='Carregar preset a aquesta targeta',command=lambda:self.load_bus_profile(self.cakewalk_preset.get())).pack(anchor='w',pady=4)
        self.cakewalk_info=tk.StringVar()
        ttk.Label(prepared,textvariable=self.cakewalk_info,wraplength=740,justify='left').pack(fill='x')
        self.cakewalk_box.bind('<<ComboboxSelected>>',lambda event:self.describe_cakewalk())
        self.describe_cakewalk()
        ttk.Label(prepared,text='Obre el projecte corresponent a Cakewalk. ATMO no carrega ni canvia els seus efectes. Reverb i eco comparteixen CC16/17: per usar-los en targetes independents, canvia el canal o els CC i adapta Cakewalk.',wraplength=740,justify='left').pack(fill='x',pady=4)
        self.port=tk.StringVar(value=(card.get('kaoss_bus') or {}).get('port',''))
        self.rate=tk.StringVar(value=str((card.get('kaoss_bus') or {}).get('rate_hz',25)))
        self.return_s=tk.StringVar(value=str((card.get('kaoss_bus') or {}).get('return_s',.6)))
        route=ttk.Frame(body);route.pack(fill='x')
        ttk.Checkbutton(route,text='Control dedicat de bus XY',variable=self.bus_enabled).pack(side='left')
        ttk.Label(route,text='Port MIDI (buit = principal)').pack(side='left',padx=5)
        self.port_box=ttk.Combobox(route,textvariable=self.port,width=24);self.port_box.pack(side='left')
        ttk.Button(route,text='Actualitzar ports',command=self.refresh_ports).pack(side='left',padx=3)
        from atmo_ui import wrap_controls
        ttk.Button(route,text='Usar sortida MIDI principal',command=self.use_main_output).pack(side='left',padx=3)
        wrap_controls(route)
        self.port_feedback=tk.StringVar()
        ttk.Label(body,textvariable=self.port_feedback,style='Muted.TLabel',wraplength=740).pack(fill='x',pady=4)
        self.port.trace_add('write',lambda *args:self.describe_port())
        for variable,title in ((self.rate,'Màxim enviaments/s (1–50)'),(self.return_s,'Retorn progressiu (0–5 s)')):
            line=ttk.Frame(body);line.pack(fill='x',pady=3)
            ttk.Label(line,text=title).pack(side='left');ttk.Entry(line,textvariable=variable,width=7).pack(side='right')
        head=ttk.Frame(body);head.pack(fill='x')
        self.preset_name=tk.StringVar(value=metadata['kaoss_ambience'])
        ttk.Combobox(head,textvariable=self.preset_name,values=tuple(CAKEWALK_PRESETS)+(LEGACY_CAKEWALK_PRESET,)+AMBIENCES,state='readonly').pack(side='left')
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
        ttk.Button(body,text='Filtre menys extrem · mínim X a 60',command=self.limit_filter).pack(anchor='w',pady=4)
        ttk.Label(body,text='Per als presets de filtre: limita el tall més baix per conservar més so. 60 és un valor MIDI, no una freqüència. Ajusta el mínim a l’oïda i prem Aplicar.',style='Muted.TLabel',wraplength=740).pack(fill='x')
        options=ttk.Frame(body);options.pack(fill='x')
        for i,(key,title) in enumerate((('rotation_enabled','Activar gir'),('invert_x','Invertir X'),('invert_y','Invertir Y'),('invert_rotation','Invertir gir'))):
            var=tk.BooleanVar(value=getattr(config,key));self.variables[key]=var;ttk.Checkbutton(options,text=title,variable=var).grid(row=0,column=i,padx=5)
        for key,title in (('smoothing_s','Suavització (0–2 s)'),('deadzone','Zona morta (0–0.2)'),('lost_timeout_s','Absència (0.05–2 s)')):
            row=ttk.Frame(body);row.pack(fill='x',pady=3);ttk.Label(row,text=title).pack(side='left')
            var=tk.StringVar(value=str(getattr(config,key)));self.variables[key]=var;ttk.Entry(row,textvariable=var,width=8).pack(side='right')
        self.release=tk.StringVar(value=metadata['kaoss_release'])
        ttk.Radiobutton(body,text='En retirar: tornar progressivament als valors de retorn (no és un bypass)',variable=self.release,value='neutral').pack(anchor='w')
        ttk.Radiobutton(body,text='En retirar: mantenir ambient',variable=self.release,value='hold').pack(anchor='w')
        test=ttk.LabelFrame(body,text='Prova sense càmera · aplica primer la configuració',padding=6);test.pack(fill='x',pady=8)
        for row,axis in enumerate(('x','y')):
            ttk.Label(test,text=axis.upper()).grid(row=row,column=0)
            for col,value in enumerate((0,64,127),1):
                ttk.Button(test,text=str(value),command=lambda a=axis,v=value:self.test_axis(a,v)).grid(row=row,column=col,padx=4,pady=3)
        ttk.Button(body,text='Guia: connectar filtre i reverb a Cakewalk',command=self.open_guide).pack(fill='x',pady=4)
        ttk.Button(test,text='Reconnectar sortida XY',command=self.reconnect_output).grid(row=2,column=0,columnspan=4,sticky='ew',pady=4)
        self.last_probe=''
        self.probe_info=tk.StringVar(value='Aplica la configuració abans d’activar qualsevol aprenentatge MIDI a Cakewalk.')
        ttk.Label(test,textvariable=self.probe_info,wraplength=730,justify='left').grid(row=3,column=0,columnspan=4,sticky='ew',pady=5)
        ttk.Button(test,text='Copiar dades de la prova',command=self.copy_probe).grid(row=4,column=0,columnspan=4,sticky='ew')
        ttk.Button(body,text='Guia alternativa sense ACT · Remote Control',command=lambda:self.open_guide('GUIA_CONTROL_DIRECTE_CAKEWALK.txt')).pack(fill='x',pady=4)
        self.status=tk.StringVar(value='Els noms d’efecte no configuren automàticament Cakewalk: cal mapar els CC.')
        ttk.Label(body,textvariable=self.status,wraplength=800).pack(fill='x',pady=6)
        self.refresh_ports()

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
        result=ambience_settings(dict(kaoss=self.read().to_dict(),kaoss_target=TARGETS[self.target.get()],kaoss_targets=[i for i,var in enumerate(self.target_cards) if var.get()],kaoss_release=self.release.get(),kaoss_ambience=self.preset_name.get(),kaoss_ranges={a:[int(v.get()) for v in values] for a,values in self.ranges.items()},kaoss_neutral={a:int(v.get()) for a,v in self.neutral.items()}))
        result['kaoss_bus']=dict(port=self.port.get().strip(),rate_hz=float(self.rate.get().replace(',','.')),return_s=float(self.return_s.get().replace(',','.'))) if self.bus_enabled.get() else None
        return result

    def open_guide(self,filename="GUIA_XY_CAKEWALK.txt"):
        from pathlib import Path
        import os
        path=Path(__file__).resolve().parent/filename
        try:
            if hasattr(os,'startfile'):os.startfile(path)
            else:
                import webbrowser
                webbrowser.open(path.as_uri())
        except OSError as exc:self.error(exc)

    def describe_port(self):
        port=self.port.get().strip()
        available=tuple(self.port_box['values'])
        main=self.app.live_kaoss.output.main_name()
        if not port:
            text=f'Sortida principal: {main}. Aplica per utilitzar-la.' if main else 'Sortida principal: connecta MIDI a la finestra principal o selecciona un port disponible.'
        elif port not in available:
            text=f'Port desat «{port}» no disponible. Actualitza ports i selecciona el port real, o usa la sortida principal. No s’ha substituït automàticament.'
        else:text=f'Port disponible: {port}. Aplica i desa el projecte per conservar-lo.'
        self.port_feedback.set(text)

    def use_main_output(self):
        self.port.set('')
        self.status.set('Sortida principal seleccionada al formulari. Prem Aplicar; la targeta desada encara no ha canviat.')

    def limit_filter(self):
        if self.preset_name.get() not in CAKEWALK_PRESETS and self.preset_name.get()!=LEGACY_CAKEWALK_PRESET:
            self.error('Selecciona un preset Cakewalk de filtre abans d’utilitzar aquest ajust.');return
        self.ranges['x'][0].set('60')
        if int(self.ranges['x'][1].get())<60:self.ranges['x'][1].set('127')
        self.status.set('Mínim X a 60 al formulari. Comprova el so i prem Aplicar. El filtre enfosqueix el so; no canvia l’afinació.')

    def refresh_ports(self):
        try:
            import mido
            self.port_box['values']=list(mido.get_output_names())
            self.describe_port()
        except Exception as exc:
            self.port_feedback.set(f'No es poden consultar els ports: {exc}. Prem Actualitzar ports després de connectar MIDI.')

    def describe_cakewalk(self):
        self.cakewalk_info.set(CAKEWALK_PRESETS[self.cakewalk_preset.get()][2])

    def load_bus_profile(self,name=LEGACY_CAKEWALK_PRESET):
        config,meta=bus_profile(name=name)
        self.bus_enabled.set(True);self.channel.set(str(config.channel))
        # The profile changes effects, never an explicitly chosen device name.
        self.rate.set('25');self.return_s.set('0.6')
        self.target.set('Canal MIDI concret');self.release.set('neutral')
        self.preset_name.set(name)
        self.cakewalk_preset.set('Filtre + reverberació' if name==LEGACY_CAKEWALK_PRESET else name)
        self.describe_cakewalk()
        for selected in self.target_cards:selected.set(False)
        for key,var in self.variables.items():var.set(getattr(config,key))
        for axis,key in (('x','x_cc'),('y','y_cc'),('rotation','rotation_cc')):
            self.parameter_names[axis].set('Personalitzat')
            for var,value in zip(self.ranges[axis],meta['kaoss_ranges'][axis]):var.set(str(value))
            self.neutral[axis].set(str(meta['kaoss_neutral'][axis]))
        self.status.set(f'{self.cakewalk_preset.get()} · canal 16 · X CC{config.x_cc} · Y CC{config.y_cc} · port {self.port.get() or chr(171)+"principal"+chr(187)}. Prem Aplicar i desa el projecte. Cakewalk necessita les assignacions corresponents.')

    def reconnect_output(self):
        self.app.live_kaoss.bus.stop();self.app.live_kaoss.output.reconnect()
        self.status.set('Sortida XY preparada per reconnectar. Prem una prova o mou la targeta; no es reprodueixen ordres antigues.')

    def copy_probe(self):
        if not self.last_probe:
            self.status.set('Encara no hi ha cap prova enviada. Aplica la configuració i prem un botó X/Y.');return
        self.window.clipboard_clear();self.window.clipboard_append(self.last_probe)
        self.status.set('Dades de la prova copiades. Confirmació local; no confirma recepció a Cakewalk.')

    def test_axis(self,axis,value):
        self.last_probe=''
        try:
            if self.app.muted:raise ValueError('Prem REPRENDRE MIDI abans de provar el control XY.')
            if getattr(self.app,'camera',None) is not None or self.app.simulation.get():
                raise ValueError('Atura la càmera i desactiva la simulació abans de les proves manuals, per aprendre només el CC escollit.')
            if self.generation!=self.app.live_kaoss.generation or int(self.app.card_id.get())-1!=self.index:
                raise ValueError('La targeta o el projecte han canviat. Torna a obrir el formulari XY.')
            card=self.app.cards[self.index]
            if card.get('function')!=CHAOS_FUNCTION or card.get('kaoss')!=self.read().to_dict() or ambience_settings(card)!=self.effect_settings():
                raise ValueError('Hi ha configuració pendent. Prem APLICAR abans d’activar l’aprenentatge MIDI a Cakewalk. Els botons de prova no apliquen ni canvien el projecte.')
            bus=self.app.live_kaoss.bus
            if self.index not in bus.cards:raise ValueError('Activa Control dedicat de bus XY i aplica la configuració.')
            if not bus.test(self.index,axis,value):raise ValueError(self.app.live_kaoss.output.error or bus.error)
            config=self.app.cards[self.index]['kaoss']
            port=(self.app.cards[self.index].get('kaoss_bus') or {}).get('port') or 'Sortida principal'
            number=config[axis+'_cc']
            raw=f'{0xB0+config["channel"]-1:02X} {number:02X} {value:02X}'
            self.last_probe=f'Port: {port} · {axis.upper()} · canal={config["channel"]} · CC={number} · valor={value} · bytes={raw} · acceptat localment'
            self.probe_info.set(self.last_probe)
            self.status.set(f'Enviat {axis.upper()} · canal {config["channel"]} · CC{config[axis+"_cc"]} = {value}. Comprova el comandament de Cakewalk.')
        except (ValueError,tk.TclError) as exc:
            self.probe_info.set('Prova no enviada: '+str(exc));self.error(exc)

    def load_preset(self):
        if self.preset_name.get() in CAKEWALK_PRESETS or self.preset_name.get()==LEGACY_CAKEWALK_PRESET:
            self.load_bus_profile(self.preset_name.get());return
        try:
            self.bus_enabled.set(False)
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
