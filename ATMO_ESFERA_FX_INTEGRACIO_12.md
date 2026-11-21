# ATMO ESFERA FX · Integració 12

## Obrir a Windows

Descarrega i extreu la branca `atmo/interficie-primera-integracio` completa en una
carpeta nova. No copiïs només el fitxer principal: necessita els mòduls del projecte.
Fes doble clic a `OBRIR_ATMO_12.bat`, al costat dels fitxers Python. Per a
l'escriptori, crea una drecera al BAT; el BAT ha de continuar dins la carpeta.
La versió 11 i la 10b es conserven sense canvis.

## Finestres i estètica

ATMO continua sent la interfície principal. **Eines completes ATMO** obre el conjunt
d'eines existent amb colors, controls i capçalera ATMO. **Tornar a ATMO** retorna al
panell principal. Tancar les eines completes les amaga; tancar el panell ATMO tanca
l'aplicació amb les comprovacions de zones i regles del motor.

Els panells deixen de dependre visualment de la finestra amagada del motor. També
s'aplica als ajustos de música, CC, Mute, àudio, zones, calibratge, regles,
participants, simulació, projecció i diagnosi MIDI. Reobrir una eina amagada la
mostra de nou. No s'utilitzen finestres sempre al davant ni captura modal del ratolí.
La sortida de projecció conserva el negre i les imatges: canviar el tema no ha de
canviar els continguts artístics. Els diàlegs de fitxers i avisos segueixen sent
els diàlegs natius del sistema operatiu.

L'edició integrada de zones es manté, amb un sol editor actiu, i l'editor ampliat
utilitza els mateixos controls ATMO. El botó **Seguir directe** també mostra ara
la previsualització, en comptes de limitar-se a canviar un estat intern.
Les pantalles inicials es conserven.

## MIDI i loopMIDI

A Windows, ATMO utilitza explícitament `mido.backends.rtmidi/WINDOWS_MM`. Això evita
que una configuració externa de Mido seleccioni un altre controlador. No implica
que qualsevol error MIDI estigui resolt: cal veure el resultat al Windows real.

L'estat del motor es mostra també al panell principal. Un error de detecció indica
el Python, el backend i el missatge original. No s'oculta l'error, però tampoc es
mostra un diàleg modal durant l'arrencada que pugui quedar darrere del motor ocult.

1. Obre loopMIDI i comprova que hi hagi un port creat (pot tenir qualsevol nom).
2. A ATMO, **Música i àudio → Connexió MIDI → Actualitzar ports**.
3. Selecciona el port i prem **Connectar / Fixar MIDI**. Seleccionar-lo no inicia
   la connexió automàticament. Detectar un port tampoc confirma recepció al DAW.
4. Si només hi ha un port, es preselecciona, però encara cal prémer Connectar.
   Si n'hi ha diversos, cal triar-ne un. Actualitzar no tanca la connexió existent.
5. Si falla, executa `DIAGNOSI_MIDI_ATMO.bat`. Aquesta prova mostra el Python, els
   mòduls i els ports; no obre ports ni envia notes ni CC.
6. Només si la diagnosi indica que falten `mido` o `rtmidi`, executa
   `INSTAL_LAR_MIDI_ATMO.bat` i torna a obrir ATMO. El BAT instal·la les versions
   del projecte al mateix Python seleccionat pel llançador. No s'executa sol.

El programa no selecciona silenciosament un altre port per connectar-se si el que
havies triat ha desaparegut. La connexió explícita conserva el cicle de notes i
Mute del motor existent.

## Comprovacions i límits

48 proves automàtiques superades: detecció MIDI, selecció explícita, conservació
de connexions, ports absents, obertura/reobertura de finestres, tema, correspondència
dels botons amb el motor, regressió de la integració 11 i model espacial.
Les proves de finestres utilitzen dobles de prova sense pantalla. Les de MIDI
utilitzen ports simulats. També s'ha executat la diagnosi sense dependències MIDI
per verificar que explica la mancança sense fallar amb un traceback.

```
python -m unittest discover -s tests -p test_atmo_runtime.py -v
python -m unittest discover -s tests -p test_atmo_integracio_11.py -v
python -m unittest discover -s tests -p test_spatial_zones.py -v
```

Pendent a Windows: obrir tots els botons de les set seccions; tancar i reobrir les
eines; comprovar proporcions i contrast; connectar el port real loopMIDI; verificar
recepció al DAW; repetir el desament de zones i les proves de càmera i projecció.
Encara no s'ha confirmat el text de l'error MIDI que apareix a l'ordinador de
l'usuari: no es pot afirmar que la seva causa concreta s'hagi resolt.

No s'han retirat funcions sense una revisió d'ús. Les il·lustracions definitives i
la simplificació de les eines continuen pendents. El motor font, les versions 10b
i 11, `main` i la branca original del motor no es modifiquen.
