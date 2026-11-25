"""Reproducible five-part adaptation of Mutopia 301; no playback or network access."""
from pathlib import Path
from collections import Counter
import argparse,copy,json,math,hashlib
import mido

PARTS=[('01_Violi_solista',40,93),('02_Flauta',73,78),('03_Oboe',68,73),('04_Viola',41,80),('05_Violoncel',42,88)]
BPM=115
TEMPO=mido.bpm2tempo(BPM)
CREDIT='Vivaldi RV269 I Allegro; Mutopia-2010/02/08-301, Anonymous (smailliw); CC BY-SA 3.0. ATMO: timbres, canals i balanc adaptats.'


def events(track):
    now=0
    for msg in track:
        now+=msg.time
        yield now,msg


def note_list(track):
    return [(t,m.type,m.note,m.velocity if m.type=='note_on' else 0) for t,m in events(track) if m.type in ('note_on','note_off')]


def generate(destination):
    out=Path(destination);out.mkdir(parents=True,exist_ok=True)
    (out/'MIDI'/'PISTES_SEPARADES').mkdir(parents=True,exist_ok=True)
    src=mido.MidiFile(Path(__file__).with_name('FONT_MUTOPIA.mid'))
    assert len(src.tracks)==6 and [sum(m.type=='note_on' and m.velocity>0 for m in t) for t in src.tracks[1:]]==[820,705,697,450,501]
    result=mido.MidiFile(type=1,ticks_per_beat=src.ticks_per_beat)
    for index,(source,(name,program,volume)) in enumerate(zip(src.tracks[1:],PARTS)):
        track=mido.MidiTrack();result.tracks.append(track)
        track.append(mido.MetaMessage('track_name',name=name))
        if index==0:
            track.extend([mido.MetaMessage('copyright',text=CREDIT),mido.MetaMessage('set_tempo',tempo=TEMPO),mido.MetaMessage('time_signature',numerator=4,denominator=4)])
        track.extend([mido.Message('program_change',channel=index,program=program),mido.Message('control_change',channel=index,control=7,value=volume),mido.Message('control_change',channel=index,control=10,value=64)])
        for msg in source:
            if msg.type in ('track_name','program_change'):continue
            track.append(msg.copy(channel=index) if not msg.is_meta else msg.copy())
        assert note_list(track)==note_list(source)
        single=mido.MidiFile(type=1,ticks_per_beat=result.ticks_per_beat)
        single.tracks.append(mido.MidiTrack([mido.MetaMessage('set_tempo',tempo=TEMPO),mido.MetaMessage('time_signature',numerator=4,denominator=4)] + [m.copy() for m in track]))
        single.save(out/'MIDI'/'PISTES_SEPARADES'/f'{name}.mid')
    result.save(out/'MIDI'/'PRIMAVERA_5_PISTES.mid')
    create_intro(out/'MIDI'/'INTRO_DEMOSTRACIO_6_I_7.mid')
    cards=[]
    for i in range(16):
        c=dict(name=f'Targeta {i+1:02d}',function='Cap acció',channel=i+1,note=52,cc=119,visual=13,axis='Rotació',min=0,max=127,harmony_key='Mi major',harmony_root=4,harmony_scale='Major (jònica)',harmony_velocity=72,arp_division='1/2 temps',arp_gate=65,arp_note_count=4,arp_octaves=1,arp_source='Notes triades',arp_notes=[64,68,71,76],arp_map='grid',arp_direction='Pujada i baixada')
        if i<5:c.update(name=PARTS[i][0][3:].replace('_',' '),function='Control d’àudio / Mute',mute_audible=0,mute_silent=127)
        if i==5:c.update(name='Alba · ambient Mi',function='Nota MIDI',note=52,harmony_velocity=58)
        if i==6:c.update(name='Brots · arpegi Mi major',function='Arpegiador espacial',harmony_velocity=58)
        cards.append(c)
    data=dict(version=4,cards=cards,bpm=BPM,quantize_harmony=True,visual=13,preview_surface='circle',master_volume=110)
    (out/'PRIMAVERA_ATMO.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    report=validate(out,src)
    (out/'INFORME_VALIDACIO.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return report


def create_intro(path):
    mid=mido.MidiFile(type=1,ticks_per_beat=480)
    ambient=mido.MidiTrack([mido.MetaMessage('track_name',name='06_Alba_ambient_Mi'),mido.MetaMessage('set_tempo',tempo=TEMPO),mido.MetaMessage('key_signature',key='E'),mido.Message('program_change',channel=5,program=89),mido.Message('control_change',channel=5,control=7,value=60),mido.Message('control_change',channel=5,control=10,value=64),mido.Message('note_on',channel=5,note=52,velocity=55),mido.Message('note_off',channel=5,note=52,velocity=0,time=480*32),mido.MetaMessage('end_of_track')])
    arp=mido.MidiTrack([mido.MetaMessage('track_name',name='07_Brots_arpegi_Mi_major'),mido.Message('program_change',channel=6,program=10),mido.Message('control_change',channel=6,control=7,value=68),mido.Message('control_change',channel=6,control=10,value=64)])
    sequence=[64,68,71,76,71,68]
    arp.append(mido.MetaMessage('text',text='Demostracio fixa de 8 compassos; ATMO en directe te rellotge propi.',time=480*4))
    for i in range(56):
        n=sequence[i%len(sequence)]
        arp.extend([mido.Message('note_on',channel=6,note=n,velocity=58,time=0 if i==0 else 84),mido.Message('note_off',channel=6,note=n,velocity=0,time=156)])
    arp.append(mido.MetaMessage('end_of_track',time=84))
    mid.tracks.extend([ambient,arp]);mid.save(path)


def validate(out,src=None):
    mid=mido.MidiFile(out/'MIDI'/'PRIMAVERA_5_PISTES.mid');assert mid.type==1 and len(mid.tracks)==5
    notes=[]
    for i,t in enumerate(mid.tracks):
        active=Counter();count=0
        for msg in t:
            assert msg.time>=0
            if not msg.is_meta:assert msg.channel==i
            if msg.type=='note_on' and msg.velocity:active[msg.note]+=1;count+=1
            elif msg.type in ('note_on','note_off'):
                active[msg.note]-=1;assert active[msg.note]>=0
        assert not any(active.values());notes.append(count)
        if src:assert note_list(t)==note_list(src.tracks[i+1])
        assert len({m.program for m in t if m.type=='program_change'})==1
        assert all(m.value==64 for m in t if m.type=='control_change' and m.control==10)
    assert len({m.program for t in mid.tracks for m in t if m.type=='program_change'})==5
    cards=json.loads((out/'PRIMAVERA_ATMO.json').read_text(encoding='utf-8'))['cards']
    assert len(cards)==16 and [c['channel'] for c in cards[:7]]==list(range(1,8))
    for c in cards[:5]:assert c['function']=='Control d’àudio / Mute' and c['cc']==119 and c['mute_audible']==0 and c['mute_silent']==127
    return dict(midi_type=1,musical_tracks=5,channels=[1,2,3,4,5],programs_zero_based=[p[1] for p in PARTS],tempo_bpm=BPM,key='Mi major / E major',duration_seconds=round(mid.length,3),notes_per_track=notes,source_notes_and_timing_preserved=True,notes_balanced=True,all_pans_centered=True,atmo_cards=7,cakewalk_project_created=False,physical_midi_and_camera_tested=False,limitations=['Els instruments VST i les assignacions Mute es configuren i es desen a Cakewalk.','L’arpegi d’ATMO no segueix el transport de Cakewalk.','La tonalitat global no garanteix consonància dels afegits durant totes les modulacions.'])


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('destination',type=Path);args=parser.parse_args()
    print(json.dumps(generate(args.destination),ensure_ascii=False,indent=2))
