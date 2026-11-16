# ATMO ESFERA FX · Integració 13

## Arrencada

Extreu el ZIP complet en una carpeta nova i obre **OBRIR_ATMO.bat**. També
**OBRIR_ATMO_12.bat** i **OBRIR_ATMO_13.bat** entren a aquesta versió. Els
llançadors d'obertura utilitzen Python 3.12, validat amb MIDI a Windows.
La diagnosi i l'instal·lador MIDI també queden fixats a Python 3.12.

Es conserven les dues pantalles d'entrada: les quatre experiències i la tria de
projecte nou, projecte existent, plantilla, entrada sense projecte o retorn.
S'elimina el paràgraf provisional sobre plantilles en desenvolupament. Triar una
plantilla continua obrint un projecte existent com a base; no s'han afegit
plantilles fictícies ni canviat el format dels projectes.

Després de la tria s'entra **directament a la pantalla principal ATMO**, amb les
eines del motor 4.8.1 i el tema ATMO. Ja no apareix el panell intermedi de set
seccions ni cal prémer «Eines completes ATMO». La càmera, l'editor i la
previsualització es mostren només quan es demanen. La inicialització del projecte
no obre la previsualització i tampoc ho fa l'ordenació retardada de finestres.

## Finestres

Tots els panells i els ajustos de música, CC, àudio, zones, calibratge, participants,
regles i diagnosi són finestres filles no modals de la principal. El sistema les
manté davant de la principal. La nova eina oberta es mostra i rep el focus; no
s'utilitza `-topmost`, `grab_set` ni `focus_force`, de manera que no es fixa per
sobre del DAW o d'altres aplicacions. Es conserva el comportament de tancar/amagar
de cada eina i la protecció dels esborranys.

L'editor ampliat de zones continua utilitzant els controls ATMO i el model espacial
existent. Les versions anteriors de la interfície queden disponibles com a codi de
referència, però els llançadors estàndard obren la versió 13.

## Marca i noms

S'actualitzen les referències de marca als fitxers de text, missatges, proves i
documentació, i es reanomenen els dos fitxers del motor i els recursos de capçalera.
Les referències als noms nous s'actualitzen conjuntament. El motor actiu es diu
`atmo_esfera_fx_4_5_15_pas_15_editor_musical_desplegable.py`.

No es canvia l'identificador administratiu del repositori de GitHub:
`espaisgeodesics/wastemachine`. Tampoc es reescriu la història Git ni els noms o les
dades que l'usuari ja tingui als seus projectes locals. `main` i la branca original
del motor continuen intactes. El format JSON dels projectes es conserva.

## Validació

56 proves automàtiques superades: 8 noves d'arrencada, propietat dels panells i
llançadors; 16 de la capa de presentació/MIDI; 9 d'edició integrada; i 23 del model
espacial. També es comprova la sintaxi de tots els fitxers Python i que les rutes
referenciades del motor i dels recursos coincideixen amb els noms nous.

Les proves d'ordre de finestres utilitzen dobles de prova: falta validar l'ordre
real i la geometria al Windows de l'usuari.

Prova curta:

1. OBRIR_ATMO.bat → Instal·lació immersiva → Projecte nou.
2. Ha d'aparèixer només la principal ATMO; cap previsualització automàtica.
3. Obre càmera, visuals i editor: han de quedar davant de la principal.
4. Clica la principal i torna a obrir els panells: han de continuar accessibles.
5. Tanca i reobre visuals; prova també música i zones.
6. Confirma que la connexió MIDI funciona amb el Python 3.12 existent.
