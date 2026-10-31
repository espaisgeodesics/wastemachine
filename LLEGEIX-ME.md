# Wasteland Machine

**Versió actual: 4.7.5.** Extreu tot el paquet: al costat del principal calen `spatial_zones.py`, `spatial_zone_editor.py`, `spatial_projection.py`, `spatial_calibration.py`, `marker_tracking.py` i `aruco_observations.py`. No calen dependències noves.

La [fase 1A d’ATMO ESFERA FX](ATMO_ESFERA_FX_FASE_1A.md) afegeix seguiment passiu de marcadors; les funcions musicals i visuals continuen pel camí actual. El simulador visible de cinc participants encara no està implementat. Les instruccions actuals de zones, calibració i durades són a [MAPA_ZONES.md](MAPA_ZONES.md).

## Obrir-lo a Windows

1. Instal·la **Python 3.12 de 64 bits** des de https://www.python.org/downloads/windows/. Inclou els components Python Launcher i Tcl/Tk (normalment seleccionats per defecte).
2. Extreu **tot** el ZIP en una carpeta del teu ordinador. No l'executis des de dins del ZIP.
3. Fes doble clic a **OBRIR_WASTELAND.bat**. La primera vegada necessita Internet per instal·lar les biblioteques. Les següents vegades comprova les dependències i obre el programa.
4. Les finestres de càmera, visuals, MIDI i editor s'obren per separat. Si alguna queda fora de pantalla, utilitza **Projecte → Restablir distribució inicial**.

Per tornar-hi, fes doble clic al mateix fitxer BAT. No es necessita cap compte ni clau API. El programa s'executa al teu ordinador; aquest paquet no crea un accés web.

## Comprovar-lo

- Sense càmera ni MIDI, comprova l'editor i els visuals. Si apareix un diagnòstic MIDI, tanca l'avís per continuar sense MIDI.
- Obre la càmera amb el botó corresponent. Permet-ne l'accés a la configuració de privadesa de Windows i tanca altres aplicacions que la facin servir.
- Els marcadors són **ArUco DICT_4X4_50, ID 0–15**, corresponents a les targetes 1–16.
- Per enviar MIDI a Cakewalk, crea un port virtual amb loopMIDI, selecciona'l al Wasteland i habilita'l com a entrada MIDI a Cakewalk. Aquests programes es configuren separadament.
- Desa el treball amb **Projecte → Desar projecte**. Els projectes són fitxers JSON; conserva'ls i fes-ne còpies de seguretat. Els vídeos es desen a GRAVACIONS.

Quan demanis un canvi, indica què has fet, què esperaves i què ha passat. Pots adjuntar una captura o copiar els errors de la consola.

## Estat de la revisió

S'ha revisat la versió Pas 15. S'ha corregit la selecció del sistema de captura segons la plataforma i l'aturada de notes en tancar o perdre la càmera. Pas 14 es conserva com a versió anterior.

Validació al núvol amb Python 3.12 i pantalla virtual: arrencada de totes dues versions, dotze visuals, cercle cromàtic, projecció i detecció ArUco sintètica. Hi ha proves automatitzades per als canvis de càmera a tests/.

La càmera física, MIDI/Cakewalk i el llançador BAT necessiten comprovació al teu Windows; aquí no es disposa d'aquests dispositius ni d'aquest sistema operatiu. No s'ha fet una auditoria exhaustiva de totes les funcions.

## Desenvolupament

La versió actual és wasteland_4_5_15_pas_15_editor_musical_desplegable.py. Amb Python 3.12, crea un entorn virtual, instal·la requirements.txt i executa aquest fitxer des d'un escriptori amb Tkinter. OpenCV headless és suficient perquè les finestres les dibuixa Tkinter.

Proves: `python -m unittest discover -s tests -v`.

## Simulació, silenci i patrons

