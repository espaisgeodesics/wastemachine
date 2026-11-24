"""Dedicated, effect-only MIDI XY. Explicit clock; never emits notes or global resets."""
from copy import deepcopy
from dataclasses import dataclass
from math import exp, isfinite

# Bank, volume/expression, pedals, data-entry and parameter selection are not effect controls.
RESERVED={0,6,7,11,32,38,64,66,69,96,97,98,99,100,101}


def settings(card):
    if card.get('function','Chaos Oscillator (Kaoss XY)')!='Chaos Oscillator (Kaoss XY)':return None
    data=card.get('kaoss_bus')
    if data is None:return None
    if not isinstance(data,dict) or set(data)-{'port','rate_hz','return_s'}:raise ValueError('Configuració de sortida XY no vàlida')
    port=data.get('port','');rate=data.get('rate_hz',25);release=data.get('return_s',.6)
    if not isinstance(port,str) or len(port)>256:raise ValueError('Port XY no vàlid')
    for value,low,high,name in ((rate,1,50,'Enviaments/s'),(release,0,5,'Retorn (s)')):
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not isfinite(value) or not low<=value<=high:raise ValueError(f'{name}: {low}–{high}')
    config=card.get('kaoss',{})
    if config.get('mode')!='Efectes' or card.get('kaoss_target')!='channel':raise ValueError('El control de bus XY necessita mode Efectes i canal concret')
    for axis in axes(card):
        cc=config[axis+'_cc']
        if cc in RESERVED or not 1<=cc<=119:raise ValueError('Tria CC lliures (p. ex. 16 i 17), sense volum, pedals ni controls reservats')
    return dict(port=port,rate_hz=rate,return_s=release)


def axes(card):return ('x','y','rotation') if card['kaoss'].get('rotation_enabled',False) else ('x','y')


CAKEWALK_PRESETS={
    'Filtre + reverberació':(16,17,'X: filtre LP del Bus D · Y: enviament D → E (Sonitus Reverb).'),
    'Filtre + eco':(16,17,'X: filtre LP del Bus D · Y: enviament D → F (Sonitus Delay).'),
    'Filtre + distorsió':(18,19,'X: filtre LP del Bus G, després de House of Metal · Y: enviament D → G.'),
}
LEGACY_CAKEWALK_PRESET='Cakewalk · filtre i reverb'


def bus_profile(channel=16,name=LEGACY_CAKEWALK_PRESET):
    from kaoss_xy import KaossConfig
    x,y,_=CAKEWALK_PRESETS['Filtre + reverberació' if name==LEGACY_CAKEWALK_PRESET else name]
    config=KaossConfig(mode='Efectes',channel=channel,x_cc=x,y_cc=y,rotation_cc=20,rotation_enabled=False)
    meta=dict(kaoss_target='channel',kaoss_targets=[],kaoss_release='neutral',kaoss_ambience=name,
        kaoss_ranges={'x':[0,127],'y':[0,127],'rotation':[0,127]},kaoss_neutral={'x':127,'y':0,'rotation':0},
        kaoss_bus={'port':'ATMO FX','rate_hz':25,'return_s':.6})
    return config,meta


class MidiFXOutput:
    def __init__(self,app):self.app=app;self.ports={};self.blocked=set();self.error=''
    def main_name(self):
        main=getattr(self.app,'midi',None)
        name=getattr(main,'name',None)
        if isinstance(name,str):return name
        name=getattr(self.app,'midi_port_name',None)
        if isinstance(name,str):return name
        choice=getattr(self.app,'midi_choice',None)
        return choice.get() if hasattr(choice,'get') else None

    def release_port(self,port):
        """Release only our own handle; the main connection is never owned here."""
        target=self.ports.pop(port,None)
        if target is not None:
            try:target.close()
            except Exception:pass
        self.blocked.discard(port)

    def send(self,port,channel,cc,value):
        try:
            import mido
            message=mido.Message('control_change',channel=channel-1,control=cc,value=value)
            main=getattr(self.app,'midi',None)
            shared=main is not None and getattr(main,'closed',False) is not True and (not port or self.main_name()==port)
            if shared:
                if port:self.release_port(port)
                target=main
            elif not port:
                raise ValueError('Connecta la sortida MIDI principal o tria un port loopMIDI')
            else:
                if port in self.blocked:return False
                target=self.ports.get(port)
                if target is None:
                    if port not in mido.get_output_names():raise ValueError(f'No es troba el port «{port}». Comprova el nom a loopMIDI i reconnecta la sortida XY.')
                    target=self.ports[port]=mido.open_output(port)
            target.send(message)
            self.error=''
            if not shared and hasattr(self.app,'record_midi_send'):self.app.record_midi_send(port,message,None)
            return True
        except Exception as exc:
            self.error=f'Port «{port or "principal"}»: {exc}. A Cakewalk, habilita aquest port només com a entrada de control; comprova que cap altra aplicació n’ocupi la sortida.'
            if port:
                self.blocked.add(port)
                target=self.ports.pop(port,None)
                if target is not None:
                    try:target.close()
                    except Exception:pass
            return False
    def reconnect(self):self.close();self.blocked.clear();self.error=''
    def close(self):
        for port in self.ports.values():
            try:port.close()
            except Exception:pass
        self.ports.clear()


