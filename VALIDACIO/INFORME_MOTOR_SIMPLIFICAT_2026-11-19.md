# ATMO ESFERA FX · motor simplificat

Branca: `atmo/interficie-primera-integracio`.
Codi validat: `82e695d65ba156dcebec701937e526bdba0d3f08`.

## Canvis

- Eliminats els tres blocs de classificació del motor. El fons utilitza la imatge aprovada de l'experiència escollida, sense canviar els originals.
- Es mantenen els accessos principals i les finestres independents de càmera, visual, MIDI, editor i projecció.
- Retirat el menú superior Àudio; Àudio local i Taula de volums continuen disponibles.
- Un únic botó Calibrar el terra a la barra principal; eliminat el duplicat de Visual. L'accés contextual de calibració de l'editor de zones es conserva.
- A la previsualització, identificadors curts al mapa i llegenda lateral amb funcions i notes. Cada quadrícula compartida es dibuixa una vegada; les seleccions de totes les targetes es conserven. Les quadrícules radials i rectangulars es poden combinar.
- La projecció, els mitjans i el comportament MIDI/àudio es conserven.

## Validació

Windows CI: https://github.com/espaisgeodesics/wastemachine/actions/runs/44610792609

- Compilació correcta; 419 proves superades amb Python 3.12.10.
- Dues proves noves per verificar quadrícules compartides i coexistència dels dos mapes.
- 90 captures reals de finestres de Windows, escalats Tk 100%, 125% i 150%; cap error de callback.
- Revisades visualment les captures del motor als escalats 100% i 150%, i la previsualització simultània d'harmonia i arpegiador.
- Els fitxers d'imatge inicials continuen protegits per les proves dels hashes aprovats.

Les captures utilitzen posicions simulades; la validació no comprova càmera física, focus DMX ni instruments MIDI externs. La llegenda indica el nombre d'entrades addicionals quan no hi caben totes en una finestra petita.

## Execució

Extreu el ZIP complet en una carpeta nova i executa `OBRIR_ATMO.bat`. No cal desinstal·lar l'anterior ni sobreescriure els projectes.
