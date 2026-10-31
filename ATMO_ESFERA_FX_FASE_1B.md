# ATMO ESFERA FX — fase 1B

Entrega: **Wasteland Machine 4.7.6**, sobre la base 4.7.5, commit
`53393a81208c3097bd08a7b7139b9df03d3e1340`, branca
`codex/wasteland-camera-windows-launcher`.
Continua l’[auditoria](ATMO_ESFERA_FX_AUDITORIA.md) i la
[fase 1A](ATMO_ESFERA_FX_FASE_1A.md). Es conserven el fitxer principal,
els accessos BAT i les funcions musicals i visuals.

## Ús

1. Obre **Participants → Registre i seguiment…**, una finestra de l’operador.
2. Escriu el nom o àlies (opcional), tria un color i indica la font i l’ID ArUco.
   La font proposada és la càmera seleccionada: `camera:0`, `camera:1`, etc.
   **ID ArUco 0 correspon a la targeta 01**, fins a ID 15 / targeta 16.
3. Prem **APLICAR PARTICIPANT**. **NOU** prepara una altra vinculació i proposa
   el primer ID lliure d’aquella font. Pots registrar cinc persones amb IDs 0–4.
   No es creen persones automàticament a partir dels noms musicals de targeta.
4. Selecciona una fila per canviar nom, color o marcador i torna a aplicar.
   La persona conserva l’identificador intern encara que canviï el marcador.
   Una parella `(font, ID)` només pot pertànyer a una persona; els duplicats
   es rebutgen sense modificar el registre. Els noms poden coincidir.
5. Desa el projecte per conservar el registre. El desament avisa si hi ha canvis
   de formulari pendents d’aplicar. Obrir/crear un projecte, canviar de fila o
   tancar la finestra comproven si cal descartar aquests canvis.

La taula mostra presència i última posició **normalitzada de càmera**, amb
«antiga» quan no és una observació actual. No és una coordenada calibrada
de terra ni dels peus. El color identifica la persona a la finestra de
l’operador: **no ordena un color a la projecció**.

La font té un diagnòstic propi. Una càmera no disponible no és una imatge vàlida
sense marcadors. Les pèrdues i avaries no eliminen ningú. **RETIRAR** i
**RECUPERAR** són ordres explícites de sessió: conserven la vinculació i no
retiren el marcador del detector ni aturen la funció MIDI/visual de la targeta.
Una detecció nova no desfà una retirada de persona. **ELIMINAR**, amb confirmació,
elimina la vinculació del registre i allibera el marcador, sense canviar la targeta.

## Model i esdeveniments

- `participants.py`: `ParticipantBinding`, `ParticipantState` i
  `ParticipantRegistry`. Identitat interna, nom, color `#RRGGBB` i vinculació
  a `(source_id, marker_id)`. Instantànies immutables; màxim 64 participants,
  coherent amb les quatre fonts de seguiment per defecte.
- `domain_events.py`: `DomainEvent` immutable i `CommonEventLog` passiu.
  Seqüència pròpia, temps monotònic, tipus, font i, quan pertoca, seqüència del
  fotograma, marcador i participant vinculat en aquell moment. Reassignar una
  persona no reescriu els esdeveniments anteriors.
- `participant_editor.py`: formulari, colors, seguiment a 4 Hz i els últims
  30 esdeveniments. Cancel·la el temporitzador en destruir la finestra.

Esdeveniments: `source_available`, `source_unavailable`, `marker_appeared`,
`marker_recovered`, `marker_temporarily_lost`, `marker_absent`, `marker_retired`
(API física de desenvolupament), `participant_retired` i `participant_restored`.
S’emet una transició una sola vegada, sense repetir-la a cada fotograma immòbil.
Els IDs es processen en ordre estable; tots els esdeveniments d’un fotograma
es retornen junts, encara que el lot superi el límit de l’historial.
El registre conserva com a màxim 500 entrades. Els marcadors sense participant
també generen esdeveniments, amb `participant_id=None`.

La pèrdua breu produeix pèrdua temporal i recuperació. L’absència només es
confirma amb una imatge vàlida, segons el llindar del seguiment (un segon per
defecte). Una avaria de font no confirma l’absència ni aplica penalitzacions.
La retirada de persona és independent de la presència del marcador.

L’observador comparteix el fotograma de la fase 1A, sense rellegir la càmera ni
repetir el detector. Els errors es contenen al diagnòstic limitat existent.
No executa accions MIDI, canvis visuals o regles de joc.

## Projectes i recuperació

El JSON conserva `version: 4` i el bloc espacial; afegeix:

```json
{
  "participants": {
    "schema_version": 1,
    "bindings": [
      {
        "participant_id": "identificador-intern-estable",
        "name": "Laia",
        "color": "#00CC88",
        "source_id": "camera:0",
        "marker_id": 0
      }
    ]
  }
}
```

Els projectes antics sense aquest bloc obren amb un registre buit. La lectura
valida camps, versió, límits, IDs i assignacions duplicades abans de modificar
el projecte o enviar MIDI. `Desar com` conserva identitats, noms i colors.
No es serialitzen presència, retirada de sessió, posicions, historial, rellotges
o esdeveniments. Crear/carregar un projecte reinicia el registre d’esdeveniments
i la retirada de sessió; el seguiment continua informant de la càmera actual.

No es migren ni sobreescriuen fitxers automàticament. Conserva el projecte
original de 4.7.5 i desa el nou amb un altre nom. La versió antiga no coneix
el bloc de participants i pot perdre’l si hi tornes a desar el projecte nou.

Copia el paquet complet: `participants.py`, `domain_events.py` i
`participant_editor.py` han d’estar al costat del principal i dels mòduls
anteriors. El BAT general en comprova la presència. No hi ha dependències noves.

## Validació i límits

**141 proves correctes, cap omesa**, amb Python 3.12, pantalla virtual Xorg i
les versions de `requirements.txt`: NumPy 2.5.4, OpenCV headless 5.0.0.93,
Pillow 13.0.0, Mido 1.3.3 i python-rtmidi 1.5.8. Les 120 proves de la base
4.7.5 també s’han executat abans de modificar el programa: totes correctes.

```text
python -m unittest discover -s tests -v
```

Les proves noves cobreixen identitat/reassignació, duplicats, camps invàlids,
límits, instantànies immutables, pèrdua, avaria, retirada, recuperació,
esdeveniments ordenats i deduplicats, formulari, colors, tancament/reobertura,
projectes antics/nous i rebuig de configuracions invàlides sense modificar
el projecte actual ni enviar MIDI.

La integració compara **els mateixos missatges MIDI i arrays dels fotogrames
públics** amb cinc ArUco sintètics, l’observador activat/desactivat, cinc
participants registrats i un de retirat. També injecta errors al seguiment
i al registre d’esdeveniments. Es mantenen les regressions de música, Mute,
àudio MIDI, visuals, zones, fotografies i calibració.

El simulador visible correspon a la fase 2 i l’adaptació dels esdeveniments
de zona al flux comú a la fase 3: les zones continuen pel camí existent.
No s’ha implementat joc, regles d’accions, àudio local, compensació d’alçada
o canvi de marca. Windows, BAT, càmera, barrets, projector, loopMIDI i Sonar
físics necessiten una prova a la instal·lació real.
