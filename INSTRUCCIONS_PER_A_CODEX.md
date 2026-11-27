# ATMO ESFERA FX · Continuació per a Codex

## Estat i base
Aquest ZIP és una còpia completa del projecte de la integració 18, partint de la V2 aprovada per l'usuari. Inclou el sistema visual V3 i els recursos locals. **No és una certificació que totes les finestres hagin estat verificades a Windows.**

Repositori: `espaisgeodesics/wastemachine` (nom administratiu, no identitat visual). Branca autoritzada: `atmo/interficie-primera-integracio`. No tocar `main` ni la branca original. Entrada Windows: `OBRIR_ATMO.bat` → `py -3.12 atmo_esfera_fx_integracio_18.py`.

## Decisió artística aprovada
ATMO Atmosfera viva: orgànic, atmosfèric, llum fluida i formes etèries. Sense referències estètiques al producte antic. Segoe UI; colors a `atmo_runtime.py`: fons `#080e20`, panells `#121f39`, controls `#1a2c49`, text `#f2f6ff`, cian `#4ce2e0`, lila `#a78bfa`, verd `#72dfa8`, alerta `#ef899b`. Les quatre imatges de l'inici han de seguir **grans i adaptables**, com a V2: l'usuari les ha aprovat explícitament.

## Canvis V3 ja fets
- `atmo_runtime.py`: estils ttk unificats amb tema `clam`, botons primaris/secundaris/perill, camps, pestanyes, taules, scrollbars, tipografia, focus i desactivats; estilització conservadora dels widgets Tk clàssics; mecanisme per aplicar el tema a finestres que s'obren més tard.
- `atmo_esfera_fx_integracio_18.py`: instal·lació del tema global a l'arrencada.
- Es mantenen les imatges locals i la disposició responsive V2 de la pantalla inicial.

## Tasques de Codex (pendents, per completar amb execució Windows)
1. Executar l'aplicació a Windows i inspeccionar **totes** les finestres. Fer captures d'inici, projectes, motor, càmera/previsualització, targetes, música/arpegiador, MIDI, Ambients XY, zones, calibració, volums, àudio local, diagnosi, simuladors, participants i regles.
2. Corregir contrastos, marges, tipografies, mides de finestra, desbordaments i scrolls per a 100/125/150% DPI. No ocultar controls ni canviar-ne el comportament. No alterar el projector ni els Canvas amb dades semàntiques.
3. Revisar que `install_window_theme` no introdueixi recursió, errors de mapatge ni retard; si en produeix, substituir per tematització explícita de cada finestra.
4. Preservar connexió loopMIDI/Cakewalk, notes/canals, arpegiador, Chaos XY sense generació de notes, volums, mitjans i fades, calibració i JSON.
5. Executar `python -m compileall -q .` i `python -m unittest discover -s tests` o la suite pròpia del repositori. Registrar pass/fail/skip i diferenciar limitacions d'entorn.
6. Fer commit només a la branca autoritzada, documentar captures i llista de fitxers modificats.

## Requisits no negociables
Llegir `COMENCA_AQUI_REVISIO_ESTETICA.md` i `ATMO_ESFERA_FX_INTEGRACIO_18.md`. Mantenir l'opció **Visual assignat: Cap**, mapes de targetes simultanis, projecció neta, configuracions MIDI, finestres auxiliars al davant i no obrir previsualització automàticament. Participants/regles només a Joc. No recuperar estètica antiga ni substituir el motor.
