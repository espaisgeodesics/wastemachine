# ATMO ESFERA FX · Encàrrec de revisió i acabat visual

Preparat el 18 de novembre de 2026 per continuar el projecte en una altra conversa de ChatGPT.
Aquest document acompanya el codi complet. La tasca d’aquesta revisió és millorar el disseny, la claredat i els recursos gràfics del programa existent.

## 1. Petició del propietari

«Vull donar una estètica coherent i acabada a tot ATMO ESFERA FX, millorar les imatges i deixar el programa preparat per tancar el projecte. M’agrada la direcció del programa nou. No vull recuperar l’estètica del programa antic: totes les eines, incloses les del motor, han de tenir l’estètica ATMO.»

Treballa en català. Comença llegint el codi i aquest document. Presenta una proposta visual concreta, amb exemples de pantalles i recursos gràfics; una llista genèrica de consells no és suficient. Separa el que has observat al codi del que has pogut verificar executant-lo.

## 2. Versió i accés

- Producte: **ATMO ESFERA FX**. No reintroduir marques ni títols antics.
- Repositori: `espaisgeodesics/wastemachine` (el nom administratiu del repositori es manté).
- Branca de treball autoritzada: **`atmo/interficie-primera-integracio`**.
- Base funcional: **integració 18**, commit `dbfda481555b0633319d12e4ab7b85ca7f767b23`.
- Arrencada a Windows: **`OBRIR_ATMO.bat` → `py -3.12 atmo_esfera_fx_integracio_18.py`**.
- Tecnologia: Python, Tkinter/ttk, Pillow i OpenCV. MIDI amb mido/python-rtmidi i loopMIDI; ús amb Cakewalk i instruments en pistes separades.
- No modificar `main` ni la branca original del motor `codex/wasteland-camera-windows-launcher`.
- Si no tens connexió al repositori, treballa amb els fitxers adjunts. No pressuposis que pots llegir GitHub perquè hi hagi un enllaç.

El ZIP que acompanya el document és una còpia del repositori, sense historial Git. No cal obrir ni executar totes les versions antigues: l’entrada actual és la 18. El document s’afegeix com a material de revisió; no introdueix una nova versió del programa.

## 3. Direcció visual que cal consolidar

Volem una eina creativa d’espai, música, llum i audiovisuals: contemporània, immersiva, clara i cuidada. Ha de resultar fàcil treballar-hi durant estones llargues.

La interfície ATMO actual és fosca, amb blau nit i accents turquesa/lila. Aquests colors són el punt de partida real del codi, no un manual de marca definitiu:

| Ús actual | Color |
| --- | --- |
| Fons | `#0b1224` |
| Panells | `#16243d` |
| Superfícies i controls | `#203452` |
| Text principal | `#f5f7ff` |
| Text secundari | `#a8bad5` |
| Accent turquesa | `#45d4d2` |
| Accent lila | `#9b8cff` |

Proposa ajustos coherents si milloren el resultat. Evita tornar als marrons, marcs antics, capçaleres industrials o combinacions sense relació amb ATMO. No converteixis totes les accions en botons d’accent: defineix una jerarquia clara entre acció principal, secundària, perill, selecció i estat inactiu.

Cal revisar tipografia, marges, espaiat, contrast, icones, capçaleres, desplegables, pestanyes, barres de desplaçament, diàlegs, missatges, finestres auxiliars i barres de títol. El resultat ha de ser coherent també en els estats hover, focus, seleccionat, desactivat, error i càrrega.

## 4. Pantalles que cal revisar

1. **Inici / experiències:** Joc, Música, Exposició, Instal·lació immersiva. Millorar les quatre imatges/il·lustracions i l’equilibri de les targetes.
2. **Tria de projecte:** projecte nou, obrir projecte, plantilla, entrar a l’editor i tornar. Conservar el flux que ja existeix.
3. **Motor principal:** fer més clara la jerarquia i l’agrupació de les eines, sense eliminar funcions per motius estètics.
4. **Càmera i previsualització:** informació llegible, proporcions correctes i diferenciació de les targetes i mapes musicals.
5. **Editor de targetes i configuració de funcions:** mateix llenguatge visual per a harmonia, arpegiador, ritmes, MIDI, àudio, visuals i Ambients XY.
6. **Zones espacials, calibració i taula de volums:** controls ordenats, estat clar i bona visibilitat de les dades.
7. **Projector:** sortida audiovisual neta; no afegir-hi controls, logotips, marques de calibració ni textos de la interfície.
8. **Altres finestres:** àudio local, diagnosi MIDI, simuladors, participants i regles. Participants i regles només han d’aparèixer al menú de la modalitat Joc.