- Els controls de simulació amb ratolí i gir ja no apareixen a la previsualització. Es conserven mètodes interns de prova; el simulador de diversos participants arribarà en una fase pròpia.
- **SILENCI ABSOLUT** atura les notes, allibera el pedal de sustain i envia All Sound Off i All Notes Off als 16 canals de la sortida MIDI connectada. També bloqueja noves activacions fins a prémer **REPRENDRE MIDI**. No silencia pistes d'àudio o instruments que no rebin aquesta sortida MIDI.
- En seleccionar **Arpegiador espacial**, el menú s’obre i pots triar Ascendent, Descendent, Pujada i baixada o Aleatori. Es conserven la divisió rítmica, durada, escala i intensitat.
- La funció **Patró rítmic** ofereix 16 passos repetits. Activa els cops a la configuració musical; la nota i el canal es trien a l'editor de la targeta. La divisió 1/4 temps equival a semicorxeres: 16 passos formen un compàs de 4/4. El patró segueix el rellotge intern i comença a la fase actual de la graella quan detecta la targeta; s'atura en retirar-la. No hi ha sincronització externa amb Cakewalk en aquesta versió.
- Per a bateria General MIDI, pots assignar targetes diferents a bombo (nota 36), caixa (38) i hi-hat (42), normalment al canal 10; depèn de l'instrument receptor. La càmera permet diverses targetes simultànies.
- Desa el projecte per conservar les direccions i els patrons. Els projectes anteriors continuen fent servir arpegis ascendents per defecte.

## Una targeta, una bateria completa

Tria **Ritme de bateria** com a funció d'una targeta: la configuració s'obre automàticament. Pots escollir Rock bàsic, Rock potent, Disco, Funk, Mig temps o Electrònic. Cada preset envia simultàniament les peces corresponents del kit; no cal una targeta per instrument. Configura el canal que rep la pista de MT Power Drum Kit a Sonar, ajusta la intensitat i prem APLICAR. Desa el projecte per conservar-ho.

La detecció de la targeta inicia el compàs des del primer pas i el repeteix mentre es manté present. En retirar-la s'aturen totes les notes que ha generat. SILENCI ABSOLUT també atura aquests ritmes.

Utilitza el port loopMIDI d'entrada de la pista de bateria i activa l'escolta d'entrada a Sonar. El canal es pot ajustar a la configuració del ritme (sovint 10 per a bateria GM, o l'entrada Omni de la pista). Les notes proposades són 36, 38, 42, 46 i 49; les pots canviar a la mateixa finestra si el mapa del teu MT Power Drum Kit difereix. No s'ha provat el plugin real al núvol. No activa els grooves interns del plugin: genera les notes MIDI que l'instrument interpreta.

El tempo és el del Wasteland. Cada bucle és un compàs de 4/4 i encara no se sincronitza automàticament amb el transport de Sonar. Retira una targeta abans d'ensenyar-ne una altra si vols canviar de ritme sense superposar-los.

## Llista de targetes i mapes de configuració

El botó superior **TARGETES EN FUNCIÓ** obre una finestra independent amb la llista de targetes i les columnes Targeta, Funció i Nom assignat. Escriu el Nom assignat directament a l’editor i prem APLICAR; també pots fer doble clic al nom a la llista. Els noms es desen amb el projecte. La posició i visibilitat d’aquesta finestra es conserven amb la distribució de finestres. Hi apareixen les targetes amb una funció diferent de **Cap acció**, incloses les assignacions inicials del programa. Les targetes actives es destaquen. Per treure'n una de la llista, selecciona Cap acció a l'editor i prem APLICAR; desa el projecte per conservar el canvi.

Clica una fila per seleccionar la mateixa targeta a l'editor i veure el seu mapa sense activar-la: sectors d'harmonia/arpegis, graella de passos del patró o de tota la bateria, cercle cromàtic, visual assignat o paràmetres MIDI. La selecció no envia notes noves. Pots provar la targeta amb la càmera.

