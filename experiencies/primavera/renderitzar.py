"""Offline MIDI preview with system FluidSynth + TimGM6mb. Never opens an audio device."""
import ctypes as C
import ctypes.util
from pathlib import Path
import argparse,subprocess,wave
import mido


def render(midi,output,soundfont):
    lib=C.CDLL(ctypes.util.find_library('fluidsynth'))
    def bind(name,restype,*argtypes):
        fn=getattr(lib,name);fn.restype=restype;fn.argtypes=list(argtypes);return fn
    ptr=C.c_void_p;I=C.c_int;S=C.c_char_p
    new_settings=bind('new_fluid_settings',ptr)
    setting_num=bind('fluid_settings_setnum',I,ptr,S,C.c_double)
    setting_int=bind('fluid_settings_setint',I,ptr,S,I)
    new_synth=bind('new_fluid_synth',ptr,ptr)
    load=bind('fluid_synth_sfload',I,ptr,S,I)
    note_on=bind('fluid_synth_noteon',I,ptr,I,I,I)
    note_off=bind('fluid_synth_noteoff',I,ptr,I,I)
    cc=bind('fluid_synth_cc',I,ptr,I,I,I)
    program=bind('fluid_synth_program_change',I,ptr,I,I)
    write=bind('fluid_synth_write_s16',I,ptr,I,ptr,I,I,ptr,I,I)
    delete=bind('delete_fluid_synth',None,ptr);delete_settings=bind('delete_fluid_settings',None,ptr)
    settings=new_settings();setting_num(settings,b'synth.sample-rate',44100.);setting_num(settings,b'synth.gain',.35)
    setting_int(settings,b'synth.reverb.active',0);setting_int(settings,b'synth.chorus.active',0)
    synth=new_synth(settings)
    if load(synth,str(soundfont).encode(),1)<0:raise RuntimeError('No es pot carregar el SoundFont')
    buffer=(C.c_short*(4096*2))();wav=Path(output).with_suffix('.wav')
    with wave.open(str(wav),'wb') as audio:
        audio.setparams((2,2,44100,0,'NONE','not compressed'))
        actual=0;elapsed=0.
        def samples(n):
            while n:
                amount=min(n,4096)
                if write(synth,amount,buffer,0,2,buffer,1,2)<0:raise RuntimeError('Render fallit')
                audio.writeframesraw(C.string_at(buffer,amount*4));n-=amount
        for msg in mido.MidiFile(midi):
            elapsed+=msg.time;target=round(elapsed*44100);samples(target-actual);actual=target
            if msg.type=='note_on':note_on(synth,msg.channel,msg.note,msg.velocity) if msg.velocity else note_off(synth,msg.channel,msg.note)
            elif msg.type=='note_off':note_off(synth,msg.channel,msg.note)
            elif msg.type=='program_change':program(synth,msg.channel,msg.program)
            elif msg.type=='control_change':cc(synth,msg.channel,msg.control,msg.value)
        for ch in range(16):cc(synth,ch,123,0)
        samples(44100*3)
    delete(synth);delete_settings(settings)
    subprocess.run(['ffmpeg','-v','error','-y','-i',str(wav),'-af','loudnorm=I=-18:TP=-2:LRA=9','-ar','44100','-codec:a','libmp3lame','-b:a','192k',str(output)],check=True)
    wav.unlink()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('folder',type=Path);parser.add_argument('--soundfont',type=Path,default=Path('/usr/share/sounds/sf2/TimGM6mb.sf2'));a=parser.parse_args()
    render(a.folder/'MIDI'/'PRIMAVERA_5_PISTES.mid',a.folder/'ESCOLTAR_PRIMAVERA.mp3',a.soundfont)
    render(a.folder/'MIDI'/'INTRO_DEMOSTRACIO_6_I_7.mid',a.folder/'ESCOLTAR_INTRO.mp3',a.soundfont)
    print('Previsualitzacions renderitzades sense dispositiu d’àudio.')
