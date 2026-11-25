"""Presence-controlled track fades. Pure MIDI envelopes; no notes or DAW transport.

Keep the existing binary Mute route. A separate, explicitly mapped CC controls
level: zero before unmute, smooth ramp, zero before mute. Legacy cards are opt-in.
"""
from dataclasses import dataclass
from math import isfinite

FUNCTION='Control d’àudio / Mute'
DEFAULTS=dict(enabled=False,cc=118,in_s=1.5,out_s=2.0,level=100)
RESERVED={0,6,7,11,32,38,64,66,67,69,96,97,98,99,100,101}


def settings(card):
    data=card.get('mute_fade',{})
    if not isinstance(data,dict) or set(data)-set(DEFAULTS):raise ValueError('Configuració de fade no vàlida')
    result=dict(DEFAULTS,**data)
    if type(result['enabled']) is not bool:raise ValueError('Fade activat: valor no vàlid')
    if type(result['cc']) is not int or not 1<=result['cc']<=119 or result['cc'] in RESERVED:
        raise ValueError('CC de fade: tria un control lliure entre 1 i 119 (recomanat: 118), sense bancs, volum MIDI ni pedals.')
    if type(result['level']) is not int or not 1<=result['level']<=127:raise ValueError('Nivell màxim del fade: 1–127')
    for key in ('in_s','out_s'):
        value=result[key]
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not isfinite(value) or not 0<=value<=60:
            raise ValueError('Temps de fade: 0–60 segons, sense valors infinits')
    if result['enabled'] and result['cc']==card.get('cc',119):raise ValueError('El CC de fade ha de ser diferent del CC de Mute')
    return result


def validate(cards,rules=None):
    """Validate separate fade routes against other mapped card/rule controllers."""
    fades={}
    for index,card in enumerate(cards):
        if card.get('function')!=FUNCTION:continue
        data=settings(card)
        if not data['enabled']:continue
        channel=card.get('channel',1)
        if type(channel) is not int or not 1<=channel<=16:raise ValueError('Canal de fade: 1–16')
        gate=card.get('cc',119)
        if type(gate) is not int or not 0<=gate<=119:raise ValueError('CC de Mute: 0–119')
        audible,silent=card.get('mute_audible',0),card.get('mute_silent',127)
        if any(type(v) is not int or not 0<=v<=127 for v in (audible,silent)) or audible==silent:
            raise ValueError('Mute: dos valors diferents entre 0 i 127')
        route=(channel,data['cc'])
        if route in fades:raise ValueError('Dues targetes comparteixen canal i CC de fade. Tria un canal o CC diferent.')
        fades[route]=index
        for other_index,other in enumerate(cards):
            other_channel=other.get('channel',1)
            function=other.get('function')
            controls=set()
            if function==FUNCTION and other_index!=index and other_channel==channel and other.get('cc')==gate:
                raise ValueError('Dues targetes comparteixen la ruta de Mute d’un fade. Tria canals o CC diferents.')
            if other_channel==channel:
                if function in (FUNCTION,'Control MIDI CC'):controls.add(other.get('cc'))
                if function=='Control MIDI CC' and other_index==1 and other.get('cc')==7:controls.add(74)
                if function=='Àudio':controls.update(c.get('cc') for c in other.get('audio_controls',{}).values() if c.get('enabled'))
            if function=='Chaos Oscillator (Kaoss XY)':
                cfg=other.get('kaoss',{})
                if cfg.get('channel',other_channel)==channel:
                    controls.add(cfg.get('y_cc'))
                    if cfg.get('mode')=='Efectes':controls.add(cfg.get('x_cc'))
                    if cfg.get('rotation_enabled',True):controls.add(cfg.get('rotation_cc'))
            if function in ('Nota MIDI','Harmonia espacial','Arpegiador espacial','Àudio','Patró rítmic','Ritme de bateria'):
                mixer=other.get('mixer',{})
                if mixer.get('channel',other_channel)==channel:controls.add(mixer.get('cc',7))
            if data['cc'] in controls:
                raise ValueError(f'El CC de fade coincideix amb un control de la targeta {other_index+1:02d}. Tria un canal o CC lliure.')
        if rules is not None:
            for rule in rules.rules:
                if rule.enabled and any(a.kind=='cc' and a.channel==channel and a.number in (data['cc'],gate) for a in rule.actions):
                    raise ValueError('El CC de fade coincideix amb una regla del projecte')
    return fades


