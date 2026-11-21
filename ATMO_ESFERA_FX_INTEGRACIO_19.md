# ATMO ESFERA FX 19 · Atmosfera viva

Base: ZIP `ATMO_ESFERA_FX_ATMOSFERA_VIVA_V3_PER_CODEX.zip` de l’usuari, sobre integració 18.
Branca exclusiva: `atmo/interficie-primera-integracio`.

## Obrir

Extreu el ZIP complet en una carpeta nova i executa **OBRIR_ATMO.bat**. Utilitza Python 3.12.
No cal desinstal·lar cap versió anterior. Conserva els projectes i els mitjans originals.

## Aspecte

S’ha consolidat la paleta Atmosfera viva a controls, capçaleres, editors i finestres auxiliars. A Windows es manté Segoe UI. Les quatre imatges inicials s’han conservat byte per byte; `atmo_assets/APROVACIO_IMATGES.json` en registra els SHA-256 i una prova ho comprova.

S’han afegit una capçalera atmosfèrica i accessos agrupats al motor principal. Les barres d’eines es reorganitzen quan falta amplada. Els formularis llargs tenen desplaçament; els botons d’aplicar a calibració i visuals es mantenen accessibles. La taula de volums permet desplaçament horitzontal i vertical.

La tematització no altera els fotogrames de projecció, les dades del mapa ni els colors amb significat funcional. El mosaic i els fades es mantenen. No s’usen les capçaleres de la identitat anterior.

## WAV i cançons a les zones

S’han corregit els dos obstacles detectats: el dispositiu local no activat i el límit antic de clips de 30 segons. Les cançons llargues es llegeixen per fragments de mig segon, amb fins a 16 capes independents; no es carreguen senceres a memòria. Es conserven volum, màster, bucle, presència i fades. WAV PCM, WAV float i OGG mono/estèreo, entre 8 i 96 kHz; durada màxima 2 hores i fitxer màxim 2 GiB.

1. Si no tens el complement local, executa **INSTAL_LAR_AUDIO_LOCAL.bat** amb Python 3.12.
2. A Zones, tria el WAV/OGG. Fes servir **ACTIVAR ÀUDIO LOCAL** i **PROVAR SO DE LA ZONA** per separar una incidència de reproducció d’una incidència de detecció/calibració. **ATURAR PROVA** només atura aquesta prova.
3. Selecciona les caselles i targetes autoritzades, comprova volum/fades i prem **Aplicar zona al mapa**. Aplicar explícitament una zona amb so també sol·licita activar el dispositiu si estava desactivat.
4. Calibra el terra i situa la targeta autoritzada a la zona. El panell mostra l’estat real del dispositiu, les capes i els errors. Si el màster o el volum de la zona és zero, no se sentirà.
5. Desa el projecte. Obrir un projecte existent no activa passivament un dispositiu que s’havia desactivat; pots activar-lo des de Zones o Àudio local.

L’àudio local va a la sortida d’àudio de Windows, independent de loopMIDI i Cakewalk. Tenir MIDI connectat no activa aquest dispositiu. **SILENCI ABSOLUT** bloqueja també el so local; desactiva’l per fer la prova.

## Verificació i captures

Consulta **VALIDACIO/INFORME_PROVES.md**, els registres i les captures. Les captures es generen des de finestres Tk reals; no són maquetes. Les imatges de càmera/posicions de prova són sintètiques i l’àudio de prova utilitza SDL amb dispositiu simulat, sense certificar escolta per altaveus.

`VALIDAR_ATMO_WINDOWS.bat` executa compilació, suite i captures a Windows i desa els resultats a `VALIDACIO/windows`. El repositori també inclou un workflow de Windows per a aquesta branca. No cal executar aquesta validació per obrir el programa.

Validació final: **417 proves correctes a Linux i 417 a Windows**, sense omissions, amb 90 captures per entorn. L’escolta i els dispositius reals de l’usuari es mantenen pendents.
