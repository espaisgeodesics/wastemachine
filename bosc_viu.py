"""Self-contained BOSC VIU prototype with deterministic synthetic test sounds."""
import copy
import json
import math
from pathlib import Path
import random
import struct
import wave

from experience_rules import ExperienceRule, RuleAction, RulesConfig
from participants import ParticipantBinding, ParticipantRegistry
from spatial_zones import Grid, SpatialMap, Zone


def _sound(path,kind,seconds):
    rate=22050;rng=random.Random(kind);slow=0.;samples=bytearray()
    count=round(rate*seconds)
    for i in range(count):
        t=i/rate;noise=rng.uniform(-1,1);slow=.985*slow+.015*noise
        envelope=min(1.,i/(rate*.04),(count-i)/(rate*.08))
        if kind=='vent':value=slow*(1+.4*math.sin(t*1.7))*1.8
        elif kind=='riu':value=.1*noise+.35*slow+.025*math.sin(t*231)
        elif kind=='fulles':value=noise*.12*(max(0,math.sin(t*6.1))**8)
        elif kind=='ocells':
            phase=t%0.32;chirp=math.sin(math.tau*(1300*t+850*phase*phase))
            value=.18*chirp*max(0,math.sin(phase/.32*math.pi))**4
        else:value=.12*(math.sin(t*math.tau*440)+.5*math.sin(t*math.tau*660))*math.exp(-t*2)
        samples.extend(struct.pack('<h',round(max(-.9,min(.9,value*envelope))*32767)))
    with wave.open(str(path),'wb') as output:
        output.setparams((1,2,rate,0,'NONE','not compressed'));output.writeframes(samples)


def create_bosc_viu(destination,cards_template):
    cards=copy.deepcopy(cards_template)
    if len(cards)!=16:raise ValueError('Calen 16 targetes base')
    for card in cards:card['function']='Cap acció'
    destination=Path(destination)
    # A new directory is required: never overwrite a user's existing experience.
    destination.mkdir(parents=True,exist_ok=False)
    sounds=destination/'sons';sounds.mkdir()
    for kind,seconds in (('ocells',1.2),('riu',3.),('vent',3.),('fulles',3.),('alarma',1.2)):
        _sound(sounds/(kind+'.wav'),kind,seconds)
    grid=Grid();authorized=frozenset(range(5))
    zones=[]
    for zid,name,rows,columns in (('ocells','OCELLS',range(1,3),range(1,4)),('riu','RIU',range(2,5),range(5,7)),
                                 ('vent','VENT',range(5,7),range(1,4)),('clariana','CLARIANA',range(5,7),range(5,7)),
                                 ('alarma','ALARMA',range(3,5),range(3,5))):
        cells={(r,c) for r in rows for c in columns if grid.eligible((r,c))}
        zones.append(Zone(zid,name,cells,authorized))
    rules=[]
    def add(rid,name,trigger,actions,zone='',group='bosc',priority=10):
        rules.append(ExperienceRule(rid,name,trigger,tuple(actions),priority,group,zone_id=zone,reason='any'))
    def play(name,gain=.5,loop=False,fade=.2,group=''):
        return RuleAction('play_sound',f'sons/{name}.wav',gain=gain,loop=loop,fade_s=fade,audio_group=group)
    add('ambient','INICIAR AMBIENT','manual',(play('vent',.4,True,.6,'vent'),play('fulles',.35,True,.6,'fulles')))
    add('ocells-enter','Cant d’ocells','zone_entered',(play('ocells',.65),),'ocells','ocells')
    for zid in ('riu','vent'):
        add(zid+'-enter',zid.upper()+' augment gradual','zone_entered',
            (play(zid,.15,True,.1),RuleAction('audio_volume',gain=.7,fade_s=.8)),zid,zid)
        add(zid+'-exit',zid.upper()+' retirada','zone_exited',(RuleAction('stop_sound',fade_s=.5),),zid,zid)
    add('clariana-enter','Clariana verda','zone_entered',(RuleAction('color','#5C9954',duration_s=0),),'clariana','paisatge')
    add('alarma-enter','Alarma i ocells silenciosos','zone_entered',
        (RuleAction('stop_sound',audio_group='ocells',audio_scope='group',fade_s=.15),
         RuleAction('audio_volume',audio_group='ocells',audio_scope='group',gain=0,fade_s=.15),
         RuleAction('audio_volume',audio_group='vent',audio_scope='group',gain=.15,fade_s=.5),
         play('alarma',.5),RuleAction('color','#A52A24',duration_s=2)), 'alarma','alarma',100)
    add('restore','RECUPERAR BOSC','manual',
        (RuleAction('stop_sound',audio_group='alarma',audio_scope='group',fade_s=.2),
         RuleAction('audio_volume',audio_group='ocells',audio_scope='group',gain=1,fade_s=.5),
         RuleAction('audio_volume',audio_group='vent',audio_scope='group',gain=1,fade_s=.5),
         RuleAction('release_visual')),group='alarma')
    registry=ParticipantRegistry(ParticipantBinding(f'bosc-{i+1}',f'Participant {i+1}',
        ('#48B8E8','#F7A541','#91CF60','#E574C7','#B19CFF')[i],'camera:0',i) for i in range(5))
    project={'version':4,'cards':cards,'master_volume':127,'bpm':120,'visual':0,'quantize_harmony':True,
             'participants':registry.to_dict(),'experience_rules':RulesConfig(tuple(rules)).to_dict()}
    project=SpatialMap(zones=tuple(zones)).into_project(project)  # no physical calibration is fabricated
    path=destination/'BOSC_VIU_PROVA.json'
    path.write_text(json.dumps(project,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    (destination/'LLEGEIX-ME.txt').write_text(
        'BOSC VIU DE PROVA\nSons sintètics generats; no són gravacions de natura.\n'
        'Obre el projecte, el simulador i carrega zones i regles. Prova OCELLS, RIU, VENT, CLARIANA i ALARMA.\n'
        'INICIAR AMBIENT i RECUPERAR BOSC són regles manuals.\n'
        'La sortida virtual no fa so. Per escoltar, instal·la el complement opcional i activa Àudio local.\n'
        'No hi ha calibració física; no substitueix les proves Windows, càmera o altaveus.\n',encoding='utf-8')
    return path
