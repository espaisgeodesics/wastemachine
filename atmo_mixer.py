"""Volume routing shared by the MIDI mixer, live velocities and local layers."""
from copy import deepcopy
import math

MIDI_SOUND={'Nota MIDI','Harmonia espacial','Arpegiador espacial','Patró rítmic','Ritme de bateria','Àudio'}
CHAOS='Chaos Oscillator (Kaoss XY)'


def sound_kind(cards,index,spatial_map=None):
    card=cards[index];function=card.get('function')
    if function in MIDI_SOUND:return 'midi'
    if function==CHAOS and card.get('kaoss',{}).get('mode','Instrument')=='Instrument':return 'midi'
    if function=='Activar zona espacial' and spatial_map is not None and any(
        zone.enabled and zone.audio_path and index in zone.authorized_cards for zone in spatial_map.zones):return 'local'
    return 'none'


def mixer_config(card):
    data=dict(channel=card.get('channel',1),cc=7,level=127)
    data.update(card.get('mixer',{}))
    if type(data['channel']) is not int or not 1<=data['channel']<=16:raise ValueError('Canal de volum: 1–16.')
    if type(data['cc']) is not int or not 0<=data['cc']<=127:raise ValueError('CC de volum: 0–127.')
    level=float(data['level'])
    if not math.isfinite(level) or not 0<=level<=127:raise ValueError('Volum: 0–127.')
    return dict(channel=data['channel'],cc=data['cc'],level=level)


def shared_route(cards,index):
    route=mixer_config(cards[index]);key=(route['channel'],route['cc'])
    return sum(sound_kind(cards,i)=='midi' and
               (mixer_config(card)['channel'],mixer_config(card)['cc'])==key for i,card in enumerate(cards))>1


def midi_level(cards,index,master):
    config=mixer_config(cards[index])
    # Standard CC7 is channel-wide. On a shared channel, master is global and
    # independent card levels apply to subsequent note velocities, not each other.
    level=127 if config['cc']==7 and shared_route(cards,index) else config['level']
    return max(0,min(127,round(level*float(master)/127)))


def note_velocity(cards,index,velocity):
    config=mixer_config(cards[index])
    if config['cc']==7 and shared_route(cards,index):
        return max(0,min(127,round(velocity*config['level']/127)))
    return max(0,min(127,int(velocity)))


def independent_channels(cards,rules):
    result=deepcopy(cards)
    reserved={action.channel for rule in rules.rules if rule.enabled for action in rule.actions if action.kind in ('note','cc')}
    used=set(reserved)
    controls={c.get('channel',1) for c in cards if c.get('function') in ('Control MIDI CC','Control d’àudio / Mute')}
    for i,card in enumerate(result):
        if sound_kind(result,i)!='midi':continue
        blocked=used | (controls if card.get('function')==CHAOS else set())
        preferred=card.get('channel',1)
        channel=preferred if preferred not in blocked else next((n for n in range(1,17) if n not in blocked),None)
        if channel is None:raise ValueError('No queden canals MIDI lliures per separar totes les targetes sonores.')
        used.add(channel);card['channel']=channel
        config=mixer_config(card);config.update(channel=channel,cc=7);card['mixer']=config
        if card.get('function')==CHAOS and isinstance(card.get('kaoss'),dict):card['kaoss']['channel']=channel
    rules.validate_channels(result)
    return result
