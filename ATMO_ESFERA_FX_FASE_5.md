# ATMO ESFERA FX — fase 5A: prototip d’àudio local i BOSC VIU

Entrega: **Wasteland Machine 4.8.0**, sobre 4.7.9 (`032e335`), a
`codex/wasteland-camera-windows-launcher`.

**Estat: prototip funcional validat al núvol, no backend definitiu homologat.**
L’[auditoria](ATMO_ESFERA_FX_AUDITORIA.md) exigeix una prova del backend a Windows
abans de tancar la fase 5. Aquesta màquina és Linux i no té sortida física:
Windows, audibilitat, latència acústica i desconnexió/reconnexió del dispositiu
real continuen pendents. No es presenten com a superats ni es requereix cap
acció al PC des del qual s’està conversant.

## Complement opcional

El backend provisional utilitza **pygame-ce 2.5.8 / SDL_mixer**, amb
**soundfile 0.14.0** per a lectura i descodificació acotada. Les dependències
estan a `requirements-audio.txt`, separades de `requirements.txt`.
L’aplicació, MIDI, visuals i simulador continuen funcionant sense el complement.
No s’importen pygame/soundfile ni s’inicia el dispositiu en arrencar l’aplicació.

Per a una prova posterior a Windows:

1. Extreu el paquet complet i executa una vegada **INSTAL_LAR_AUDIO_LOCAL.bat**.
2. Obre **OBRIR_WASTELAND.bat**, que fa servir el mateix entorn `.venv`.
   L’accés històric `_461` pot seleccionar un altre Python i no tenir el complement.
3. Obre **Àudio → Àudio local opcional...** i prem **ACTIVAR**.
4. Si falla, el panell mostra el diagnòstic; cap so pendent es reproduirà
   automàticament quan s’activi el dispositiu més tard.

Es fa servir la sortida d’àudio predeterminada del sistema. No hi ha encara
selector propi de dispositiu, àudio espacial ni reproducció en streaming.
El dispositiu només es reserva per aquest backend dins del procés: no s’apropia
d’un mixer pygame ja obert per un altre component.

## Controls locals i aturada

El panell mostra fins a setze veus amb grup, canal **local**, font, marcador,
fitxer, volum efectiu i fade. Els canals locals són independents dels canals
MIDI. El màster escala el volum de totes les capes; el percentatge és un
control de guany, no un mesurador de nivell acústic.

- **ATURAR CAPA** fa una retirada amb fade del propietari seleccionat.
- **ATURAR ÀUDIO LOCAL** cancel·la també els inicis pendents i atura les veus
  locals, mantenint el backend disponible. No envia cap ordre a Sonar.
- **DESACTIVAR** atura i tanca el backend. **ACTIVAR** permet reintentar-lo.
- Tancar el panell deixa la reproducció activa. Tancar l’aplicació la finalitza.
- **SILENCI ABSOLUT** atura les veus locals i bloqueja noves accions sonores
  mentre continuï activat, a més de conservar el seu comportament MIDI.

Canviar de projecte/configuració de regles o tancar/perdre la càmera atura les
veus locals. Canviar el port MIDI no és una ordre d’aturada local: les dues
rutes són independents. Obrir un projecte no activa un backend desactivat;
si ja estava activat explícitament, queda disponible per als nous esdeveniments.
L’activació i el volum màster local són de sessió i no es desen al projecte.

## Accions de regles

L’editor afegeix **Reproduir so local, Aturar so local i Volum local**:

- Reproduir: WAV PCM/OGG, guany 0–1, fade d’entrada i bucle opcional.
- Aturar: grup d’àudio, fade 0–10 s i abast participant/marcador o tot el grup.
- Volum: guany 0–1, fade i el mateix selector d’abast.

Un grup d’àudio buit hereta el grup de la regla. Cada veu té propietari
`(grup, font, marcador)`: participants diferents poden mantenir el mateix so
en canals independents. Tornar a reproduir el mateix clip/bucle del mateix
propietari actualitza el guany sense començar-lo de nou i pot cancel·lar un
fade de retirada. Un altre grup permet una capa addicional del mateix participant.

