# ATMO ESFERA FX — fase 6A: Kaoss XY al simulador

Entrega: **Wasteland Machine 4.8.1**, sobre 4.8.0 (`81f8b00`), branca
`codex/wasteland-camera-windows-launcher`.

**Estat: motor i editor de prova, sense connexió Kaoss a les sortides reals.**
Aquesta entrega avança la fase 6 mentre continua pendent la validació física
Windows/àudio de la fase 5. No tanca cap d’aquestes dues fases completes.
No requereix descarregar ni instal·lar res al PC des del qual es conversa.

## Què es pot provar

A **Participants → Simulador de cinc participants… → Kaoss XY de prova**:

1. Tria un ID de marcador virtual.
2. Selecciona un preset i prem **CARREGAR PRESET**: només omple el formulari.
3. Ajusta els camps i prem **APLICAR A LA PROVA**.
4. Mou el participant a **Mapa i moviment**; el gir s’aplica amb els controls
   existents. Consulta els missatges a **Sortida de prova**.
5. **DESAR KAOSS…** desa totes les assignacions aplicades. Els canvis que encara
   només són al formulari no es desen. **OBRIR KAOSS…** valida abans de substituir.

| Preset | Mode | X | Y | Rotació |
|---|---|---|---|---|
| ATMOSFERA | Instrument | Notes de l’escala | CC 74 | CC 11 |
| PULSACIÓ | Instrument | Notes de l’escala | Velocitat de la nota | CC 74 |
| TRANSFORMACIÓ | Efectes | CC 74 | CC 1 | CC 11 |
| ÒRBITA | Efectes | CC 10 | CC 11 | CC 1 |

En mode Instrument, X selecciona notes de l’escala dins del rang MIDI inclusiu.
La tònica és una classe de nota: Do=0, La=9. El rang utilitza números MIDI,
sense imposar la numeració d’octaves de cap sintetitzador. La velocitat varia
entre 1 i 127; variar Y amb la mateixa nota sostinguda no la torna a disparar.
En mode Efectes no s’emeten notes.

X creix d’esquerra a dreta; Y de càmera creix cap avall i s’inverteix per defecte.
Cada eix es pot invertir. La rotació es pot desactivar, especialment per a una
futura prova Dome. Es filtra per l’arc curt en travessar 360°/0°.

Hi ha suavització temporal exponencial de 0–2 s, zona morta de 0–0,2 en coordenades
normalitzades i quantització lliure, a quart, mig o un temps. La prova avança
amb el pols existent del simulador (aproximadament 100 ms) i tempo 120 BPM.
El motor admet un tempo explícit; encara no hi ha sincronització amb el
transport de Sonar ni garantia de precisió musical amb el dibuix de Tk.

## Vida de les notes i canals

Cada assignació utilitza un canal MIDI exclusiu, separat dels altres Kaoss i
de les regles virtuals habilitades. Les col·lisions es rebutgen en tots dos
sentits abans d’aturar o canviar la configuració anterior. La càrrega de zones
amb regles incompatibles també es rebutja abans de substituir el mapa.

Un canvi de nota envia Note Off abans del nou Note On. Un Note Off rebutjat
conserva la propietat i bloqueja la nota següent fins al reintent. Una nota
nova rebutjada no queda pendent per reproduir-la més tard sense una observació
nova. Aquests casos s’han provat amb destinataris injectats; el simulador només
registra ordres, sense port real.

L’absència i la font no disponible alliberen la nota quan passen 250 ms per
defecte (configurable 50 ms–2 s), sempre que el rellotge continuï avançant.
Una nota pendent de quantització també es cancel·la en perdre el marcador.
Retirar una persona deixa d’aportar observacions i aplica el mateix termini.

Canviar assignacions allibera les notes Kaoss anteriors. **DESACTIVAR MARCADOR**
elimina una assignació; **SILENCIAR PROVA** les elimina totes. Aquest botó no
atura les regles ni l’àudio de prova. Tancar el simulador allibera les notes;
reobrir-lo conserva les assignacions i les observacions noves poden activar-les.
**REINICIAR PROVA** conserva configuració, però no veus ni deteccions anteriors.

Els CC actius han de ser diferents; es rebutgen els pedals 64, 66 i 69 i els
missatges de canal 120–127. Els CC es dedupliquen i es limiten a cinquanta lots
per segon i marcador. A la interfície, el pols més lent imposa el límit efectiu.

## Configuració i compatibilitat

Els fitxers `.kaoss.json` tenen `schema_version: 1` i assignacions per ID sota
`kaoss_xy`. Es validen tipus, camps, límits, canals i rangs; la lectura es limita
a 64 KiB. El desament utilitza un fitxer temporal i substitució atòmica.
S’admeten fins a setze assignacions, per a IDs ArUco 0–49; la sessió visible
continua limitada a cinc participants.

La configuració de prova és independent del JSON de projecte. No s’afegeix
encara «Kaoss XY espacial» al selector de funcions reals. No s’importen fitxers
Kaoss automàticament en obrir projectes. Els presets no alteren les targetes
existents i no s’obre cap dispositiu MIDI o d’àudio.

Mòduls nous: `kaoss_xy.py` (configuració i motor amb rellotge/destinatari
injectables) i `kaoss_editor.py` (formulari de prova). La integració utilitza
les observacions actuals del simulador i el registre MIDI simulat existent.
El principal només actualitza la versió. No canvien els camins reals de MIDI,
Mute, seqüenciador, visuals, zones, projecció o gravació ni les dependències.

## Verificació al núvol

**273 proves superades**, incloses 27 noves: quatre presets, configuració
personalitzada, escala i extrems, velocitat sense redispar, ordre Off/On,
quantització, pèrdua/font avariada, reintents, zona morta, rotació circular,
canals de cinc participants, validació atòmica, editor i desament/lectura.
Les proves d’integració comproven que la sortida real MIDI i els fotogrames
públics continuen idèntics, i la bateria existent verifica la resta de funcions.

Entorn: Python 3.12.14, Linux, servidor X virtual `:99`, complement d’àudio
opcional instal·lat i SDL dummy només dins de les seves proves. S’ha detectat
un avortament de Tk quan el recollidor automàtic finalitza objectes d’una prova
anterior des d’un fil MIDI. El llançador de proves recull aquests objectes al
fil principal entre proves; això no modifica el funcionament de l’aplicació.

Des de l’arrel, amb l’entorn virtual configurat:

```sh
DISPLAY=:99 PYTHONDONTWRITEBYTECODE=1 python -m tools.provar_tests
```

Cal accés al servidor X; sense pantalla, les proves gràfiques s’ometen i no
constitueixen la verificació completa d’aquesta entrega.

## Pendent per a la fase 6B

Connectar el motor a «Kaoss XY espacial» com a funció explícita de targeta,
reservar canals també respecte del MIDI antic i el mesclador, integrar el seu
rellotge fora del dibuix i desar la configuració dins del projecte. Verificar
Panic, aturada de càmera, edició, canvi de port i tancament amb el port real
simulat abans d’activar cap ruta física. Després caldrà una prova amb càmera,
receptor MIDI i Sonar. La simulació actual no acredita cap d’aquestes proves
físiques ni el calibratge Dome.