**SEGUIR DIRECTE** torna a la previsualització automàtica. Els mapes seleccionats són de consulta: no substitueixen el vídeo de gravació ni la sortida de projecció. La distribució de finestres desada es continua recuperant en arrencar.

## Monitor unificat, controls CC i visuals en directe

**TARGETES EN FUNCIÓ** inclou ara el monitor ArUco: nom, funció, ID, estat, canal, nota, CC, eix, valor, X/Y, gir i visual assignat. Ja no s'obre una segona finestra de monitor. Utilitza la barra horitzontal per veure totes les columnes i desmarca **Només targetes amb funció** si vols consultar també les inactives amb Cap acció. Els noms i la distribució desada es conserven.

En seleccionar **Control MIDI CC** s'obre la seva configuració, amb canal, número CC i desplegable de moviment (rotació, horitzontal o vertical). Per tornar a obrir-la, torna a seleccionar Control MIDI CC al desplegable de funcions. La T02 amb CC7 conserva el control especial radial de volum i filtre CC74, indicat a la finestra.

Les targetes actives generen els visuals assignats. Diversos visuals diferents se superposen mitjançant una mescla de llum; en retirar una targeta desapareix la seva capa, i sense cap targeta la sortida en directe queda negra. Activar una targeta amb càmera o simulació torna automàticament al directe; seleccionar una fila permet inspeccionar el seu mapa sense activar MIDI ni projectar-lo.

La projecció i la gravació reben la mateixa composició en directe. La projecció ja no està limitada al color pla: mostra també els dotze visuals renovats, amb llum, halo i moviment continu. El cercle cromàtic conserva la seva projecció de color pla, que també es pot combinar amb altres visuals. Els mapes i els indicadors del ratolí són només d'ajuda a la previsualització. S'ha comprovat la finestra de projecció en pantalla virtual; cal provar el monitor/projector físic al teu ordinador. Les assignacions numèriques i els noms dels visuals es mantenen per compatibilitat amb els projectes anteriors.

## Àudio: disparar un clip complet dins de Sonar

La funció **Àudio** envia un pols de nota MIDI per iniciar un clip configurat prèviament a Sonar. No reprodueix fitxers localment ni activa directament qualsevol pista del timeline. Necessita una cel·la de la vista Matrix de Sonar, o un sampler amb reproducció one-shot, que tingui aquesta nota assignada.

1. A Sonar, carrega l'àudio a una cel·la Matrix o un sampler. Configura'l perquè una nota curta iniciï el clip complet, sense bucle i sense aturar-se quan arriba el note-off. Per començar, utilitza llançament immediat, sense esperar cap compàs. No el vinculis a una pista amb un instrument de bateria que pugui interpretar la mateixa nota.
2. Associa una nota MIDI lliure d'un canal concret al llançament del clip, rebuda des del mateix port loopMIDI del Wasteland. La configuració d'aquesta associació es fa a Sonar. Comprova que una pulsació curta reprodueixi l'àudio sencer abans d'utilitzar la càmera.
3. A l'editor del Wasteland, selecciona **Àudio**. El menú s'obre automàticament: indica canal, nota i la durada real del clip en segons. El botó **PROVAR DISPAR A SONAR** envia el pols sense necessitat de càmera. Desa el projecte per conservar els paràmetres.
4. En detectar la targeta s'envia un sol dispar. Retirar-la no envia una ordre d'aturada. El bloqueig impedeix repetir-lo durant la durada indicada, encara que es retiri i es torni a detectar la targeta. Quan acaba aquest temps, cal una nova aparició de la targeta per tornar-lo a disparar; no es repeteix automàticament si es manté visible. També es bloquegen dues targetes amb la mateixa nota i canal mentre el clip està ocupat.