El guany efectiu és guany de veu × guany de grup × màster. Un control de volum
de grup s’aplica també a veus futures, fins a una altra ordre o reinici d’estat.
Una alarma pot aturar els ocells i deixar el seu grup a zero fins a recuperar-lo.
Les ordres d’aturada de prioritat superior suprimeixen un inici contradictori
del mateix lot; controls de volum/aturada amb el mateix destinatari es resolen
per la prioritat i el desempat estables de la fase 4.

Un so sense bucle acaba quan el backend informa que el canal ja no està ocupat.
No s’utilitza el temporitzador de bloqueig del dispar MIDI a Sonar com a falsa
prova de final de l’àudio. La funció antiga **Àudio** de les targetes continua
sent el dispar MIDI existent, sense convertir-la automàticament en reproductor.

Les ordres reals es posen en una cua acotada. El diagnòstic de regles distingeix
«en cua d’àudio» de l’acceptació o error posterior del backend al panell local.
Un fitxer absent o una ordre rebutjada no desplaça les altres veus. Un error
comunicat per SDL es diagnostica i permet una nova activació explícita, sense
reproduir una cua antiga. Això no garanteix detectar totes les avaries físiques
que el sistema operatiu no comuniqui a SDL.

## BOSC VIU de prova

**Projecte → Crear BOSC VIU de prova...** crea i obre una carpeta nova amb JSON,
cinc participants, cinc zones i cinc WAV. Mai sobreescriu una experiència
existent; si el nom ja existeix, el menú proposa una carpeta numerada.
El projecte anterior no es desa automàticament i el diàleg ho indica.

Els sons es generen de manera determinista amb síntesi simple: **no són
gravacions de natura ni una banda sonora definitiva**. No es descarreguen
recursos d’Internet. La clariana utilitza un color de prova, substituïble per
una imatge des de l’editor de regles.

| Zona / ordre | Interacció del prototip |
|---|---|
| OCELLS | Entrada confirmada → cant sintètic curt, sense bucle. |
| RIU | Entrada → bucle i augment gradual de volum; sortida → fade d’aturada del mateix participant. |
| VENT | Entrada → capa i augment gradual; sortida → retirada amb fade. |
| CLARIANA | Entrada → color verd persistent. |
| ALARMA | So de prova, ocells aturats i grup silenciat, vent reduït i color vermell prioritari durant dos segons. |
| INICIAR AMBIENT | Ordre manual amb bucles independents de vent i fulles. |
| RECUPERAR BOSC | Ordre manual que atura l’alarma, recupera els grups i allibera la seva ordre visual. |

El volum del riu/vent varia per transició confirmada de zona i fade; encara no
es calcula una modulació contínua per distància o moviment. La sortida d’exit
de les regles de prova utilitza `any`, inclosa revalidació per pèrdua prolongada;
és editable. No hi ha joc, penalitzacions, Kaoss ni sincronització amb Sonar.

El projecte es crea **sense calibració física**. El menú obre el simulador i
hi carrega una còpia. A **Sortida de prova** es veuen les veus, volums i fades
simulats, sense dispositiu ni so real. Les proves amb WAV funcionen encara que
no s’hagi instal·lat el complement. La inspecció d’OGG necessita soundfile.

Per escoltar després, activa l’àudio local i executa una regla manual des del
formulari real, o utilitza la càmera amb calibració física vàlida. El simulador
continua sent silenciós; no s’ha afegit cap connexió oculta a la sortida real.

## Arquitectura, límits i recursos

- `local_audio.py`: motor de veus/grups/fades, backend silenciós i adaptador SDL.
- `audio_controller.py`: un treballador dedicat que importa el complement,
  descodifica, reprodueix i avança fades fora de Tk i del fil musical MIDI.
- `audio_window.py`: només instantànies immutables i ordres; el treballador
  no modifica widgets.
- `bosc_viu.py`: constructor de l’experiència de prova i els WAV sintètics.

El prototip accepta clips mono/estèreo de fins a **30 s**, entre 8 i 96 kHz,
amb fitxer de fins a **16 MiB** i límits addicionals de descodificació. No és
un sistema per carregar ambients llargs a RAM. A taxes altes, el límit de PCM
transitori pot restringir més la durada. S’utilitzen bucles de clips curts.

