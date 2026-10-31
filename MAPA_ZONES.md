# Mapa de zones espacials — fases 1, 2, 3 i 4

## Abast real d'aquesta entrega

La fase 1 va afegir el motor independent `spatial_zones.py` i les seves proves. La fase 2, a **Wasteland 4.7.0**, afegeix `spatial_zone_editor.py`, integra la configuració a l'editor de targetes i incorpora el bloc espacial al desament/obertura de projectes. La resta de funcions existents es conserva. La fase 3, a **Wasteland 4.7.1**, connecta el motor en directe amb la projecció persistent mitjançant `spatial_projection.py`.

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

La fase 3 arbitra les ordres de zones i color confirmades; vegeu les regles de prioritat al final d’aquest document.

## JSON i imatges

`SpatialMap.to_dict()` i `from_dict()` serialitzen i validen la versió 1 del bloc espacial. `into_project(project)` retorna una còpia del diccionari amb el camp `spatial_zones`, preservant els altres camps; `from_project(project)` retorna un mapa buit si un projecte antic no té aquest camp. Es conserven quadrícula, zones, autoritzacions, imatges, calibració i opcions d'estabilitat. Els estats temporals de detecció i l'escena en curs no es desen: obrir un altre projecte crearà un motor nou.

**Des de la 4.7.0, `save_project()` / `open_project()` conserven el bloc espacial.** Els projectes antics s'obren amb un mapa buit. En fer Desar com, les rutes es recalculen respecte del nou fitxer de projecte mantenint la mateixa imatge d'origen; una ruta relativa no es resol mai assumint la carpeta de treball del procés.

`image_reference(image_file, project_file)` proposa una ruta relativa si la imatge és dins de la carpeta del projecte; per a imatges externes conserva una ruta absoluta. `check_image_asset(reference, project_file)` distingeix `not_assigned`, `unresolved`, `unsupported`, `missing`, `unreadable` i `exists`, sense carregar imatges. `exists` només comprova l'existència del fitxer, no que el seu contingut es pugui decodificar. Les rutes es resolen amb les regles del sistema operatiu on s'executa el programa.

En la fase 3, una imatge absent o corrupta genera un avís i conserva l’última sortida vàlida. La sol·licitud d'escena del motor no és una confirmació que la imatge s'hagi projectat.

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

2. **Completada a la 4.7.0:** editor gràfic i integració JSON. Vegeu les instruccions següents.
3. **Completada a la 4.7.1:** càrrega d’imatges amb memòria cau, proporcions preservades, errors i prioritat amb el color; previsualització amb guies i projecció neta.
4. **Captura implementada a la 4.7.2.** Queda pendent la prova amb la càmera i el terra físic de la instal·lació.

No s'ha afegit vídeo, OSC, múltiples projectors ni cap altra ampliació de la fase 5.

## Resultat de la validació de la fase 1

Han passat les 23 proves del motor espacial i les 41 proves existents del projecte: **64 executades, 64 correctes, cap omesa**. Les proves d'interfície antigues s'han executat amb Xvfb. No s'ha modificat el fitxer principal ni les dependències. Aquest resultat no valida una instal·lació física de la cúpula, un editor de zones encara inexistent ni fotografies en un projector real.

## Fase 2 — ús de l'editor (4.7.0)

Fitxers d’execució necessaris a la mateixa carpeta: el Python principal, `spatial_zones.py`, `spatial_zone_editor.py` i, des de la 4.7.1, `spatial_projection.py`. No s'han afegit dependències. L'accés d'arrencada existent continua servint.

1. Prem **ZONES ESPACIALS** a dalt, o selecciona **Activar zona espacial** com a funció de la targeta. En aquest segon cas, la targeta actual queda proposada per a una zona nova; no s'afegeix automàticament a una zona existent.
2. Prem NOVA ZONA. Fes clic o arrossega sobre el cercle per seleccionar caselles; tornar-hi a clicar les treu. Les caselles completament fora del cercle no es poden seleccionar.
3. Escriu un nom, marca les targetes autoritzades (01–16, equivalents als IDs 0–15) i, si vols, tria una imatge JPG/PNG. La miniatura es carrega només en triar o obrir aquella zona, no en cada moviment de ratolí. Si el fitxer falta o és corrupte es mostra un avís al lloc de la miniatura.
4. Prem **DESAR ZONA AL MAPA** per aplicar les dades. Per conservar-les al disc, desa després el projecte al menú Projecte. Una zona sense imatge o sense targetes autoritzades es pot preparar com a esborrany; encara no produeix cap escena.
5. Clica una zona de la llista per modificar-la, o prem ELIMINAR ZONA per retirar-la del mapa. Els solapaments entre zones habilitades es rebutgen, també si s'han seleccionat caselles mentre la zona estava deshabilitada.

Els canvis de formulari no aplicats no es desen silenciosament: l'aplicació demana aplicar-los abans de desar el projecte, i consulta abans de descartar-los en canviar de zona o projecte o en tancar. Tancar només la finestra de zones l'amaga i conserva el formulari en memòria.