Eliminar textos provisionals o redundants que es detectin. Conservar els avisos necessaris per entendre un error o evitar perdre dades. Si una funció sembla sobrant, proposar-ne la retirada amb el motiu; no eliminar-la en una passada visual.

## 5. Imatges i recursos nous

Necessitem una família gràfica coherent, no quatre imatges sense relació. Proposa:

- Una imatge o il·lustració per a cada experiència: Joc, Música, Exposició i Instal·lació immersiva.
- Una direcció per a la identitat/capçalera ATMO i, si és útil, una pantalla d’inici més cuidada.
- Icones coherents per a les eines habituals.
- Una llista dels recursos a produir amb nom de fitxer, pantalla de destí, mides, proporció, transparència i tractament en pantalles petites.

Si pots generar imatges, lliura els fitxers utilitzables, a més dels exemples. Si no pots, lliura prompts de producció precisos. Evita posar textos dins de les imatges: els títols i botons s’han de continuar dibuixant com a elements de la interfície, nítids i editables. Preveu espais tranquils on hagi d’anar text.

Els recursos finals han de poder funcionar des de fitxers locals, sense connexió a Internet. Preveu PNG/JPEG i transparència PNG quan calgui; verifica qualsevol format o font addicional amb la tecnologia existent. Mantén la proporció de les imatges i una alternativa visual quan falti un fitxer.

El paquet de text local revisat no conté una biblioteca d’imatges originals ni un logotip vectorial aprovat. El motor té una referència a `capcalera_atmo_esfera_fx_460.png`, però l’adaptador ATMO actual dibuixa la capçalera amb text. Comprova els recursos que realment trobis al ZIP: no donis una ruta al codi per un fitxer existent ni presentis imatges inventades com si fossin originals aprovats. Si s’afegeixen originals més endavant, integra’ls respectant la direcció ATMO.

Si utilitzes recursos de tercers, indica’n procedència i llicència. Els nous recursos de la interfície han d’estar separats dels fitxers d’imatge, vídeo i so que tria l’usuari per als seus projectes.

## 6. Funcions que cal preservar

Aquest apartat és una llista de regressió, no una petició d’afegir més funcions:

- Arrencada amb `.bat` i Python 3.12; pantalla principal maximitzada.
- Motor principal visible i finestres auxiliars al davant quan s’obren; no obrir la previsualització automàticament a l’inici.
- Connexió MIDI/loopMIDI, diagnosi i ús amb pistes separades a Cakewalk.
- Editor de targetes, configuració específica de cada funció i opció **Visual assignat: Cap**.
- Mapes musicals simultanis diferenciats per targeta, amb notes i posició de l’arpegiador. Les guies són per a l’operador, no per al projector.
- Arpegiador configurable: nombre de notes, direcció, font de notes, octaves i tipus de mapa.
- Màster i nivell de cada targeta sonora; indicació de les targetes sense so. No alterar els canals MIDI amb una operació de disseny.
- **Chaos XY / Ambients** és un controlador d’efectes sobre instruments que ja sonen: no ha de crear notes. Reverb, eco, filtre, etc. depenen de les assignacions MIDI Learn/ACT del receptor; no és un processador de WAV locals.
- Imatges i vídeos assignats a targetes, amb fade in/fade out configurables i transicions. El vídeo actual no incorpora la seva pista d’àudio.
- Zones amb imatge i so, fades d’àudio i solapament de capes.
- Botó **CALIBRAR EL TERRA**. Cercle amb punts cardinals; quadrat/rectangle amb cantonades. Rectangle amb dimensions en la mateixa unitat.
- La previsualització adopta el contorn i la proporció calibrats. No reintroduir un selector de forma independent que contradigui la calibració.
- Mosaic només al projector: dues imatges en dues meitats, tres en tres franges i quatre en quadrants; proporció original de cada imatge.
- Projectes JSON i referències a mitjans existents. Abans de crear un projecte nou: desar, descartar o cancel·lar; si el desament falla o es cancel·la, no substituir el projecte.
- No presentar DMX com a implementat: l’usuari només ha plantejat per al futur una interfície USB-DMX i encara no disposa de l’equip.

## 7. Mapa del codi: per on començar