**La durada és un bloqueig temporal configurat, no una detecció del final real.** Sonar no retorna aquest final al Wasteland. Si hi ha espera de llançament, estirament de temps o canvis al clip, cal ajustar la durada perquè no es pugui tornar a disparar abans d'hora. El monitor mostra el bloqueig restant; això confirma l'enviament del dispar, no que Sonar estigui sonant. Cal validar la reproducció a Sonar al teu ordinador.

El pols MIDI dura com a màxim 80 ms; el receptor ha d'ignorar-ne la finalització per continuar en one-shot. La retirada d'una targeta, el canvi de funció o la pausa de visuals no aturen el clip. Per aturar-lo abans del final, utilitza els controls de Sonar. El botó SILENCI ABSOLUT del Wasteland bloqueja MIDI i envia ordres de silenci als instruments, però no és un control de transport de les pistes d'àudio de Sonar.

## Interfície simplificada

S'han retirat el metrònom visual, el botó FINESTRES i els botons permanents de configuració de l'editor. Tria o torna a seleccionar una funció al desplegable per obrir la seva configuració. Els BPM continuen marcant el rellotge intern dels arpegis i patrons. La capçalera torna a mostrar el paisatge industrial amb el títol centrat, sense subtítol, versions duplicades ni controls falsos. El fitxer principal conserva el nom anterior per mantenir els accessos d'arrencada existents.

## Àudio: moviment, volum i efectes

La finestra que s'obre en seleccionar **Àudio** té dues pestanyes: **Reproducció** i **Moviment i efectes**. A la segona pots activar fins a tres controls independents: volum (CC7), panoràmica (CC10) i efecte assignable (CC74 per defecte, amb propostes CC91 per reverberació i CC94 per delay). Els controls estan desactivats inicialment: activa només els que hagis vinculat al receptor.

Cada control permet escollir moviment horitzontal, vertical, rotació o distància al centre; invertir-ne el sentit; ajustar mínim/màxim entre 0 i 127, i canviar el número CC. Per exemple, volum vertical invertit fa que a dalt soni més fort. Per evitar arribar al silenci, posa el mínim de volum a 30 o 40. Els controls actius han de tenir CC diferents. Tots utilitzen el canal MIDI de la targeta.

Aquests controls **envien missatges MIDI, no afegeixen processament d'àudio al Wasteland**. Una pista d'àudio de Sonar no interpreta automàticament tots aquests CC: assigna'ls a volum, panoràmica o paràmetres de plugin amb MIDI Learn / ACT, o utilitza un sampler que els admeti. Configura l'entrada MIDI i els canals perquè no modifiquin instruments que no vulguis controlar. Per fer l'aprenentatge d'un paràmetre, activa primer només aquell control i mou la targeta.

Mentre la targeta és present, els moviments modifiquen els controls sense tornar a iniciar el clip. Retirar-la deixa l'últim valor al receptor i el clip continua; tornar-la a mostrar abans que acabi permet continuar controlant-la sense repetir el dispar. La configuració es desa amb el projecte. Inversió de reproducció, canvi de velocitat o bucles no s'han afegit: requereixen un receptor adequat i una configuració específica a Sonar; aquesta funció conserva la reproducció completa una sola vegada.

## Previsualització de seguiment i projecció neta

El directe mostra les guies de control: cercle cromàtic quan hi ha una targeta amb aquest visual, mapa de sectors quan hi ha harmonia/arpegis, i marcadors de totes les targetes actives amb número, orientació i un recorregut dels últims 2,5 segons. Cada targeta té un traç propi. Les coordenades del ratolí sobre el cercle utilitzen la mateixa escala que el mapa visible.

La projecció i la gravació continuen rebent només la composició visual neta: color pla o visuals superposats, sense cercle, mapes, identificadors ni trajectòries. En retirar l'última targeta, el directe i la projecció tornen al negre; consultar una targeta a la llista continua permetent veure'n el mapa sense projectar-lo.

## Taula de volums i noms a l'editor

