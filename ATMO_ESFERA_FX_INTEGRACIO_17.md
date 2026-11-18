# ATMO ESFERA FX · Integració 17

Branca: `atmo/interficie-primera-integracio`. Punt de partida: integració 16.

## Obrir a Windows

Descomprimeix el ZIP complet en una carpeta nova i executa **OBRIR_ATMO.bat**.
No cal desinstal·lar res. El llançador utilitza Python 3.12 i obre la integració 17.
Conserva els projectes i els fitxers d’imatge/so/vídeo originals. Les referències a mitjans es desen al projecte; no s’incrusten al JSON.

## Imatges i vídeos a les targetes

A l’editor de targetes, tria **Canviar visual → CONFIGURAR FUNCIÓ**.
Pots seleccionar un visual generat, **Cap**, o un **fitxer d’imatge o vídeo**.
També pots assignar Imatge / Vídeo a una targeta que tingui una altra funció.

- Fade in: 0–10 s, inicialment 0,5 s.
- Fade out: 0–10 s, inicialment 1 s.
- L’aparició de la targeta activa el mitjà; la retirada en fa el fade out.
- En canviar de targeta/mitjà, el mitjà anterior es fon amb el nou.
- Els vídeos permeten bucle; sense bucle retenen l’últim fotograma mentre la targeta segueix activa.
- Es respecta la proporció original amb bandes negres si cal.
- Si coincideixen diverses targetes amb fitxers, guanya la prioritat més alta; en empat, l’ID menor. Les regles visuals explícites tenen prioritat sobre aquests mitjans.
- Vídeo sense pista d’àudio integrada. La descodificació depèn dels còdecs d’OpenCV disponibles.

Prem **APLICAR A LA TARGETA** i desa el projecte. En fer «Desar com», es conserven les referències als fitxers originals.

## Música i previsualització

La pantalla inicial i el motor principal s’obren maximitzats. Les finestres auxiliars continuen sent independents.
La previsualització mostra conjuntament els mapes d’harmonia i arpegiador, les cel·les/sectors actius i notes MIDI. Els colors identifiquen les targetes. Aquestes guies no es projecten.

L’arpegiador permet nombre de notes (1–32 o Auto), acord/escala/notes MIDI triades, 1–6 octaves, direccions ascendent/descendent/anada i tornada/aleatòria/ordre triat, i quadrícula 8 × 3 o sectors i anells. El rang ha de contenir prou notes diferents. Els projectes antics sense aquests paràmetres mantenen Auto i el mapa radial.

## Taula de volums i Cakewalk

El màster controla l’àudio local i els canals MIDI. Cada targeta sonora té nivell propi; les targetes sense so es mostren inactives. Per defecte, els instruments MIDI utilitzen CC7.

Per instruments en pistes separades, prem **Preparar canals MIDI independents** i configura cada pista de Cakewalk perquè rebi només el canal indicat. Desa el projecte. Aquest botó canvia els canals de les targetes de manera explícita i allibera les notes anteriors.

En un canal MIDI compartit, CC7 afecta tot el canal: el nivell individual només modifica la velocitat de les notes següents. Per canviar el volum d’una nota sostinguda independentment, separa els canals. El receptor ha de respondre a CC7, o cal assignar el controlador amb MIDI Learn / ACT.
Una zona local compartida per diverses targetes reprodueix una sola veu i utilitza el nivell més alt de les targetes presents.

## Chaos XY · Ambients

La funció Chaos XY de les targetes és un controlador d’efectes: no crea notes. Permet destinació a totes les targetes MIDI sonores, a targetes seleccionades o a un canal concret; ambients Obert / aire, Cova, Eco, Aguts i greus, Reverb i brillantor; assignació X/Y/gir, CC, rangs, valors neutres, suavitzat i retirada amb retorn neutre o manteniment.

A Cakewalk, vincula els CC als paràmetres del sintetitzador o dels plugins amb MIDI Learn / ACT. Enviar CC91 o CC12 no crea per si mateix una reverberació o un eco. No processa els WAV locals. Silenci/aturada restableix els controls enviats, també si havies triat mantenir-los.
Les configuracions antigues de Chaos Instrument es conserven a `kaoss_instrument_legacy` quan es migren a Ambients. El simulador conserva el model d’instrument.

## Verificació

Proves automàtiques de transicions, descodificació d’imatges, vídeo simulat, arpegiador, encaminament d’efectes, mesclador MIDI i volum local, a més de regressions de les integracions anteriors.
La validació de Windows, títols de finestra, càmera, còdecs de vídeo i resposta audible real a Cakewalk queda pendent al dispositiu de l’usuari. S’han instal·lat OpenCV i mido en un directori temporal per executar la suite del motor. Les proves de finestres sense pantalla disponible s’ometen; no hi ha dispositius MIDI/àudio físics.
