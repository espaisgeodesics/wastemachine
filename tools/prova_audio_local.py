"""Reproducible SDL prototype probe. API timings are NOT acoustic latency."""
import argparse
import json
import math
import os
from pathlib import Path
import platform
import struct
from tempfile import TemporaryDirectory
import time
import wave

from local_audio import AudioCommand,AudioEngine,PygameAudioBackend


def probe(dummy=False):
    if dummy:os.environ['SDL_AUDIODRIVER']='dummy'
    began=time.perf_counter();backend=PygameAudioBackend();init_ms=(time.perf_counter()-began)*1000
    engine=AudioEngine(backend)
    try:
        with TemporaryDirectory() as folder:
            path=Path(folder)/'tone.wav'
            samples=b''.join(struct.pack('<h',round(math.sin(i/22050*math.tau*440)*3000)) for i in range(11025))
            with wave.open(str(path),'wb') as output:output.setparams((1,2,22050,0,'NONE','not compressed'));output.writeframes(samples)
            began=time.perf_counter();clip=backend.load(path);decode_ms=(time.perf_counter()-began)*1000
            assert len(clip.payload.get_raw())==clip.size_bytes and any(clip.payload.get_raw())
            began=time.perf_counter()
            for i in range(5):engine.dispatch(AudioCommand('play_sound','prova','probe:0',i,str(path),.3,.1,True),time.monotonic())
            start_ms=(time.perf_counter()-began)*1000
            assert len(engine.snapshot())==5
            assert all(backend.pg.mixer.Channel(i).get_busy() for i in range(5))
            engine.dispatch(AudioCommand('audio_volume','prova',gain=.4,fade_s=.15,scope='group'),time.monotonic())
            end=time.monotonic()+.2
            while time.monotonic()<end:engine.tick(time.monotonic());time.sleep(.01)
            engine.tick(time.monotonic())
            gains=[v.gain for v in engine.snapshot()]
            assert all(abs(gain-.12)<.02 for gain in gains)
            engine.dispatch(AudioCommand('stop_sound','prova',fade_s=.1,scope='group'),time.monotonic())
            end=time.monotonic()+.15
            while time.monotonic()<end:engine.tick(time.monotonic());time.sleep(.01)
            engine.tick(time.monotonic())
            assert not engine.snapshot()
            assert all(not backend.pg.mixer.Channel(i).get_busy() for i in range(5))
            return {'passed':True,'app_version':'4.8.0','platform':platform.system(),'driver':os.environ.get('SDL_AUDIODRIVER','system default'),
                    'pygame_ce':backend.pg.version.ver,'sdl':list(backend.pg.get_sdl_version()),
                    'soundfile':backend.sf.__version__,'python':platform.python_version(),
                    'mixer_format':list(backend.pg.mixer.get_init()),'clip_duration_s':clip.duration_s,
                    'init_ms':round(init_ms,3),'decode_ms':round(decode_ms,3),'start_5_channels_api_ms':round(start_ms,3),
                    'decoded_cache_bytes':backend.cache_bytes,'voices_tested':5,'group_fade_and_stop':True,
                    'windows_backend_exercised':platform.system()=='Windows','physical_output_verified':False,
                    'acoustic_latency_ms':None,'limitations':'API timings only. Device audibility, acoustic latency and unplug/recovery need physical validation.'}
    finally:engine.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--dummy',action='store_true');parser.add_argument('--report',type=Path)
    args=parser.parse_args()
    try:report=probe(args.dummy)
    except Exception as exc:report={'passed':False,'platform':platform.system(),'error':str(exc),'physical_output_verified':False}
    encoded=json.dumps(report,ensure_ascii=False,indent=2)
    print(encoded)
    if args.report:args.report.write_text(encoded+'\n',encoding='utf-8')
    return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
