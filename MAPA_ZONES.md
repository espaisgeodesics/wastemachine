# Mapa de zones espacials — fase 1

## Abast real d'aquesta entrega

S'afegeixen exclusivament `spatial_zones.py`, `tests/test_spatial_zones.py` i aquest document. El programa principal continua sent **Wasteland 4.6.3**: no s'ha canviat cap funció MIDI, Mute, harmonia, arpegiador, càmera, finestra o projecció. El motor encara **no està connectat al programa**; no hi ha editor gràfic de zones ni opció «Activar zona espacial» al desplegable en aquesta fase. No cal actualitzar el Python principal al PC per aquesta entrega.

El motor produeix esdeveniments i sol·licituds d'escena. No obre una càmera, no envia MIDI, no carrega ni dibuixa fotografies i no executa vídeo. L'estat persistent d'una escena aquí és una referència d'imatge; la càrrega, validació real i presentació de la imatge són tasques de la fase de projecció.

## Coordenades i dades

- Terra normalitzat: quadrat `[0,1] × [0,1]`, amb cercle de centre `(0.5,0.5)` i radi `0.5`. X creix cap a la dreta i Y cap avall.
- `Grid` és 8×8 per defecte. Les caselles són `(fila, columna)`, començant per zero. S'accepten les caselles parcialment dins del cercle; les completament exteriors o només tangents sense superfície útil es rebutgen. Una posició realment fora del cercle no activa res.
- Els límits interns exactes pertanyen a la casella de la dreta o de sota. Els extrems 1.0 pertanyen a l'última fila/columna. S'absorbeix l'error numèric diminut de la transformació als límits; això no substitueix la histèresi física.
- `Zone` té `id`, `name`, `cells`, `authorized_cards`, `image_path` i `enabled`. Els IDs ArUco són **0–15**: la targeta 05 és ID 4. Noms i identificadors són obligatoris; una zona necessita com a mínim una casella. Una llista de targetes autoritzades buida no n'autoritza cap.
- Les zones habilitades no poden compartir caselles. Els esborranys deshabilitats poden solapar-se, però no s'activen. No s'accepten IDs duplicats, caselles fora del mapa ni formats diferents de JPG/JPEG/PNG. No s'implementa vídeo.

## Calibració

`Calibration` calcula una homografia a partir de quatre parelles de punts. Les coordenades de càmera també són normalitzades: `(centre_x / amplada, centre_y / alçada)`, com les que calcula el detector actual. No s'han de passar píxels directament.

Per defecte els punts de terra són **nord, est, sud i oest**, respectivament `(0.5,0)`, `(1,0.5)`, `(0.5,1)`, `(0,0.5)`. Les quatre coordenades de càmera han de correspondre a aquestes mateixes referències físiques fixes i en aquest ordre; no s'ordenen automàticament segons l'aspecte de la imatge. També es poden proporcionar altres quatre punts de terra coneguts en ordre de perímetre, per exemple els vèrtexs d'un quadrat de referència.

Es rebutgen punts fora del rang, repetits, col·lineals, no convexos, mal condicionats o que introdueixin un horitzó projectiu dins del terra circular. Una calibració guardada es reconstrueix i valida a partir dels punts, no d'una matriu JSON acceptada a cegues.

`update_camera(observations, now)` només permet activar zones si hi ha una calibració vàlida. Sense ella retorna `status='uncalibrated'`, sense esdeveniments ni cap transformació identitat implícita. `update_normalized(...)` és una API **explícita de simulació/proves**, amb coordenades de terra ja normalitzades; no és una alternativa de calibració per a la instal·lació real. Les dues API esperen un temps monotònic en segons i creixent estrictament entre fotogrames.

L'homografia pressuposa terra pla i quatre referències ben mesurades. No corregeix la distorsió de lent, el moviment de la càmera o una mala identificació dels punts. La configuració visual i la validació física de la cúpula queden pendents de les fases següents.

## Confirmació d'entrades i sortides

Cada crida conté **totes** les targetes observades en aquell fotograma. Les que no hi són es consideren absents; enviar un diccionari buit comunica un fotograma sense targetes.

Valors inicials de `Stabilization`:

| Opció | Valor | Efecte |
|---|---:|---|
| `enter_delay_s` | 0,15 s | Temps mínim amb la mateixa zona candidata. |
| `min_detections` | 3 | Deteccions consecutives mínimes per confirmar l'entrada. |
| `exit_delay_s` | 0,20 s | Tolerància temporal per confirmar una sortida o desaparició. |
| `hysteresis` | 0,01 | Marge de terra normalitzat al voltant de les caselles de la zona ja confirmada. |
| `max_detection_gap_s` | 0,20 s | Una interrupció llarga obliga a estabilitzar de nou la detecció. |

Cal complir tant el temps d'entrada com el nombre de deteccions. Una detecció intermèdia absent o en una altra zona interromp la candidatura. Moure's entre caselles de la mateixa zona no genera entrades noves. La histèresi conserva la zona anterior mentre la posició encara sigui al seu marge; el filtre temporal estabilitza el canvi quan ja s'ha superat aquell marge.

