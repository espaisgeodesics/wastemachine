# ATMO ESFERA FX · Integració 11

Punt de partida: `atmo_esfera_fx_integracio_10b.py`, conservat sense modificacions.
La versió 11 s'obre amb `python atmo_esfera_fx_integracio_11.py` des de la carpeta
completa del projecte, amb les dependències del motor instal·lades. No substitueix
el motor ni canvia el format dels projectes.

## Edició integrada

A **Espai**, selecciona una zona de la llista o prem **Nova zona**. Clica o
arrossega per afegir o treure caselles dins del cercle. Configura el nom,
l'habilitació, les targetes 01–16 (IDs interns 0–15), la imatge JPG/PNG i la durada.
El panell de propietats té una barra de desplaçament; **Aplicar zona al mapa**
queda sempre disponible. Aplicar modifica el mapa en memòria; **Desar projecte**
conserva els canvis al disc. El motor impedeix desar si hi ha un esborrany pendent.

Les validacions, les imatges i la seva miniatura, els modes de durada, els IDs i
les rutes relatives es gestionen amb el controlador `ZoneEditor` original i el
model `SpatialMap`. No s'ha duplicat el motor d'activació de zones. La calibració
i el retorn als visuals continuen utilitzant les eines originals.

Canviar de secció conserva l'esborrany i la selecció ATMO. Obrir o crear un
projecte manté les comprovacions originals de canvis pendents.

**Editor original** continua disponible. Si hi ha canvis sense aplicar, cal
cancel·lar el canvi d'editor o acceptar descartar-los. Mentre l'original està
actiu, ATMO mostra un botó **Tornar a l'edició ATMO** en lloc d'una segona graella
editable. Tancar la finestra original també torna a ATMO, amb la mateixa protecció
dels esborranys. Així només un editor pot modificar el mapa en cada moment.

Les tres pantalles inicials i l'arrencada del motor són les de la 10b. Es mantenen
la paleta, la tipografia i la navegació ATMO. No s'han incorporat il·lustracions
definitives perquè encara no s'han aportat.

## Validació

S'han executat 32 proves sense pantalla gràfica: 9 de regressió ATMO i 23 del
model espacial original. Inclouen selecció amb arrossegament, solapaments,
autoritzacions, durades, persistència, cancel·lacions i canvi d'editor. Una prova
compara l'estructura Python de les pantalles inicials i l'arrencada amb la 10b.

Des de l'arrel del repositori:

```
python -m unittest discover -s tests -p test_atmo_integracio_11.py -v
python -m unittest discover -s tests -p test_spatial_zones.py -v
```

Pendent de validar a Windows amb la interfície real, càmera i sortida audiovisual:

1. Obrir les pantalles inicials i comprovar proporcions, tipografia i accessibilitat
   dels controls a la mida mínima de finestra.
2. Crear una zona amb diverses caselles, targetes, imatge i cada mode de durada;
   aplicar, desar, tancar i tornar a obrir el projecte.
3. Canviar de secció amb un esborrany: ha de conservar-se. Intentar desar un
   esborrany sense aplicar: el motor ha d'avisar.
4. Alternar entre ATMO i l'editor original, cancel·lant i acceptant el descart;
   verificar que els canvis aplicats apareixen a tots dos editors.
5. Repetir la prova amb un projecte nou, **Desar com...** en una altra carpeta,
   imatges absents i una zona deshabilitada.
6. Calibrar, provar una targeta en directe i confirmar la imatge, la durada i el
   retorn als visuals. Comprovar que les funcions MIDI i d'àudio originals segueixen
   funcionant. Les proves sense pantalla no certifiquen aquests comportaments físics.
