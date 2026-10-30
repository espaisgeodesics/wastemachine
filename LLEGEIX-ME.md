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