El motor conserva la zona actual confirmada i l'última zona d'entrada de cada targeta per separat. `confirmed_zone(id)` retorna la zona actual o `None`; `last_entered_zone(id)` conserva l'última entrada fins i tot després de sortir-ne.

## Escena persistent i prioritat

`FrameResult` conté `events`, `scene`, `scene_changed` i `image_changed`, a més de l'estat de l'entrada. Els esdeveniments són `enter` i `exit`; les sortides indiquen si s'han produït per moviment, absència o una interrupció de detecció.

Una entrada autoritzada i confirmada en una zona amb imatge produeix una sol·licitud d'escena. Sortir de la zona, travessar un espai buit, desaparèixer o detectar una targeta no autoritzada **no esborra l'escena**. Una zona sense imatge pot registrar l'entrada, però no substitueix l'escena anterior.

No s'emet una entrada per cada fotograma. Una reentrada a la mateixa escena genera un esdeveniment nou i actualitza la seva informació de targeta/temps, però no marca recàrrega d'imatge. Canviar entre dues zones que utilitzen exactament la mateixa referència d'imatge canvia la zona activa amb `scene_changed=True`, però manté `image_changed=False`.

Les entrades de diferents fotogrames segueixen l'ordre de confirmació: l'última és la més recent. Si diverses targetes confirmen entrades amb imatge **al mateix fotograma**, guanya l'ID ArUco més baix, independentment de l'ordre de detecció. Es retornen els esdeveniments de totes les targetes per permetre mostrar-los a l'editor.

La prioritat entre color cromàtic i escena de zona encara no s'implementa: arribarà amb la integració de projecció. Caldrà un àrbitre d'ordres visuals confirmades; un fotograma de color actualitzat contínuament no ha de desfer una ordre de zona només per executar-se després al bucle.

## JSON i imatges

`SpatialMap.to_dict()` i `from_dict()` serialitzen i validen la versió 1 del bloc espacial. `into_project(project)` retorna una còpia del diccionari amb el camp `spatial_zones`, preservant els altres camps; `from_project(project)` retorna un mapa buit si un projecte antic no té aquest camp. Es conserven quadrícula, zones, autoritzacions, imatges, calibració i opcions d'estabilitat. Els estats temporals de detecció i l'escena en curs no es desen: obrir un altre projecte crearà un motor nou.

**Aquest còdec encara no modifica `save_project()` / `open_project()` del programa.** No afegeixis el bloc manualment al teu projecte habitual esperant que el Wasteland actual el conservi: el seu desament encara no incorpora zones. La integració dels camps es farà en connectar l'editor al programa.

`image_reference(image_file, project_file)` proposa una ruta relativa si la imatge és dins de la carpeta del projecte; per a imatges externes conserva una ruta absoluta. `check_image_asset(reference, project_file)` distingeix `not_assigned`, `unresolved`, `unsupported`, `missing`, `unreadable` i `exists`, sense carregar imatges. `exists` només comprova l'existència del fitxer, no que el seu contingut es pugui decodificar. Les rutes es resolen amb les regles del sistema operatiu on s'executa el programa.

En la fase de projecció, una imatge absent o corrupta haurà de generar un avís i conservar l'última escena realment carregada. La sol·licitud d'escena del motor no és una confirmació que la imatge s'hagi projectat.

## Exemple executiu sense càmera

```python
from spatial_zones import SpatialMap, SpatialEngine, Zone

config = SpatialMap(zones=(
    Zone('bosc', 'Bosc', {(3, 2), (4, 2)}, {4}, 'imatges/bosc.jpg'),
    Zone('desert', 'Desert', {(3, 5)}, {4}, 'imatges/desert.jpg'),
))
engine = SpatialEngine(config)
for now in (0, .08, .16):
    result = engine.update_normalized({4: (.3, .45)}, now)
assert result.scene.zone_id == 'bosc'
engine.update_normalized({}, .24)
result = engine.update_normalized({}, .45)
assert result.scene.zone_id == 'bosc'  # La retirada no esborra l'escena.
for now in (.53, .61, .69):
    result = engine.update_normalized({4: (.7, .45)}, now)
assert result.scene.zone_id == 'desert'
```

Proves independents de càmera, Tkinter i MIDI:

```text
python -m unittest discover -s tests -p test_spatial_zones.py -v
```

## Fases pendents

2. Editor gràfic de caselles, noms, autoritzacions, imatges i configuració des de les targetes; integració del bloc JSON amb el programa.
3. Càrrega d'imatges amb memòria cau, proporcions preservades, gestió d'errors i prioritat amb el color; previsualització amb guies i projecció neta.
4. Captura dels punts de calibració i proves amb la càmera i el terra físic.

No s'ha afegit vídeo, OSC, múltiples projectors ni cap altra ampliació de la fase 5.

## Resultat de la validació d'aquesta entrega

Han passat les 23 proves del motor espacial i les 41 proves existents del projecte: **64 executades, 64 correctes, cap omesa**. Les proves d'interfície antigues s'han executat amb Xvfb. No s'ha modificat el fitxer principal ni les dependències. Aquest resultat no valida una instal·lació física de la cúpula, un editor de zones encara inexistent ni fotografies en un projector real.
