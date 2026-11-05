# ATMO ESFERA FX — fase 2: simulador de cinc participants

Entrega: **Wasteland Machine 4.7.7**, sobre la [fase 1B, 4.7.6](ATMO_ESFERA_FX_FASE_1B.md),
commit recuperable `c349ed2`, branca `codex/wasteland-camera-windows-launcher`.
Continua l’abast de la fase 2 definit a l’[auditoria](ATMO_ESFERA_FX_AUDITORIA.md).

## Ús

Obre **Participants → Simulador de cinc participants…**. No cal càmera ni MIDI.
És una finestra separada; no es recuperen controls de ratolí sota la
previsualització musical existent.

- **Mapa i moviment** mostra cinc participants amb nom, color, marcador i una
  fletxa d’orientació. Clica un cercle per seleccionar-lo i arrossega’l per
  moure’l. La posició es limita a la superfície normalitzada `[0,1] × [0,1]`.
  Un arrossegament iniciat fora d’un participant no el mou.
- Escriu un gir en graus i prem **APLICAR GIR**. Una volta completa equival a
  360°; el contracte intern conserva l’orientació en voltes `[0,1)`.
- **OCULTAR / MOSTRAR** simulen pèrdua i reaparició del marcador seleccionat.
  L’absència es confirma després d’un segon amb font disponible; la persona
  no s’elimina ni es reassigna. El punt gris ratllat és una guia de simulació,
  no una detecció actual.
- Desmarca **Font disponible** per simular una avaria. Tots els marcadors
  observats passen a pèrdua temporal, sense confirmar absència per l’avaria.
  Torna-la a marcar per recuperar la font.
- **Participants i esdeveniments** permet editar noms, colors i IDs 0–15,
  retirar i recuperar cada persona, eliminar vinculacions i crear-ne de noves.
  Hi ha com a màxim cinc participants; elimina’n un abans de crear-ne un altre.
  La font virtual és fixa: `simulator:0`. Els IDs duplicats es rebutgen.
- **RETIRAR** conserva la identitat i impedeix que **MOSTRAR** desfaci la
  retirada. **RECUPERAR** restaura el participant i mostra el seu marcador;
  encara cal que la font estigui disponible per detectar-lo.
- **REINICIAR PROVA**, amb confirmació, torna als cinc participants inicials
  i buida seguiment i esdeveniments virtuals. No modifica el projecte real.

El registre de la segona pestanya mostra els últims 30 esdeveniments comuns,
amb seqüència, tipus, font, marcador i participant. El model en conserva 500.
Les posicions antigues estan marcades com a tals; els estats de persona i
de font continuen diferenciats com a les fases anteriors.

Tancar la finestra atura els seus temporitzadors i conserva la sessió virtual
en memòria. Reobrir-la recupera noms, posicions i estat. Sortir del programa
o reiniciar la prova descarta la sessió virtual. Les dades del simulador
**no es desen amb el projecte**, i els textos de la finestra ho indiquen.

## Contracte i aïllament

`participant_simulator.py` no importa Tkinter, OpenCV ni Mido. Crea
`ObservationFrame` i `MarkerObservation` amb font `simulator:0`, seqüència
creixent i temps monotònic; usa el mateix `MarkerTracker`, `ParticipantBinding`,
`ParticipantRegistry` i `CommonEventLog` de producció. Cada fotograma conté
tots els marcadors virtuals visibles i no retirats. Una avaria genera
`status='unavailable'` i zero observacions, diferent d’una imatge vàlida buida.

Les posicions estan etiquetades `camera_normalized`: són coordenades virtuals
de prova, **no coordenades calibrades de terra ni dels peus**. La quadrícula
és una referència de moviment; no crea zones espacials ni constitueix una
calibració Dome.

`simulator_window.py` només consumeix la sessió virtual. El seu seguiment,
registre de participants i esdeveniments són independents dels reals:
no canvia la càmera, el projecte, les assignacions musicals, els missatges
MIDI, el contingut públic, les fotografies ni els estats de Mute. El menú
normal de participants de la fase 1B continua mostrant el registre real.

Els esdeveniments de transició es dedupliquen, els historials són limitats,
el moviment no genera una aparició repetida i els camps invàlids o temps
no creixents no modifiquen parcialment el seguiment.

## Validació

**157 proves correctes, cap omesa**, amb Python 3.12, pantalla virtual Xorg i
les versions exactes de `requirements.txt`. `pip check` no detecta incompatibilitats.

```text
python -m unittest discover -s tests -v
```

Les proves noves cobreixen cinc identitats independents, moviment i gir,
ocultació i absència, avaria i recuperació, retirada explícita, reassignació,
duplicats, límit de cinc, camps i temps invàlids, reinici, memòria limitada,
paritat de seguiment amb fotogrames equivalents de càmera, arrossegament,
formulari, tancament/reobertura i cancel·lació dels dos temporitzadors.

La integració comprova que operar el simulador conserva exactament el
registre i el seguiment reals, les targetes, els missatges MIDI i els arrays
de fotogrames públics. Es mantenen les proves anteriors de càmera ArUco
sintètica, música, Mute, àudio MIDI, zones, fotografies, projectes i calibració.
També s’han revisat les dues pestanyes en pantalla virtual i el tancament
normal de tota l’aplicació.

## Instal·lació i següent increment

Cal copiar el paquet complet, inclosos `participant_simulator.py` i
`simulator_window.py`; el BAT general comprova que siguin presents. No hi ha
dependències noves ni migració de projectes. Per tornar a 4.7.6, recupera el
commit `c349ed2` i el projecte original.

La fase 3 adaptarà els esdeveniments de zones al flux comú. Aquesta entrega
no executa regles, accions de fotografia o so des del simulador, Kaoss ni
victòria/derrota: són increments posteriors. El mapa espacial, MIDI i visuals
actuals continuen funcionant per la seva ruta existent. La validació de
Windows, BAT i dispositius físics continua pendent a la instal·lació real.