| Fitxer | Responsabilitat |
| --- | --- |
| `OBRIR_ATMO.bat` | Llançador Windows actual. |
| `atmo_esfera_fx_integracio_18.py` | Entrada actual, selecció d’experiència/projecte i obertura del motor. |
| `atmo_runtime.py` | Paleta, estils ttk, tematització i adaptador de presentació. Important: alguns mètodes del motor queden substituïts aquí. |
| `atmo_primary.py` | Motor com a finestra principal, arrencada i propietat/visibilitat de les finestres auxiliars. |
| `atmo_windows.py` | Maximització i intent de barra de títol fosca nativa a Windows. |
| `atmo_esfera_fx_4_5_15_pas_15_editor_musical_desplegable.py` | Motor actual: menús, panells, editor, taula de volums, projecte, càmera i connexió de funcions. El nom tècnic no determina l’estètica que s’ha de conservar. |
| `atmo_esfera_fx_integracio_12.py` | Components ATMO compartits, inclòs `AtmoZoneEditor`, encara importats per l’entrada 18. No és codi prescindible pel fet de dir «12». |
| `spatial_zone_editor.py`, `spatial_calibration.py` | Edició de zones i calibració. |
| `atmo_preview.py` | Mapa de l’operador, etiquetes i superposicions musicals. |
| `atmo_projection_mosaic.py`, `spatial_projection.py` | Composició i distribució d’imatges al projector. |
| `card_media_editor.py`, `card_media.py` | Selector d’imatges/vídeos i transicions. |
| `atmo_card_functions.py`, `atmo_ambience.py` | Configuració i encaminament d’Ambients XY. |
| `atmo_music.py`, `atmo_mixer.py`, `zone_audio.py` | Comportament musical, volums i àudio de zones: preservar-ne la lògica. |
| `audio_window.py`, `rule_editor.py`, `participant_editor.py`, `simulator_window.py` | Altres interfícies que també necessiten coherència. |
| `tests/` | Proves de regressió. |
| `ATMO_ESFERA_FX_INTEGRACIO_17.md`, `ATMO_ESFERA_FX_INTEGRACIO_18.md` | Detall dels darrers canvis i limitacions. |

Inspecciona el conjunt d’adaptadors abans de canviar un estil: editar només el motor pot no modificar el que veu l’usuari. Evita duplicar una paleta nova en cada finestra. Proposa centralitzar els estils en la mesura necessària, sense reescriure el motor ni migrar a una altra biblioteca gràfica com a part d’aquest acabat visual.

## 8. Què espero rebre de la revisió

Primer lliura:

1. Diagnosi breu i prioritzada dels problemes visuals reals, amb pantalla/fitxer afectat.
2. Una proposta ATMO coherent: paleta, tipografia, jerarquia, espaiat, botons, icones i estats.
3. Exemples visuals d’Inici, Motor principal i Editor de targetes. Identifica’ls com a propostes, no com a captures de l’aplicació executada.
4. Proposta de les quatre imatges d’experiència, amb fitxers o prompts i especificacions de producció.
5. Pla curt de canvis per aplicar el disseny de manera consistent a totes les finestres, indicant què afecta només presentació i què podria afectar comportament.

Una vegada acordada la proposta visual, la implementació ha de lliurar recursos locals i canvis concrets revisables, amb una guia d’arrencada clara. No cal afegir funcions noves ni crear una instal·lació nova per fer una revisió estètica.

## 9. Validació i límits coneguts

A la integració 18 s’han executat 408 proves: 327 passen i 81 s’ometen perquè requereixen pantalla gràfica. La versió 17 va rebre confirmació de funcionament per part de l’usuari. La 18 s’ha lliurat amb els canvis de terra, projecte i mosaic; aquest document no afirma una validació visual completa a Windows de la 18.

El codi permet revisar estructura i colors, però no substitueix veure les finestres reals. Si no hi ha captures actuals, fes explícita aquesta limitació; pots començar igualment amb el codi i les propostes. Per validar el resultat final convé contrastar Inici, Projecte, Motor, Editor, Zones, Calibració, Volums i configuracions, amb finestres de mida diferent i escalat de Windows del 100%, 125% i 150%.

Comprova que no es tallen etiquetes o botons, que les finestres es poden redimensionar, que els controls importants continuen accessibles, que el contrast i el focus de teclat són clars i que el projector es manté net. Les proves existents s’han de seguir executant, però una suite verda no acredita per si sola que el disseny es vegi bé.
