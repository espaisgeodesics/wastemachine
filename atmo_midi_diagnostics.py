"""Read-only MIDI diagnosis, with the same Python as the ATMO launcher."""
import importlib
import sys
from atmo_runtime import detect_midi


def main():
    print('ATMO ESFERA FX · Diagnosi MIDI')
    print('Python:', sys.executable)
    print('Versió:', sys.version)
    for name in ('mido', 'rtmidi'):
        try:
            module = importlib.import_module(name)
            print(name + ': disponible', getattr(module, '__version__', ''))
        except Exception as exc:
            print(name + ': ERROR', type(exc).__name__, str(exc))
    try:
        mido = importlib.import_module('mido')
    except ImportError:
        mido = None
    ports, error, backend = detect_midi(mido)
    print('Backend:', backend)
    if error:
        print('ERROR:', error)
        print('Si falten mido o rtmidi, executa INSTAL_LAR_MIDI_ATMO.bat amb el mateix Python.')
        return 1
    print('Ports de sortida:', repr(ports))
    print('Aquesta prova no obre ports ni envia missatges MIDI.')
    print('Si no hi ha ports, comprova que loopMIDI tingui un port creat i actualitza els ports a ATMO.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