L'avís **SENSE CALIBRACIÓ** continua visible quan no hi ha dades vàlides. Si es carrega un projecte amb una calibració matemàtica vàlida, encara s'indica que queda pendent validar-la físicament. La fase 4 incorpora la captura de punts de càmera, descrita a continuació.

La funció de zones no envia notes ni controls MIDI. Des de la fase 3, una entrada autoritzada i confirmada amb calibració vàlida activa la fotografia assignada i actualitza l’indicador de l’editor.

Validació de la fase 2: **72 proves executades i correctes**, incloses les 8 noves de l'editor i de rutes d'imatges. S'han comprovat creació/modificació/eliminació, agrupació, bloqueig de solapaments, miniatures absents/corruptes, projectes antics, rutes relatives, Desar com i conservació de les funcions musicals. La interfície s'ha provat amb pantalla virtual; queden pendents les proves a Windows i la instal·lació real de la cúpula.


## Fase 3 — projecció persistent (4.7.1)

Amb un projecte calibrat, assigna **Activar zona espacial** a la targeta i autoritza-la a les zones que hagi d’activar. Una entrada confirmada carrega la fotografia assignada. Quan la targeta surt o desapareix, la fotografia continua fins a una altra ordre visual. **TORNAR ALS VISUALS**, a l’editor de zones, permet deixar aquesta fotografia i recuperar els visuals en directe.

La previsualització mostra el cercle, la quadrícula, les zones, la posició i el recorregut recent de les targetes espacials calibrades. La projecció mostra només la fotografia, sense guies. La imatge conserva les proporcions amb franges negres quan cal, també en projectors amb una relació d’aspecte diferent. Les transparències es componen sobre negre i es respecta l’orientació EXIF. La gravació rep el fotograma net a la mida habitual del programa.

Prioritat:

- L’última entrada de zona confirmada substitueix la sortida anterior. Si coincideixen entrades de zones, guanya l’ID ArUco més baix.
- Una targeta cromàtica confirma una ordre en aparèixer o després de moure’s almenys 0,025 unitats normalitzades, amb tres deteccions i 0,15 segons. El marge de retorn és 0,0125; una interrupció superior a 0,25 segons reinicia la confirmació. Una targeta quieta no desplaça repetidament una fotografia nova.
- Si color i zona es confirmen al mateix fotograma, guanya la zona. Entre diversos colors simultanis guanya l’ID més baix.
- Quan desapareix el color que controla la sortida es recuperen els visuals en directe; no es reactiva automàticament una fotografia antiga. Una reentrada confirmada a una zona pot tornar a activar-la.
- Una targeta amb **Canviar visual**, amb un visual diferent del cromàtic, també recupera els visuals en directe quan apareix.

Una fotografia absent o malmesa mostra un avís i conserva la sortida anterior. Les imatges vàlides es descodifiquen només quan cal activar-les i es reutilitzen; les memòries cau estan limitades a quatre originals i quatre fotogrames redimensionats. Els originals es redueixen a un màxim de 4096×4096. Modificar el mapa reinicia la detecció i la memòria cau, conservant la fotografia actual; obrir un altre projecte esborra l’escena anterior.

**La captura gràfica de calibració està disponible des de la 4.7.2; vegeu les instruccions següents.** Sense calibració vàlida les zones no s’activen, i no s’assumeix que càmera i terra tinguin les mateixes coordenades. Les proves automàtiques utilitzen dades sintètiques o una calibració coneguda; no substitueixen la prova a Windows amb càmera i projector físics.

Validació de la fase 3: **86 proves correctes**, amb proves del motor, errors d’imatge, prioritat cromàtica, memòria cau, proporcions, transparència i integració amb la interfície en pantalla virtual. Es mantenen les proves existents de MIDI, àudio i funcions musicals.


## Fase 4 — captura de calibració (4.7.2)

Fitxer addicional necessari: `spatial_calibration.py`, al costat del principal i dels altres tres mòduls espacials. `OBRIR_WASTELAND.bat` és l’accés amb nom estable; l’accés anterior també continua funcionant.

1. Obre la càmera. Situa-la de manera fixa i identifica quatre referències físiques al perímetre del cercle del terra: nord, est, sud i oest. Són noms de referència del mapa, no cal una brúixola. Marca-les físicament per poder repetir la prova.
2. Obre **ZONES ESPACIALS → CALIBRAR TERRA**. La finestra mostra la imatge original de càmera sense mirall ni anotacions ArUco. Prem **CONGELAR IMATGE**.
3. Fes clic als quatre punts, en ordre nord, est, sud i oest. La selecció avança automàticament. Pots seleccionar qualsevol nom i tornar a clicar per corregir-lo. Els clics a les franges exteriors de la imatge s’ignoren. Els punts s’emmagatzemen normalitzats respecte de la imatge original, independentment de la mida de la finestra.
4. Prem **APLICAR CALIBRACIÓ**. Es rebutgen els punts incomplets, repetits, col·lineals, creuats o numèricament invàlids. La calibració anterior es conserva fins que s’aplica una captura vàlida. Si hi ha un formulari de zona pendent, es demana abans de descartar-lo.
5. Comprova al mapa la posició d’una targeta amb funció **Activar zona espacial** i autoritzada. Passa-la pel centre i per les zones; comprova que l’indicador segueixi el desplaçament. Desa el projecte per conservar la calibració.