**TAULA DE VOLUMS** obre un mesclador MIDI per a les targetes amb funcions de so. Cada franja mostra el nom i un fader independent; el màster escala tots els nivells de les franges. La taula funciona també quan la targeta ja no és davant de la càmera i el clip continua sonant. Obrir-la o carregar el projecte no envia ordres de volum automàtiques.

Cada franja té canal i CC configurables. Per defecte es proposen CC diferents (20 + ID de targeta) per poder assignar-los per separat a Sonar amb MIDI Learn / ACT. **No és un mesclador d'àudio local:** vincula cadascun d'aquests controls al volum de la pista corresponent de Sonar o del sampler. El botó Enviar / Learn envia el nivell actual per comprovar la ruta o fer-ne l'aprenentatge. Les rutes de franges diferents han de ser diferents (canal + CC); el programa impedeix duplicar-les. Els percentatges són valors de control MIDI, no mesuradors de dB.

Moure un fader envia només el CC d'aquella franja; el màster envia els nivells escalats a totes. Si també tens un control de volum per moviment assignat al mateix paràmetre de Sonar, l'última ordre que rebi el paràmetre preval: desactiva aquell control de moviment si vols que el fader sigui l'únic que en governi el volum. Desa el projecte per conservar rutes, nivells i màster.

El **Nom assignat** ara es pot editar directament sota el número de targeta a l'editor; prem APLICAR i desa el projecte. La previsualització ja no mostra la franja de simulació ni el control de gir. La finestra de targetes té una vista compacta, amb la casella **Detall ArUco** per veure totes les columnes quan calgui. Les distribucions antigues que tenien aquesta finestra molt ampla s'adapten una vegada; les noves distribucions desades respecten la mida que triïs.

La capçalera gràfica utilitza `capcalera_wasteland_460.png`, que ha d'estar al costat del fitxer Python. Manté l'estètica i el títol centrat de la imatge original i n'elimina els falsos controls. No hi ha subtítol ni segona versió a sota.

## Arrencada identificable i tres finestres iguals (4.6.1)

La barra de títol mostra 4.6.1. A **Ajuda → Versió i fitxer que s'està executant** pots consultar el camí exacte del programa i el Python utilitzat. El nou **OBRIR_WASTELAND_461.bat** obre explícitament el fitxer principal de la mateixa carpeta, primer amb el Python 3.12 d'usuari que ja funciona, després amb el virtualenv local o el Python Launcher si cal. Mantén al costat la imatge capcalera_wasteland_460.png.

La distribució inicial conserva càmera a dalt a l'esquerra, previsualització a dalt a la dreta i editor a sota a la dreta, amb totes tres de la mateixa mida. Si la distribució desada és anterior a aquesta revisió, les tres mides s'adapten en arrencar sense eliminar-ne el fitxer. Pots desar aquesta distribució nova o moure les finestres i tornar-la a desar. El MIDI continua en una finestra compacta independent.

El camp **Nom assignat** és a l'editor, just sota Targeta / ID ArUco. Escriu-hi el nom, prem APLICAR i desa el projecte. La previsualització no té casella de simulació ni control de gir. Si encara els veus, consulta el fitxer real en execució a Ajuda i comprova que has actualitzat aquella carpeta.

## Diagnosi del Mute a Sonar (4.6.2)

Al panell MIDI, **DIAGNOSI MIDI** mostra aparicions/retirades i els missatges acceptats o rebutjats pel port local. Pots copiar o desar el registre. No confirma la recepció a Sonar. Les ordres de prova CC 0 i 127 serveixen per verificar manualment una assignació absoluta del Mute sense enviar notes. La revisió 4.6.2 només diagnosticava el problema; després de verificar els dos estats a Sonar, la 4.6.3 afegeix la funció de presència/Mute descrita al final. Instruccions i conclusions detallades a DIAGNOSI_MUTE_SONAR.md. L'accés OBRIR_WASTELAND_461.bat continua obrint el mateix fitxer principal actualitzat; la barra de títol ara indica 4.6.2.

