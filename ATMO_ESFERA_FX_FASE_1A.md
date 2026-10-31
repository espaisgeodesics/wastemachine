# ATMO ESFERA FX — fase 1A completada

Entrega: **Wasteland Machine 4.7.5**, sobre la base estable 4.7.4. Arquitectura i primer increment aprovats per Jordi després de l’[auditoria A–G](ATMO_ESFERA_FX_AUDITORIA.md).

Aquesta fase introdueix el model comú de detecció i un seguiment passiu. La detecció actual continua executant les funcions musicals i visuals; el seguiment nou observa les mateixes deteccions, sense enviar notes, canviar imatges ni aplicar regles de joc. No s’han migrat els projectes ni afegit dependències.

## Fitxers i contractes

- `marker_tracking.py`: model immutable `MarkerObservation`, `ObservationFrame`, `MarkerState`, `ObservationSample`, `SourceState` i motor `MarkerTracker`. No importa Tkinter, OpenCV, Mido ni cap reproductor.
- `aruco_observations.py`: converteix el resultat del detector ArUco en un fotograma comú. No activa funcions de targeta.
- El principal incorpora `App.observe_marker_frame`, connectat després de detectar i abans de les accions existents. No es torna a llegir la càmera ni es repeteix el detector.
- El BAT comprova que els dos mòduls nous siguin presents, juntament amb els espacials.

Un `ObservationFrame` conté font, seqüència, temps monotònic de captura, estat de font i observacions. La font s’identifica com `camera:0`, `camera:1`, etc.; la seqüència de l’adaptador creix durant l’execució. Tots els marcadors del fotograma s’entreguen alhora, també els que tenen **Cap acció** o una funció musical diferent de zones.

Cada observació conserva ID 0–15, centre X/Y normalitzat de la imatge original, cantonades normalitzades i orientació en voltes `[0,1)`, no graus. L’espai de coordenades és explícitament `camera_normalized`: **no és la posició dels peus ni el resultat d’una calibració de terra**. La conversió manté la convenció de centre i gir del camí actual.

El diccionari físic continua sent `DICT_4X4_50`; el convertidor filtra els IDs 16–49 com fa el programa existent. El model comú rebutja IDs fora de 0–15, dades no finites o fora de rang, dues deteccions amb el mateix ID en un fotograma i temps/seqüències que no creixen per font. Un fotograma invàlid no modifica parcialment l’estat de seguiment.

## Identitat i pèrdues de detecció

La identitat física és `(font, ID ArUco)`. Dos marcadors de fonts diferents no comparteixen l’estat encara que tinguin el mateix número. Això encara no és un registre de persones: noms, colors i vinculació marcador/participant corresponen a la fase 1B.

| Estat | Significat |
|---|---|
| `detected` | El marcador apareix en el fotograma vàlid actual. |
| `temporarily_lost` | No apareix en una imatge vàlida recent, o la font no està disponible. |
| `absent` | Una imatge vàlida confirma que fa almenys el temps configurat que no es veu. |
| `retired` | Retirada explícita amb l’API de desenvolupament; no es produeix per una pèrdua de càmera. |

El llindar d’absència del seguiment és **1 segon per defecte**, configurable al construir el motor. És independent dels **250 ms** del funcionament MIDI actual i dels filtres espacials: aquesta entrega no canvia cap d’aquests temps.

Una font `ok` sense observacions és diferent d’una font `unavailable`. Durant una avaria de càmera, el seguiment no confirma absència només perquè passen segons: els marcadors queden temporalment perduts amb `source_available=False`. Això no elimina participants ni penalitza ningú. En recuperar una detecció, conserva `first_seen` i la identitat física. Si la primera imatge vàlida després de recuperar la càmera continua buida i ha passat el llindar, pot confirmar absència.

L’última posició es conserva com a dada antiga: `observed=False` i `age_s` indiquen que no és una detecció actual. El canvi d’índex de càmera marca la font anterior com a no disponible; les identitats de la nova són independents. Tancar/reobrir el mateix índex conserva les identitats físiques conegudes.

L’API `retire(source_id, marker_id)` és només de desenvolupament, no afegeix un botó ni un sistema de joc. Una retirada explícita no es desfà perquè la càmera torni a veure aquell ID. L’estat de seguiment és de memòria durant l’execució; no es desa al projecte ni es migra cap dada de Jordi.

