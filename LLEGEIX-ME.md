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
- A **Arpegiador espacial → CONFIGURAR MÚSICA / PATRÓ**, tria Ascendent, Descendent, Pujada i baixada o Aleatori. Es conserven la divisió rítmica, durada, escala i intensitat.
- La funció **Patró rítmic** ofereix 16 passos repetits. Activa els cops a la configuració musical; la nota i el canal es trien a l'editor de la targeta. La divisió 1/4 temps equival a semicorxeres: 16 passos formen un compàs de 4/4. El patró segueix el rellotge intern i comença a la fase actual de la graella quan detecta la targeta; s'atura en retirar-la. No hi ha sincronització externa amb Cakewalk en aquesta versió.
- Per a bateria General MIDI, pots assignar targetes diferents a bombo (nota 36), caixa (38) i hi-hat (42), normalment al canal 10; depèn de l'instrument receptor. La simulació amb ratolí activa una targeta cada vegada; la càmera permet diverses targetes.
- Desa el projecte per conservar les direccions i els patrons. Els projectes anteriors continuen fent servir arpegis ascendents per defecte.
