"""Build only the current runtime closure; no previous entry versions or user data."""
import ast
import json
from pathlib import Path
import shutil
import zipfile
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
ENTRY='atmo_esfera_fx_integracio_19'
ENGINE='atmo_esfera_fx_4_5_15_pas_15_editor_musical_desplegable'


def build(destination):
    destination=Path(destination)
    if destination.exists():shutil.rmtree(destination)
    destination.mkdir(parents=True)
    pending=[ENTRY,ENGINE,'atmo_frozen_check'];included=set()
    while pending:
        name=pending.pop()
        source=ROOT/(name+'.py')
        if name in included or not source.is_file():continue
        included.add(name);shutil.copy2(source,destination/source.name)
        tree=ast.parse(source.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            names=([node.module] if isinstance(node,ast.ImportFrom) and node.module else
                   [alias.name for alias in node.names] if isinstance(node,ast.Import) else [])
            pending.extend(n.split('.')[0] for n in names)
    (destination/'atmo_assets').mkdir()
    for name in ('atmo_logo.png','atmo_joc.png','atmo_musica.png','atmo_exposicio.png','atmo_immersiva.png','APROVACIO_IMATGES.json'):
        shutil.copy2(ROOT/'atmo_assets'/name,destination/'atmo_assets'/name)
    with Image.open(ROOT/'atmo_assets'/'atmo_logo.png') as image:
        image.save(destination/'atmo_assets'/'atmo.ico',format='ICO',sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
    for guide in ('GUIA_XY_CAKEWALK.txt','GUIA_CONTROL_DIRECTE_CAKEWALK.txt','GUIA_FADES_CAKEWALK.txt'):
        shutil.copy2(ROOT/guide,destination/guide)
    shutil.copy2(ROOT/'packaging'/'LLEGEIX_ME.txt',destination/'LLEGEIX_ME.txt')
    (destination/'OBRIR_ATMO.bat').write_text('@echo off\ncd /d "%~dp0"\npy -3.12 atmo_esfera_fx_integracio_19.py\npause\n')
    (destination/'requirements.txt').write_text('numpy\nopencv-contrib-python\nPillow\nmido==1.3.3\npython-rtmidi==1.5.8\npygame-ce==2.5.8\nsoundfile==0.14.0\n')
    (destination/'MANIFEST.json').write_text(json.dumps({'entry':ENTRY,'engine':ENGINE,'modules':sorted(included)},indent=2))
    forbidden=[p.name for p in destination.glob('atmo_esfera_fx_integracio_*.py') if p.stem!=ENTRY]
    if forbidden:raise RuntimeError('Old entry modules remain: '+str(forbidden))
    archive=destination.parent/'ATMO_ESFERA_FX_Codi_net.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as output:
        for path in sorted(destination.rglob('*')):
            if path.is_file():output.write(path,Path('ATMO_ESFERA_FX')/path.relative_to(destination))
    return sorted(included)


if __name__=='__main__':
    import sys
    print(json.dumps(build(Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'build'/'clean'),indent=2))