## Límits i aïllament

Per defecte: 4 fonts com a màxim, 16 IDs per font, 90 mostres d’historial per marcador i horitzó de 2,5 segons. Es conserva l’última observació fora de l’historial quan cal per informar d’una posició antiga. No es guarden fotogrames de càmera per marcador. Els límits són configurables i validats.

Les instantànies són còpies de només lectura amb estats immutables; consultar-les no canvia el seguiment. Els errors de l’adaptador s’acumulen en un registre limitat a 50 entrades, sense afegir-los al registre de recepció MIDI ni modificar l’estat de Sonar. Un error del nou observador es conté perquè la lògica existent continuï. Si el nou observador rebutja un fotograma, això no reescriu les decisions del camí musical antic: encara no és l’autoritat de control.

No hi ha cap finestra nova ni overlays públics. Per inspecció de desenvolupament sobre una instància `app`:

```python
states = app.marker_tracker.snapshot()
source_states = app.marker_tracker.sources()
errors = tuple(app.tracking_errors)
# Exemple, si el marcador ja s’ha detectat:
state = states.get(('camera:0', 4))
if state:
    print(state.presence, state.last_observation.position, state.age_s,
          state.observed, state.source_available)
```

`app.tracking_enabled=False` permet comparar el camí existent sense observador durant proves; no és una preferència que s’hagi de canviar al projecte. No s’ha traslladat encara la lectura de càmera fora del fil Tkinter, ni implementat el simulador de cinc participants o la compensació d’alçada dels barrets.

## Validació

**120 proves correctes, cap omesa**, amb Python 3.12 i pantalla virtual Xvfb: les 103 anteriors i 17 noves.

S’ha verificat:

- Cinc IDs 0–4 amb estats independents i ordre del detector variable.
- Pèrdua breu, absència confirmada, posició antiga, retorn i retirada explícita.
- Avaria prolongada de font diferenciada de fotograma buit, i canvi de càmera.
- Duplicats, dades invàlides, errors de temps i seqüència, sense actualitzacions parcials.
- Instantànies immutables, historial limitat, nombre de fonts limitat i errors limitats.
- Conversió de cantonades, centre i orientació en coordenades originals.
- Detecció amb el detector OpenCV real d’una imatge sintètica de cinc marcadors, desaparició, avaria i reaparició.
- **Igualtat exacta de missatges MIDI i arrays dels fotogrames públics** en la mateixa seqüència amb l’observador activat/desactivat.
- La mateixa igualtat injectant una excepció al motor de seguiment.

Les regressions existents continuen comprovant notes, harmonia/arpegis, bateria, Mute, diagnosi, calibració, persistència/durada d’imatges, color, projecció i projectes. Això no mesura latència ni precisió amb cinc persones reals.

Proves només del model, sense càmera, MIDI ni pantalla:

```text
python -m unittest discover -s tests -p test_marker_tracking.py -v
```

Suite completa, des d’un escriptori amb Tkinter o pantalla virtual:

```text
python -m unittest discover -s tests -v
```

## Windows i recuperació

1. Desa el projecte actual i conserva la carpeta estable 4.7.4.
2. Extreu tot el paquet 4.7.5 en una carpeta nova; no copiïs només el principal. Necessita els quatre mòduls espacials i els dos nous mòduls de seguiment al seu costat.
3. Obre `OBRIR_WASTELAND.bat` i comprova **4.7.5** a la capçalera/Ajuda. L’accés anterior també serveix si tots els mòduls són a la carpeta.
4. Obre el teu JSON existent, comprova MIDI i fotografies com abans, inclosa la retirada i el compte enrere configurat. La calibració desada continua servint per a les proves de targetes, amb els límits físics ja documentats.
5. Fes una prova curta de desconnexió/reobertura de càmera al Windows abans de fer que el seguiment nou controli regles. Aquest desplegament no activa penalitzacions ni jocs.

Per recuperar la versió anterior, obre la carpeta estable amb el seu projecte original. No hi ha migració que s’hagi de desfer. El paquet estable es pot recuperar al commit `bde3ccac6cf25d14e3078b192eb41d26c1cb0ede`.

**Següent increment proposat:** fase 1B, registre de participants i esdeveniments comuns. Després, simulador visible de cinc participants. Aquesta entrega només completa la fase 1A aprovada.