## Control d'àudio / Mute per presència (4.6.3)

A l'editor tria **Control d’àudio / Mute**, una funció diferent de Nota MIDI i del dispar Àudio. La configuració s'obre automàticament amb els valors que Jordi ja ha provat a Sonar: canal 1, controlador CC119, visible/audible 0 i absent/silenciat 127. Prem Aplicar i desa el projecte. A Sonar mantén Remote Control del Mute en Controller, 119, canal 1.

La targeta visible envia 0 i deixa sentir la pista; retirar-la més de 250 ms envia 127 i activa el Mute. No canvia el transport, per tant el projecte de Sonar pot continuar en bucle. No es generen notes d'instrument. En aplicar la funció amb la targeta absent, connectar MIDI o carregar el projecte es posa l'estat de silenci; si la targeta ja està activa en reconnectar, se sincronitza l'estat visible. Tancar la càmera, el programa o activar SILENCI ABSOLUT silencia també aquests controls mentre hi hagi connexió MIDI operativa. No canviïs a mà el Mute de Sonar si vols deixar-ne el control a la targeta: l'aplicació no en rep l'estat de retorn.

Cada pista independent necessita una ruta canal+CC pròpia. El monitor mostra l'últim valor acceptat pel port local al camp Valor; la diagnosi permet comprovar els missatges i els errors. Els projectes antics no es modifiquen per convertir automàticament les seves funcions: assigna expressament la funció nova a les targetes que hagin de controlar el Mute.

## Editor de zones espacials (4.7.0 — fase 2)

El botó superior ZONES ESPACIALS obre un editor independent de la quadrícula circular 8×8. Pots seleccionar i agrupar caselles, posar nom a cada zona, autoritzar targetes, triar una imatge i veure'n la miniatura. La funció Activar zona espacial de l'editor de targetes també obre aquesta configuració. Prem DESAR ZONA AL MAPA i després desa el projecte per conservar-la. Els projectes antics continuen obrint-se; les zones i les rutes d'imatges també es conserven en fer Desar com.

Aquesta fase configura el mapa però encara no activa fotografies a la projecció. No envia MIDI i no interpreta les coordenades de càmera com si estiguessin calibrades. La fase següent integrarà la projecció persistent. Documentació completa a MAPA_ZONES.md.

## Participants — ATMO fase 1B (4.7.6)

Obre **Participants → Registre i seguiment…**, escriu el nom o àlies, tria el color i assigna una font (`camera:0`, etc.) i un ID ArUco 0–15. Prem **APLICAR PARTICIPANT** i desa el projecte. **NOU** permet afegir més persones; seleccionar una fila permet editar-la. El nom del participant és independent del nom i la funció musical de la targeta. ID 0 correspon a targeta 01.

La finestra mostra presència, última posició de càmera i incidències de font. Les pèrdues no eliminen participants. **RETIRAR / RECUPERAR** són ordres de sessió i no aturen les funcions MIDI/visuals de la targeta. **ELIMINAR** suprimeix la vinculació, amb confirmació. Colors i seguiment són només de l’operador; la projecció continua neta. Els projectes antics obren amb el registre buit. Detalls, compatibilitat i proves a [ATMO_ESFERA_FX_FASE_1B.md](ATMO_ESFERA_FX_FASE_1B.md).

## Simulador de cinc participants — ATMO fase 2 (4.7.7)

Obre **Participants → Simulador de cinc participants…**. A **Mapa i moviment**, clica i arrossega cada participant; configura’n el gir o oculta/mostra el marcador. La casella **Font disponible** simula una avaria i la recuperació de la font. A **Participants i esdeveniments** pots canviar noms, colors i IDs, retirar/recuperar persones i veure els successos. **REINICIAR PROVA** torna als cinc participants inicials, amb confirmació.

