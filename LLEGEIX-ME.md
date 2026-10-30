# Wasteland Machine

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

Quan demanis un canvi, indica què has fet, què esperaves i què ha passat. Pots adjuntar una captura o copiar els errors de la consola. Les modificacions locals encara no s'han publicat al repositori de GitHub.

## Estat de la revisió

S'ha revisat la versió Pas 15. S'ha corregit la selecció del sistema de captura segons la plataforma i l'aturada de notes en tancar o perdre la càmera. Pas 14 es conserva com a versió anterior.

Validació al núvol amb Python 3.12 i pantalla virtual: arrencada de totes dues versions, dotze visuals, cercle cromàtic, projecció i detecció ArUco sintètica. Hi ha proves automatitzades per als canvis de càmera a tests/.

La càmera física, MIDI/Cakewalk i el llançador BAT necessiten comprovació al teu Windows; aquí no es disposa d'aquests dispositius ni d'aquest sistema operatiu. No s'ha fet una auditoria exhaustiva de totes les funcions.

## Desenvolupament

La versió actual és wasteland_4_5_15_pas_15_editor_musical_desplegable.py. Amb Python 3.12, crea un entorn virtual, instal·la requirements.txt i executa aquest fitxer des d'un escriptori amb Tkinter. OpenCV headless és suficient perquè les finestres les dibuixa Tkinter.

Proves: `python -m unittest discover -s tests -v`.

## Simulació, silenci i patrons

- A la finestra VISUAL, activa **SIMULAR AMB RATOLÍ**. Tria una targeta a l'editor, configura-la i prem APLICAR. Mantén premut el botó esquerre sobre la imatge i arrossega per simular-ne la posició; un cercle groc indica la targeta. Deixa anar el clic per retirar-la. El control Gir simula la rotació. La càmera i la simulació són alternatives; activar-ne una desactiva l'altra.
- **SILENCI ABSOLUT** atura les notes, allibera el pedal de sustain i envia All Sound Off i All Notes Off als 16 canals de la sortida MIDI connectada. També bloqueja noves activacions fins a prémer **REPRENDRE MIDI**. No silencia pistes d'àudio o instruments que no rebin aquesta sortida MIDI.
- En seleccionar **Arpegiador espacial**, el menú s’obre i pots triar Ascendent, Descendent, Pujada i baixada o Aleatori. Es conserven la divisió rítmica, durada, escala i intensitat.
- La funció **Patró rítmic** ofereix 16 passos repetits. Activa els cops a la configuració musical; la nota i el canal es trien a l'editor de la targeta. La divisió 1/4 temps equival a semicorxeres: 16 passos formen un compàs de 4/4. El patró segueix el rellotge intern i comença a la fase actual de la graella quan detecta la targeta; s'atura en retirar-la. No hi ha sincronització externa amb Cakewalk en aquesta versió.
- Per a bateria General MIDI, pots assignar targetes diferents a bombo (nota 36), caixa (38) i hi-hat (42), normalment al canal 10; depèn de l'instrument receptor. La simulació amb ratolí activa una targeta cada vegada; la càmera permet diverses targetes.
- Desa el projecte per conservar les direccions i els patrons. Els projectes anteriors continuen fent servir arpegis ascendents per defecte.

## Una targeta, una bateria completa

Tria **Ritme de bateria** com a funció d'una targeta: la configuració s'obre automàticament. Pots escollir Rock bàsic, Rock potent, Disco, Funk, Mig temps o Electrònic. Cada preset envia simultàniament les peces corresponents del kit; no cal una targeta per instrument. Configura el canal que rep la pista de MT Power Drum Kit a Sonar, ajusta la intensitat i prem APLICAR. Desa el projecte per conservar-ho.

La detecció de la targeta inicia el compàs des del primer pas i el repeteix mentre es manté present. En retirar-la s'aturen totes les notes que ha generat. El ratolí serveix per provar el ritme complet mantenint premut el clic. SILENCI ABSOLUT també atura aquests ritmes.

Utilitza el port loopMIDI d'entrada de la pista de bateria i activa l'escolta d'entrada a Sonar. El canal es pot ajustar a la configuració del ritme (sovint 10 per a bateria GM, o l'entrada Omni de la pista). Les notes proposades són 36, 38, 42, 46 i 49; les pots canviar a la mateixa finestra si el mapa del teu MT Power Drum Kit difereix. No s'ha provat el plugin real al núvol. No activa els grooves interns del plugin: genera les notes MIDI que l'instrument interpreta.

El tempo és el del Wasteland. Cada bucle és un compàs de 4/4 i encara no se sincronitza automàticament amb el transport de Sonar. Retira una targeta abans d'ensenyar-ne una altra si vols canviar de ritme sense superposar-los.

## Llista de targetes i mapes de configuració

El botó superior **TARGETES EN FUNCIÓ** obre una finestra independent amb la llista de targetes i les columnes Targeta, Funció i Nom assignat. Escriu el Nom assignat directament a l’editor i prem APLICAR; també pots fer doble clic al nom a la llista. Els noms es desen amb el projecte. La posició i visibilitat d’aquesta finestra es conserven amb la distribució de finestres. Hi apareixen les targetes amb una funció diferent de **Cap acció**, incloses les assignacions inicials del programa. Les targetes actives es destaquen. Per treure'n una de la llista, selecciona Cap acció a l'editor i prem APLICAR; desa el projecte per conservar el canvi.

Clica una fila per seleccionar la mateixa targeta a l'editor i veure el seu mapa sense activar-la: sectors d'harmonia/arpegis, graella de passos del patró o de tota la bateria, cercle cromàtic, visual assignat o paràmetres MIDI. La selecció no envia notes noves. Pots provar la targeta amb la simulació o la càmera quan vulguis. Canviar de selecció retira una simulació que estigués premuda.

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

Aquests controls **envien missatges MIDI, no afegeixen processament d'àudio al Wasteland**. Una pista d'àudio de Sonar no interpreta automàticament tots aquests CC: assigna'ls a volum, panoràmica o paràmetres de plugin amb MIDI Learn / ACT, o utilitza un sampler que els admeti. Configura l'entrada MIDI i els canals perquè no modifiquin instruments que no vulguis controlar. Per fer l'aprenentatge d'un paràmetre, activa primer només aquell control i mou la targeta o la simulació.

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