@dataclass
class State:
    seen: float
    filtered: tuple
    updated: float
    sent_at: float=float('-inf')
    values: dict=None
    release_at: float|None=None
    start: dict=None
    def __post_init__(self):self.values={} if self.values is None else self.values


class BusXY:
    def __init__(self,send):self.send=send;self.cards={};self.states={};self.error='';self.last_time=None
    @staticmethod
    def validate(cards,rules):
        occupied={}
        for index,card in enumerate(cards):
            data=settings(card)
            if data is None:continue
            config=card['kaoss'];channel=config['channel']
            for axis in axes(card):
                cc=config[axis+'_cc'];route=(data['port'],channel,cc)
                if route in occupied:raise ValueError('Dues targetes XY comparteixen port, canal i CC')
                occupied[route]=index
                for other_id,other in enumerate(cards):
                    if other_id==index:continue
                    if other.get('channel',1)==channel and other.get('function') in ('Control MIDI CC','Control d’àudio / Mute') and other.get('cc')==cc:
                        raise ValueError('El CC XY coincideix amb una altra targeta. Tria un canal o CC lliure.')
                    other_config=other.get('kaoss',{})
                    if other.get('function')=='Chaos Oscillator (Kaoss XY)' and not other.get('kaoss_bus') and other_config.get('channel')==channel:
                        controls={other_config.get('y_cc')}
                        if other_config.get('mode')=='Efectes':controls.add(other_config.get('x_cc'))
                        if other_config.get('rotation_enabled',True):controls.add(other_config.get('rotation_cc'))
                        if cc in controls:raise ValueError('El CC XY coincideix amb un altre control Kaoss')
                if any(a.kind=='cc' and a.channel==channel and a.number==cc for r in rules.rules if r.enabled for a in r.actions):
                    raise ValueError('El CC XY coincideix amb una regla del projecte')
        return {i:deepcopy(c) for i,c in enumerate(cards) if settings(c) is not None}
    def configure(self,cards):self.cards=cards
    def _time(self,now):
        if not isfinite(now) or self.last_time is not None and now<self.last_time:raise ValueError('Rellotge XY no vàlid')
        self.last_time=now
    def observe(self,index,x,y,rotation,now):
        self._time(now);card=self.cards[index];config=card['kaoss']
        if not all(isfinite(v) and 0<=v<=1 for v in (x,y,rotation)):return
        target=tuple(1-v if config.get('invert_'+a,False) else v for a,v in zip(('x','y','rotation'),(x,y,rotation)))
        state=self.states.get(index)
        if state is None:state=self.states[index]=State(now,target,now)
        else:
            smooth=config.get('smoothing_s',.08);alpha=1 if smooth==0 else 1-exp(-(now-state.updated)/smooth)
            state.filtered=tuple(old if abs(new-old)<=config.get('deadzone',.015) else old+alpha*(new-old) for old,new in zip(state.filtered,target))
            state.seen=now;state.updated=now;state.release_at=None
    def _send(self,index,axis,value):
        card=self.cards[index];data=settings(card);config=card['kaoss']
        accepted=self.send(data['port'],config['channel'],config[axis+'_cc'],value) is not False
        if not accepted:self.error='No s’ha pogut enviar el control XY; no es reenviaran ordres antigues.'
        return accepted
    def release(self,index,now,force=False):
        state=self.states.get(index)
        if state is None:return
        card=self.cards[index]
        if not force and card.get('kaoss_release')=='hold':state.release_at=float('inf');return
        if state.release_at is None or force:
            state.release_at=now;state.start=dict(state.values)
    def tick(self,now):
        self._time(now)
        for index,state in list(self.states.items()):
            card=self.cards[index];config=card['kaoss'];data=settings(card)
            if now-state.seen>=config.get('lost_timeout_s',.25) and state.release_at is None:self.release(index,now)
            if state.release_at==float('inf'):continue
            if now-state.sent_at+1e-9<1/data['rate_hz']:continue
            finished=False
            if state.release_at is not None:
                progress=1 if not data['return_s'] else min(1,(now-state.release_at)/data['return_s'])
                values={a:round(state.start.get(a,card['kaoss_neutral'][a])+(card['kaoss_neutral'][a]-state.start.get(a,card['kaoss_neutral'][a]))*progress) for a in axes(card)}
                finished=progress>=1
            else:
                values={a:round(card['kaoss_ranges'][a][0]+(card['kaoss_ranges'][a][1]-card['kaoss_ranges'][a][0])*state.filtered[n]) for n,a in enumerate(('x','y','rotation')) if a in axes(card)}
            failed=False
            for axis,value in values.items():
                if state.values.get(axis)!=value:
                    if not self._send(index,axis,value):failed=True;break
                    state.values[axis]=value
            state.sent_at=now
            if failed or finished:self.states.pop(index,None)
    def test(self,index,axis,value):
        if axis not in axes(self.cards[index]) or type(value) is not int or not 0<=value<=127:raise ValueError('Prova XY no vàlida')
        # Manual values remain owned so panic/close restores exactly these axes.
        accepted=self._send(index,axis,value)
        if accepted:
            state=self.states.setdefault(index,State(0,(.5,.5,0),0))
            state.values[axis]=value;state.release_at=float('inf')
        return accepted
    def stop(self):
        accepted=True
        for index,state in list(self.states.items()):
            for axis in state.values:
                accepted=self._send(index,axis,self.cards[index]['kaoss_neutral'][axis]) and accepted
        self.states.clear()
        return accepted