**REPETIR CAPTURA** torna a la imatge en directe; no esborra la calibració ja aplicada. Una captura absent o de més d’un segon no es pot congelar. Canviar de projecte reinicia la captura; canviar de càmera, reobrir-la o canviar-ne la mida impedeix aplicar una captura antiga. Obrir un projecte recupera i valida els punts desats. Si mous la càmera o canvies la disposició física, torna a calibrar: el programa no pot detectar automàticament aquests moviments.

La captura no envia MIDI ni canvia les autoritzacions o les imatges de les zones. Les fotografies segueixen les regles persistents de la fase 3.

Validació 4.7.2: **93 proves correctes**, incloses 7 proves noves de captura, clics amb franges i redimensionament, correcció de punts, dades invàlides, captura caducada, canvi de context, conservació de dades i desament/obertura. Interfície revisada en pantalla virtual. La comprovació física de càmera, Sonar i projector a Windows continua pendent.

### Prova física proposada

Crea dues zones separades amb fotografies diferents i autoritza la mateixa targeta a totes dues. Comprova primer que el punt del mapa coincideixi amb la zona física. Mantén la targeta unes dècimes de segon a la primera zona: ha d’aparèixer la primera fotografia. Retira-la: la fotografia ha de continuar. Entra a la segona zona: ha de substituir-la per la segona. Una targeta no autoritzada no ha de canviar la fotografia. Si la posició no coincideix, revisa l’ordre dels quatre punts i torna a calibrar abans de retocar el mapa.


## Contorn circular de calibració (4.7.3)

A **CALIBRAR TERRA**, el desplegable **Contorn de referència** permet triar **Circumferència del domo** (per defecte) o **Quatre costats**. Mantén els quatre punts físics nord, est, sud i oest: la circumferència calculada passa per aquestes referències i es transforma a la perspectiva de la càmera. Pot aparèixer com una el·lipse a la fotografia. No és un dibuix lliure ni canvia la calibració o el terra circular del mapa; és una guia per comprovar el perímetre real. Si els quatre punts encara no són vàlids, no es dibuixa la circumferència. L’opció només afecta aquesta finestra, no afegeix contorns a la projecció.

### Una fotografia per casella

Cada zona té una fotografia. Per assignar una fotografia diferent a cada casella, crea una zona independent per casella: NOVA ZONA, selecciona una sola casella, dona-li nom, autoritza la targeta, tria la imatge i desa la zona. Repeteix-ho amb cada casella i desa el projecte. Pots autoritzar la mateixa targeta a diverses zones. Si selecciones quatre caselles en una mateixa zona, les quatre comparteixen la fotografia. Els efectes visuals per zona encara no estan implementats; les zones actuals activen fotografies JPG/PNG.

Validació 4.7.3: **95 proves correctes**, incloent el retorn de coordenades amb perspectiva i el canvi de contorn sense modificar els punts de calibració. Revisió visual del contorn circular en pantalla virtual.


## Durada de les fotografies (4.7.4)

A l’editor de zones, cada zona té un desplegable **Durada de la imatge**:

- **Mentre la targeta sigui a la zona**: en retirar la targeta que ha activat la fotografia, o en sortir de la zona, la projecció queda negra. S’aplica la tolerància de sortida configurada (0,20 s per defecte) per evitar parpelleigs per una detecció perduda.
- **Segons després de retirar-la**: la fotografia continua mentre la targeta és a la zona. Després de confirmar-ne la sortida comença el compte enrere dels segons indicats. La durada admet decimals amb coma o punt, de 0,1 a 86400 segons. Tornar a la zona cancel·la el compte enrere; una nova retirada el torna a iniciar. En acabar queda negre, sense recuperar automàticament una altra fotografia o visual antic.
- **Mantenir la imatge**: conserva el comportament persistent anterior, fins a una altra ordre visual o TORNA ALS VISUALS.

Les zones noves proposen el primer mode. Les zones dels projectes antics es carreguen com **Mantenir la imatge**, perquè no canviïn silenciosament: selecciona cada zona, tria el comportament desitjat, prem **DESAR ZONA AL MAPA** i desa el projecte. La calibració i les autoritzacions es conserven.

El seguiment correspon a la targeta que ha activat l’última fotografia. Una nova ordre de zona o color substitueix la sortida i cancel·la el temporitzador anterior; aquest no pot apagar una imatge nova. Canviar la mida del projector, fer una pausa visual o desar el projecte no reinicia el compte enrere. La previsualització pot continuar mostrant el mapa mentre la sortida del projector és negra.

Validació 4.7.4: **103 proves correctes**, amb proves noves de desaparició, tolerància de detecció, retorn abans del final, absència de caducitat mentre la targeta és visible, cancel·lació per una altra ordre, compatibilitat amb projectes anteriors, validació de segons i arribada del negre a la sortida de projecció. Revisió del formulari en pantalla virtual; queda pendent comprovar el comportament al projector físic.