És una sessió virtual independent, sense càmera ni MIDI, que no modifica el projecte ni la projecció. Les dades virtuals es conserven en reobrir la finestra mentre el programa segueix obert; no es desen al projecte. La quadrícula no és una calibració de terra ni executa encara accions de zona. Instruccions i límits a [ATMO_ESFERA_FX_FASE_2.md](ATMO_ESFERA_FX_FASE_2.md).

## Zones al flux comú — ATMO fase 3 (4.7.8)

El registre de participants mostra ara la **Zona** confirmada i els esdeveniments d’entrada/sortida de tots els marcadors autoritzats, també si tenen una funció musical. Això no canvia què sona o què es projecta: les fotografies continuen responent a la funció Activar zona espacial, amb les mateixes durades.

Al simulador, **CARREGAR ZONES DEL PROJECTE** copia el mapa a una superfície virtual amb calibració sintètica. Mou els cinc participants i consulta les entrades, sortides i motius a la segona pestanya. No es carreguen fotografies ni es modifica la calibració real. **REINICIAR PROVA** conserva aquesta còpia del mapa. Detalls i compatibilitat a [ATMO_ESFERA_FX_FASE_3.md](ATMO_ESFERA_FX_FASE_3.md).

## Regles i sortides — ATMO fase 4 (4.7.9)

Obre **Regles → Regles i sortides…**. Configura un activador, els filtres opcionals de participant/zona/ID, la prioritat i una o més accions. Afegeix cada acció a la llista i prem **APLICAR REGLA**. Color i imatge persisteixen amb durada 0; les notes tenen durada de 0,05 a 60 segons. Els canals MIDI de regles han de ser diferents dels de les targetes i del mesclador. **EXECUTAR** envia les accions reals; **ALLIBERAR SORTIDA** retorna la propietat visual al camí existent. Aplicar regles reinicia les seves sortides anteriors. Desa el projecte per conservar-les.

Per provar sense dispositius, obre el simulador i prem **CARREGAR ZONES I REGLES DEL PROJECTE**. **REGLES DE PROVA...** edita la còpia virtual; **Sortida de prova** mostra la imatge/color i els missatges MIDI simulats sense tocar la projecció o el port real. Els projectes antics obren sense regles i conserven el seu funcionament. Instruccions, prioritats, grups visuals i límits a [ATMO_ESFERA_FX_FASE_4.md](ATMO_ESFERA_FX_FASE_4.md).

## Àudio local i BOSC VIU — prototip ATMO fase 5A (4.8.0)

**Projecte → Crear BOSC VIU de prova...** crea una carpeta nova amb cinc zones, regles i WAV sintètics. Obre el simulador per provar ocells, riu, vent, clariana i alarma sense càmera ni dispositiu d’àudio. Els sons són de prova, no gravacions de natura; la clariana és un color substituïble per una fotografia.

El complement real és opcional: **INSTAL_LAR_AUDIO_LOCAL.bat**, després **OBRIR_WASTELAND.bat** i **Àudio → Àudio local opcional... → ACTIVAR**. Hi ha fins a setze capes, bucles curts, volum/fade per participant o grup i màster local. Les noves accions són Reproduir so local, Aturar so local i Volum local. La funció antiga Àudio de les targetes continua sent MIDI per a Sonar.

**ATURAR ÀUDIO LOCAL** només atura el reproductor local. El silenci absolut també el bloqueja; tancar el panell no atura la reproducció. El simulador continua silenciós i mostra les veus a Sortida de prova. No s’activa el dispositiu automàticament ni es desa l’activació al projecte.

Validat al núvol amb SDL `dummy`; **Windows, altaveus i latència acústica encara no estan validats**. Abans d’utilitzar-lo en una instal·lació real, cal completar la prova documentada. Detalls, límits, format de regles 2 i evidència a [ATMO_ESFERA_FX_FASE_5.md](ATMO_ESFERA_FX_FASE_5.md). Les dependències bàsiques MIDI/visuals no han canviat.
