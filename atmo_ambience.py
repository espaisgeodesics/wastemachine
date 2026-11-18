"""Effect-only XY presets and explicit MIDI destinations. No sound generation."""
from copy import deepcopy
from kaoss_xy import KaossConfig

PARAMETERS={'Brillantor / filtre':74,'Resonància':71,'Reverb':91,'Eco / delay (Learn)':12,
            'Chorus':93,'Greus (Learn)':20,'Volum':7,'Personalitzat':None}
TARGETS={'Totes les targetes MIDI amb so':'all','Targetes seleccionades':'selected','Canal MIDI concret':'channel'}
AMBIENCES=('Obert / aire','Cova','Eco','Aguts i greus','Reverb i brillantor')
SOUND_FUNCTIONS={'Nota MIDI','Harmonia espacial','Arpegiador espacial','Patró rítmic','Ritme de bateria','Àudio'}


def neutral_cc(cc):return 127 if cc in (7,74) else (64 if cc==20 else 0)


def ambience_preset(name,channel=1):
    if name not in AMBIENCES:raise ValueError('Ambient no vàlid')
    data={
      'Obert / aire':((74,91,12),((80,127),(0,40),(0,30))),
      'Cova':((74,91,12),((25,90),(35,120),(0,90))),
      'Eco':((74,12,91),((45,127),(0,110),(0,80))),
      'Aguts i greus':((74,20,71),((20,127),(20,108),(0,70))),
      'Reverb i brillantor':((74,91,93),((25,127),(0,110),(0,90))),
    }[name]
    config=KaossConfig(mode='Efectes',channel=channel,x_cc=data[0][0],y_cc=data[0][1],rotation_cc=data[0][2])
    metadata=dict(kaoss_target='all',kaoss_targets=[],kaoss_release='neutral',kaoss_ambience=name,
      kaoss_ranges={axis:list(limits) for axis,limits in zip(('x','y','rotation'),data[1])},
      kaoss_neutral={axis:neutral_cc(cc) for axis,cc in zip(('x','y','rotation'),data[0])})
    return config,metadata


def ambience_settings(card):
    config=card.get('kaoss',{})
    result=dict(kaoss_target=card.get('kaoss_target','all'),kaoss_targets=card.get('kaoss_targets',[]),
      kaoss_release=card.get('kaoss_release','neutral'),kaoss_ambience=card.get('kaoss_ambience','Personalitzat'),
      kaoss_ranges=deepcopy(card.get('kaoss_ranges',{axis:[0,127] for axis in ('x','y','rotation')})),
      kaoss_neutral=deepcopy(card.get('kaoss_neutral',{axis:neutral_cc(config.get(key,cc)) for axis,key,cc in
        (('x','x_cc',74),('y','y_cc',91),('rotation','rotation_cc',12))})))
    if result['kaoss_target'] not in TARGETS.values() or result['kaoss_release'] not in ('neutral','hold'):raise ValueError('Destinació o retirada XY no vàlida')
    ids=result['kaoss_targets']
    if not isinstance(ids,list) or any(type(i) is not int or not 0<=i<=15 for i in ids):raise ValueError('Targetes de destinació XY no vàlides')
    if result['kaoss_target']=='selected' and not ids:raise ValueError('Selecciona almenys una targeta sonora de destinació')
    for axis in ('x','y','rotation'):
        limits=result['kaoss_ranges'].get(axis)
        neutral=result['kaoss_neutral'].get(axis)
        if not isinstance(limits,(tuple,list)) or len(limits)!=2 or any(type(v) is not int for v in limits) or not 0<=limits[0]<=limits[1]<=127:
            raise ValueError('Límits de cada eix XY: 0–127, mínim ≤ màxim')
        if type(neutral) is not int or not 0<=neutral<=127:raise ValueError('Valor neutre XY: 0–127')
    return result


def effect_channels(cards,marker):
    card=cards[marker];settings=ambience_settings(card)
    if settings['kaoss_target']=='channel':return {card['kaoss']['channel']}
    ids=range(len(cards)) if settings['kaoss_target']=='all' else settings['kaoss_targets']
    return {cards[i]['channel'] for i in ids if 0<=i<len(cards) and i!=marker and (cards[i].get('function') in SOUND_FUNCTIONS or
            cards[i].get('function')=='Chaos Oscillator (Kaoss XY)' and cards[i].get('kaoss',{}).get('mode')=='Instrument')}


def mapped_cc(card,cc,value):
    settings=ambience_settings(card);config=card['kaoss']
    axis=next((axis for axis,key in (('x','x_cc'),('y','y_cc'),('rotation','rotation_cc')) if config[key]==cc),None)
    if axis is None:return value,neutral_cc(cc)
    low,high=settings['kaoss_ranges'][axis]
    return round(low+(high-low)*value/127),settings['kaoss_neutral'][axis]


def normalise_ambience_card(card):
    if card.get('function')!='Chaos Oscillator (Kaoss XY)':return
    previous=card.get('kaoss')
    if previous is None or previous.get('mode')!='Efectes':
        if previous is not None:card['kaoss_instrument_legacy']=deepcopy(previous)
        config,settings=ambience_preset('Obert / aire',card.get('channel',1))
        card['kaoss']=config.to_dict();card.update(settings)
    ambience_settings(card)
