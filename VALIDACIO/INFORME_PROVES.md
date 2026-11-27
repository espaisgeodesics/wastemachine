# Informe de proves · ATMO ESFERA FX 19 · Atmosfera viva

Base: ZIP V3 de l’usuari. Branca exclusiva `atmo/interficie-primera-integracio`.

## Resultats verificats

| Comprovació | Resultat |
| --- | --- |
| Compilació `python -m compileall -q .` | Correcta |
| Suite `python -m tools.provar_tests`, Linux amb pantalla Xvfb i SDL dummy | **417 proves, 417 correctes, 0 errors, 0 omissions** |
| Captures amb finestres Tk reals, escales de font 100%, 125%, 150% | 90 captures, sense excepcions; vegeu el JSON de cada entorn |
| Quatre imatges inicials aprovades | SHA-256 idèntics al ZIP V3; prova automàtica |
| WAV de 35 segons en dos canals locals | Lectura per fragments, reproducció SDL i aturada independent correctes |
| WAV float, bucle i final natural | Correctes amb SDL dummy |
| Targeta dins una zona mentre el dispositiu s’activa | La reproducció comença en estar el dispositiu disponible |
| MIDI físic, loopMIDI, Cakewalk, altaveus i projector real | No disponibles en aquest entorn |
| Windows Server 2025, Python 3.12.10, Tk 8.6.15 i Segoe UI | **417 proves correctes, 0 errors, 0 omissions; compilació i 90 captures correctes** |

Els registres reals de Linux són a `logs/`. S’ha utilitzat el runner propi del projecte perquè força la recollida d’objectes Tk al fil principal. No s’han detectat excepcions de callbacks al registre final.

## Regressions corregides

- Esdeveniments de mapatge que arriben com una ruta Tcl en lloc d’un widget Python: el tema ja no intenta cridar-hi `winfo_class`.
- Duplicació de bindings del tema: instal·lació idempotent.
- Fonts amb nom compost a la base d’opcions Tk; es preserva la mida demanada.
- Imatges Pillow associades a l’intèrpret Tk equivocat en obrir/tancar finestres: ara tenen un `master` explícit.
- Temporitzadors de prova cancel·lats amb un propietari Tk incorrecte: s’evita eliminar dues vegades les ordres Tcl.
- Camps clàssics amb text negre sobre un fons fosc i controls que mantenien la paleta anterior.
- Controls d’aplicar que quedaven tallats, especialment a calibració; barres d’eines massa amples i desplaçament vertical absent a Volums.
- La pantalla inicial conserva les quatre imatges grans i reserva espai per als títols i botons, evitant que la mida de la foto els expulsi de la finestra.
- Recuperació d’interrupcions breus de SDL entre fragments a Windows: la cançó continua sense perdre la capa.
- Proves de rutes compatibles amb el nom curt i llarg de les carpetes Windows; doble de finestra complet i rellotge virtual estrictament creixent a les proves.
- Menú principal fosc que reutilitza les mateixes ordres i manté l’accés de teclat.
- Desar noms o visuals sense canviar de canal ja no envia una ràfega innecessària de volums MIDI.

## Incidència dels WAV

El reproductor anterior només admetia clips de 30 segons i 16 MiB, i el dispositiu podia continuar desactivat. L’editor permetia seleccionar cançons sense fer evident aquesta limitació. Ara es llegeixen les cançons llargues per fragments de 0,5 segons, mantenint les capes independents i la memòria acotada. Hi ha activació, prova, aturada i estat visibles a Zones. Aplicar explícitament una zona sonora sol·licita l’activació si el dispositiu era desactivat.

L’extensió WAV per si sola no garanteix un fitxer vàlid. Un fitxer corrupte, un dispositiu no disponible o un complement no instal·lat es comunica a l’estat / registre; no es presenta com a reproducció correcta. Les comprovacions SDL dummy proven descodificació, canals i ordres, **no que s’hagi sentit so pels altaveus de l’usuari**.

## Captures i abast visual

Les captures Linux mostren l’aplicació executada, amb finestres obertes mitjançant les seves accions reals. Les posicions del mapa de demostració són sintètiques. Les fonts de Linux fan servir Helvetica/Nimbus Sans com a substitut del sistema; el programa conserva **Segoe UI a Windows**. No hi ha barres de títol de Windows en aquestes captures.

Les escales es generen amb `tk scaling`; no acrediten per si soles el comportament del DPI per monitor de Windows. Es lliuren captures d’inici/projecte, motor, càmera, visual, targetes, MIDI, volums, harmonia, arpegiador, patrons, bateria, Ambients XY, visuals de fitxer, àudio MIDI, CC, Mute, nota, zones, calibració, àudio local, diagnosi, participants, regles, simulador i projector.

## Validació nativa de Windows

Execució final: [GitHub Actions 44416544196](https://github.com/espaisgeodesics/wastemachine/actions/runs/44416544196), sobre codi `7526303a6c09b36771ead51e90e5988216e57c1a`. Totes les fases han acabat correctament. `CI_WINDOWS.json` n’identifica el commit i l’artefacte. La primera execució va detectar diferències de camins curts/llargs, dobles incomplets de finestres i rellotge de proves, i una interrupció SDL entre fragments; s’han corregit i s’ha repetit la suite fins a obtenir el resultat verd final.

S’han revisat captures natives, incloses Inici al 150%, Motor, Targetes, Zones/So, Calibració, Ambients, Àudio i Regles. S’ha corregit el retall del botó llarg d’entrada i s’ha afegit desplaçament a l’espai central del motor. La barra de menú reutilitza les ordres originals amb presentació ATMO fosca.

El servidor Windows de CI té una pantalla petita: s’hi ha comprovat que els formularis disposen de desplaçament i que les accions d’aplicar són accessibles. Segoe UI hi està disponible. L’escalat es prova amb `tk scaling` a 100/125/150%; el DPI per monitor del Windows 10 concret de l’usuari continua requerint verificació al seu equip.

## Pendent de l’equip real

- Escolta del WAV de l’usuari amb la seva sortida d’àudio seleccionada a Windows; possible ús exclusiu del dispositiu per un altre programa.
- loopMIDI/Cakewalk amb les pistes i assignacions MIDI reals.
- Càmera i calibració del terra físic, projecció i vídeos amb els còdecs de l’ordinador.
- DPI per monitor i barres de títol natives de la versió concreta de Windows.

No hi ha errors coneguts de les suites finals Linux i Windows. Els punts d’equip real es mantenen pendents i no es marquen com a validats.

## Fitxers lliurats

- `CAPTURES_I_PROVES_WINDOWS.zip`: les 90 captures natives, el registre Windows i les dependències. Descomprimeix-lo dins de `VALIDACIO/windows/` per veure cada imatge.
- `CAPTURES_LINUX.zip`: les 90 captures Linux i metadades. Descomprimeix-lo dins de `VALIDACIO/`.
- `RESUM_VISUAL_WINDOWS.png` i `RESUM_VISUAL_LINUX.png`: fulls de contacte per consultar ràpidament les pantalles.
- `logs/`: registres de les suites finals i compilació.
- `FITXERS_MODIFICATS.md`: relació respecte del ZIP V3.