PCM/mixer: 48 kHz, 16 bits, estèreo; reescalat lineal quan cal. Buffer nominal
de 512 mostres, que **no és una mesura de latència acústica**. Cada clip està
limitat a 8 MiB de dades i la memòria cau a **32 MiB i 32 entrades**, sense
expulsar clips en ús. Són límits de PCM emmagatzemat; no inclouen l’intèrpret,
SDL, les imatges ni tots els buffers transitoris del descodificador.

Hi ha **16 canals**, **64 controls de grup**, cua de **128 ordres** i registres
de **100 entrades**. No es roba una veu activa per admetre’n una altra. Les
ordres rebutjades queden al diagnòstic. Una aturada global cancel·la un inici
que encara s’estigui carregant abans que pugui començar a sonar.

Els projectes anteriors de regles segueixen amb `schema_version: 1`. Quan hi ha
accions d’àudio es desa `schema_version: 2`, amb `audio_group`, `gain`, `fade_s`,
`loop` i `audio_scope`. La versió nova llegeix ambdues; una versió antiga pot
rebutjar el format nou. No s’hi desen veus actives, activació, cues o rellotges.
`Desar com` també rebasa les rutes dels sons, igual que les imatges.

## Evidència i següent validació

**246 proves correctes, cap omesa**, amb Python 3.12, pantalla virtual Xorg,
les dependències bàsiques fixades i el complement opcional instal·lat al núvol.
Les 206 proves anteriors també s’han executat amb el backend desactivat abans
d’afegir les proves noves.

La suite inclou WAV i OGG sobre SDL real amb **controlador `dummy`**, cinc
canals simultanis, remostreig, final natural, fades, aturada, mixer ocupat,
errors d’inicialització/dispositiu, reintent explícit, límits de memòria/cua,
cancel·lació de càrregues, absència del complement i regressions anteriors.
Hi ha proves de BOSC VIU complet en simulació i del panell/controls al núvol.

La descodificació comparteix el treballador amb el control de fades: una càrrega
pesada pot retardar el següent pas d’un fade, encara que SDL continuï mesclant
les veus i Tk/MIDI no hagin d’esperar-la. La regularitat sota càrrega també
forma part de la validació física pendent.

```text
python -m unittest discover -s tests -v
python -m tools.prova_audio_local --dummy --report AUDIO_PROVA_NUVOL.json
```

[AUDIO_PROVA_NUVOL.json](AUDIO_PROVA_NUVOL.json) registra una execució Linux amb
SDL 2.32.10: temps d’inicialització, descodificació d’un WAV de 0,5 s i inici
per API de cinc canals amb memòria cau calenta, amb 96.000 bytes de PCM compartit.
Són **una observació de temps de programari**,
no una garantia, un benchmark de pitjor cas o latència fins a l’altaveu.
`physical_output_verified` i `windows_backend_exercised` són falsos.

També s’ha executat el bucle real de Tk amb SDL `dummy`: ambient amb quatre
capes, alarma que retira ocells, aturada local, simulador silenciós, cap enviament
MIDI i tancament del treballador sense veus pendents. S’han comprovat les rodes
publicades de pygame-ce i soundfile per a Python 3.12 / Windows x64; això no és
una instal·lació ni execució a Windows.

**Pendent abans de tancar la fase 5 i triar backend definitiu:** prova a Windows
amb el dispositiu real, audibilitat, latència d’inici i retirada mesurada,
comportament de desconnexió/reconnexió i sessió llarga amb càmera/MIDI/projector.
S’ha deixat **PROVAR_AUDIO_LOCAL.bat**, que executa el mateix probe amb el driver
configurat i desa `AUDIO_PROVA_WINDOWS.json`. El probe no pot confirmar per si
sol que s’escolti als altaveus ni mesurar la latència acústica. No s’ha de
confondre un resultat de `dummy` amb validació física.

El punt de recuperació és 4.7.9, `032e335`, amb el projecte original. El backend
continua opcional i desactivat d’entrada mentre es completa aquesta validació.
