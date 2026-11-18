"""Spatial music geometry and configurable arpeggio note pools, no GUI or MIDI."""
import math
import random
import re

NOTE_NAMES=('Do','Do#','Re','Re#','Mi','Fa','Fa#','Sol','Sol#','La','La#','Si')
DIRECTIONS=('Ascendent','Descendent','Pujada i baixada','Baixada i pujada','Aleatori','Ordre triat')
ARP_MAPS={'Sectors i anells':'radial','Quadrícula 8 × 3':'grid'}
ARP_SOURCES=('Acord','Escala','Notes triades')


def note_label(note):
    return f'{NOTE_NAMES[note%12]}{note//12-1}'


def music_zone(card,x,y):
    if card.get('function')=='Arpegiador espacial' and card.get('arp_map','radial')=='grid':
        return min(7,max(0,int(x*8))),min(2,max(0,int(y*3)))
    angle=(math.atan2(.5-y,x-.5)+math.tau)%math.tau
    sector=int((angle+math.pi/8)//(math.pi/4))%8
    radius=min(1,math.hypot(x-.5,y-.5)*2)
    return sector,0 if radius<1/3 else (1 if radius<2/3 else 2)


def parse_notes(value):
    if isinstance(value,str):
        try:value=[int(token) for token in re.split(r'[\s,;]+',value.strip()) if token]
        except ValueError as exc:raise ValueError('Escriu notes MIDI entre 0 i 127, separades per espais o comes.') from exc
    if not isinstance(value,(list,tuple)) or not 1<=len(value)<=32 or any(type(n) is not int or not 0<=n<=127 for n in value):
        raise ValueError('Cal triar entre 1 i 32 notes MIDI (0–127).')
    return list(value)


def arp_settings(card):
    count=card.get('arp_note_count',0)
    octaves=card.get('arp_octaves',2)
    source=card.get('arp_source','Acord')
    layout=card.get('arp_map','radial')
    direction=card.get('arp_direction','Ascendent')
    if type(count) is not int or not 0<=count<=32:raise ValueError('Nombre de notes: 1–32 o Auto.')
    if type(octaves) is not int or not 1<=octaves<=6:raise ValueError('Octaves: 1–6.')
    if source not in ARP_SOURCES or layout not in ARP_MAPS.values() or direction not in DIRECTIONS:
        raise ValueError('Configuració d’arpegiador no vàlida.')
    notes=parse_notes(card.get('arp_notes',[60,64,67,72,76]))
    return dict(arp_note_count=count,arp_octaves=octaves,arp_source=source,arp_map=layout,
                arp_direction=direction,arp_notes=notes)


def arp_pitches(card,sector,ring,chord,scales):
    settings=arp_settings(card)
    count=settings['arp_note_count']
    if not count:
        return list(chord[:2]) if ring==2 else (list(chord) if ring==1 else list(chord)+[min(127,chord[0]+12)])
    source=settings['arp_source']
    if source=='Notes triades':base=settings['arp_notes']
    elif source=='Escala':
        intervals=scales[card.get('harmony_scale','Menor natural (eòlica)')]
        root=48+int(card.get('harmony_root',9))%12
        start=sector%len(intervals)
        base=[root+intervals[i%len(intervals)]+12*(i//len(intervals)) for i in range(start,start+len(intervals))]
    else:base=list(chord)
    pool=[]
    for octave in range(settings['arp_octaves']):
        for note in base:
            value=max(0,min(127,note+octave*12+(1-ring)*12))
            if 0<=value<=127 and value not in pool:pool.append(value)
    if source!='Notes triades':pool.sort()
    if count>len(pool):raise ValueError(f'Aquest rang permet {len(pool)} notes diferents. Redueix el nombre o amplia les octaves / notes triades.')
    return pool[:count]


def sequence_notes(pitches,direction):
    notes=list(pitches) if direction=='Ordre triat' else sorted(pitches)
    if direction in ('Descendent','Baixada i pujada'):notes.reverse()
    if direction in ('Pujada i baixada','Baixada i pujada') and len(notes)>1:notes=notes+notes[-2:0:-1]
    return notes


def arpeggio_note(pitches,index,direction):
    if not pitches:return None
    if direction=='Aleatori':return random.choice(pitches)
    sequence=sequence_notes(pitches,direction)
    return sequence[index%len(sequence)]