@dataclass(frozen=True)
class Route:
    channel:int
    gate:int
    audible:int
    silent:int
    cc:int
    in_s:float
    out_s:float
    level:int

    @classmethod
    def from_card(cls,card):
        data=settings(card)
        return cls(card['channel'],card['cc'],card.get('mute_audible',0),card.get('mute_silent',127),data['cc'],data['in_s'],data['out_s'],data['level'])


@dataclass
class Envelope:
    route:Route
    present:bool=False
    start:float=0.
    target:float=0.
    since:float=0.
    duration:float=0.
    level_sent:int|None=None
    gate_sent:int|None=None
    sent_at:float=float('-inf')
    retry_at:float=float('-inf')

    def value(self,now):
        progress=1. if self.duration==0 else max(0.,min(1.,(now-self.since)/self.duration))
        smooth=progress*progress*(3-2*progress)
        return self.start+(self.target-self.start)*smooth


class PresenceFades:
    def __init__(self,send):
        self.send=send;self.states={};self.error=''

    def clear(self):
        """Only after silencing/disconnecting: never replay envelopes on a new port."""
        self.states.clear();self.error=''

    def forget(self,index):self.states.pop(index,None)

    def _send(self,state,cc,value):
        try:
            if self.send(state.route.channel,cc,value) is False:raise RuntimeError('El port MIDI no ha acceptat el control')
            return True
        except Exception as exc:
            self.error=f'No s’ha pogut enviar el fade: {exc}'
            return False

    def request(self,index,card,present,now,immediate=False):
        if not isfinite(now):raise ValueError('Rellotge de fade no vàlid')
        route=Route.from_card(card)
        state=self.states.get(index)
        if state is not None and state.route!=route:
            if not self.stop(index,now):return False
            self.forget(index);state=None
        if state is None:
            state=self.states[index]=Envelope(route,since=now)
        present=bool(present and not immediate)
        if immediate:
            state.present=False;state.start=state.target=0.;state.since=now;state.duration=0.
            state.retry_at=float('-inf')
        elif present!=state.present:
            value=state.value(now)
            state.present=present;state.start=value;state.target=float(route.level if present else 0)
            state.since=now
            seconds=route.in_s if present else route.out_s
            state.duration=seconds*abs(state.target-value)/route.level
        return self._step(state,now,force=immediate)

    def _step(self,state,now,force=False):
        if not force and now<state.retry_at:return False
        r=state.route
        value=round(state.value(now))
        ended=now>=state.since+state.duration
        # Startup/reconnection and re-entry at zero always set gain before unmute.
        if state.level_sent is None:
            if not self._send(state,r.cc,0):state.retry_at=now+.5;return False
            state.level_sent=0
        if state.present and state.gate_sent!=r.audible:
            if not self._send(state,r.gate,r.audible):state.retry_at=now+.5;return False
            state.gate_sent=r.audible
        if (force or ended or now-state.sent_at>=1/30) and state.level_sent!=value:
            if not self._send(state,r.cc,value):state.retry_at=now+.5;return False
            state.level_sent=value;state.sent_at=now
        # Silence only after the receiver accepted the zero level. This is also
        # safe when the send failed on the final frame; the next call retries.
        if not state.present and ended and state.level_sent==0 and state.gate_sent!=r.silent:
            if not self._send(state,r.gate,r.silent):state.retry_at=now+.5;return False
            state.gate_sent=r.silent
        state.retry_at=float('-inf');self.error=''
        return True

    def tick(self,now):
        if not isfinite(now):raise ValueError('Rellotge de fade no vàlid')
        return all([self._step(state,now) for state in self.states.values()])

    def stop(self,index,now):
        state=self.states.get(index)
        if state is None:return True
        state.present=False;state.start=state.target=0.;state.duration=0.;state.since=now;state.retry_at=float('-inf')
        return self._step(state,now,force=True)
