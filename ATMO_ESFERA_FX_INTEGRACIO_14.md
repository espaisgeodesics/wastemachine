# ATMO ESFERA FX · Integració 14

Obre la carpeta completa amb **OBRIR_ATMO.bat** o **OBRIR_ATMO_14.bat**. Els
llançadors es mantenen a Python 3.12 i continuen entrant a la pantalla principal.

## Funció i configuració per targeta

L'editor inclou **Chaos Oscillator (Kaoss XY)** al selector de funcions i un botó
permanent **CONFIGURAR FUNCIÓ…**. Seleccionar una funció obre la seva configuració;
el botó permet tornar-la a obrir sense canviar-la ni tornar-la a seleccionar.

- Chaos: presets ATMOSFERA, PULSACIÓ, TRANSFORMACIÓ i ÒRBITA; instrument o efectes;
  canal, tònica, escala, rang de notes, velocitat, eixos X/Y, rotació, inversions,
  CC, suavització, zona morta, quantització i temps d'absència.
- Harmonia, arpegiador, patró rítmic i bateria: editor musical existent.
- CC, àudio, Mute i zones: els seus editors específics existents.
- Nota MIDI, tempo i canvi de visual: formulari amb els paràmetres corresponents.
- Cap acció: indica que no necessita paràmetres addicionals.

Aplica la configuració a la targeta i després desa el projecte. El formulari Chaos
està vinculat a una targeta i al projecte on s'ha obert: no aplica silenciosament
a una altra targeta o a un projecte diferent.

## Chaos en directe

Es reutilitza el `KaossEngine` existent, que fins ara només s'utilitzava al
simulador. Ara les observacions de la càmera o de la simulació de targeta del
motor alimenten també aquest motor i les seves notes/CC passen pel mateix port
MIDI i registre de l'aplicació. La configuració es desa al bloc `kaoss` de cada
targeta dins del projecte habitual; els projectes anteriors continuen sent vàlids.
La prova independent del simulador continua disponible i conserva la seva
configuració independent.

Chaos és un controlador/instrument MIDI XY: **no s'ha afegit un sintetitzador
intern d'àudio**. Per sentir-lo, connecta loopMIDI i un instrument receptor al DAW,
amb el canal corresponent. Cada assignació Chaos necessita un canal propi, separat
d'altres targetes MIDI, de la taula de volums i de les regles. El formulari proposa
un canal lliure i rebutja els conflictes en aplicar.

El temps d'absència configurat s'aplica tant al seguiment de la targeta com a la
veu Kaoss. Retirar la targeta, canviar de funció, canviar de projecte o activar
silenci allibera les notes. Si falla un NoteOff, l'antic motor conserva la propietat
de la veu i bloqueja la reassignació fins que es pugui alliberar. Sense port MIDI
no es deixen notes pendents per a una connexió futura.

## Previsualització

S'elimina l'obertura de visuals des del callback de selecció de la taula de
targetes. La selecció automàtica de files, inclosos els esdeveniments pendents
d'arrencada, pot actualitzar el mapa de targeta sense obrir la previsualització.
El botó explícit de visuals continua obrint-la.

## Validació

97 proves superades: 33 de presentació, arrencada i integració prèvia; 23 del model
espacial; 23 del Kaoss existent; i 18 de la integració per targetes. Les noves proves
cobreixen l'aplicació real de configuracions del motor, el desament JSON, la ruta
MIDI, la retirada, el silenci, l'absència, canals ocupats, NoteOff fallits, canvi de
funció, callbacks de configuració i selecció de taula sense obertura de visuals.
També es comprova la sintaxi de tots els fitxers Python.

Les proves MIDI utilitzen un receptor simulat. Falta validar el formulari gràfic,
la càmera i el so real al Windows de l'usuari.

Prova curta:

1. Projecte nou: la previsualització ha de continuar tancada.
2. Editor de targetes → targeta → Chaos Oscillator (Kaoss XY).
3. Carrega un preset, revisa el canal lliure i prem Aplicar a la targeta.
4. Connecta MIDI al DAW; mou/gira la targeta i després retira-la.
5. Torna a obrir CONFIGURAR FUNCIÓ…; desa i reobre el projecte per revisar els valors.
6. Repeteix el botó amb arpegiador i patró rítmic; els editors anteriors s'han
   de continuar obrint davant de la principal.
