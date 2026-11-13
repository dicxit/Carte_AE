# Convertisseur de carte AE

Outil Windows qui transforme les paysages Condor (`.trn` / `.raw`) en cartes BMP 32 bits :
courbes de niveau, teinte d'altitude, ombrage, mer, lacs, rivières, routes, zones urbaines,
noms de villes et légende « By Dicxit(AE) ».

Version de référence : **2.11** (12/11/2026) (`VERSION` dans `src/Carte_courbes_gui.pyw`).

## Contenu du projet

| Fichier | Rôle |
|---|---|
| `Carte_AE.exe` | Application prête à l'emploi (double-clic). |
| `src/Carte_courbes_gui.pyw` | Interface graphique (tkinter). |
| `src/carte_courbes.py` | Moteur de rendu : lecture, relief, courbes, rivières, routes, villes, légende. |
| `src/worldcover.py` | Lacs, mer et zones urbaines à partir d'ESA WorldCover. |
| `src/osm_routes.py` | Routes et cours d'eau OpenStreetMap, convertis en `.npz`. |
| `src/Carte_courbes.bat` | Lancement en ligne de commande (choix du `.raw` puis du BMP). |
| `src/carte_courbes.ico` | Icône de l'application. |
| `style_AE.json` | Style AE (vert, modèle AA3_AE). |
| `style_DGT.json` | Style DGT (couleurs claires, zones urbaines orange). |

## Utilisation

1. Lancer `Carte_AE.exe`.
2. Choisir le paysage (`.trn` ou copie `.raw`) et le style (AE ou DGT).
3. Régler la qualité (Normale, Haute, Maximale), les rivières et lacs, les noms de villes.
4. Cliquer sur **Créer la carte**.

Le fichier créé s'appelle `<paysage>_AE.bmp` avec le style AE, `<paysage>_DGT.bmp` avec le style DGT,
et il est placé à côté du `.trn`.

Quand on change de style, le suffixe du nom de la carte (`_AE`, `_AEb`, `_DGT`) est remplacé
automatiquement dans le champ « Carte BMP à créer ». Le dossier et le nom de base ne changent pas.

Noms de villes : ils viennent du fichier `.cup` du paysage (à côté du `.trn`, ou dans
`D:\Condor3\Landscapes\<nom>\`). Sans `.cup`, la carte est faite sans noms de villes.

Lacs : ils viennent des tuiles WorldCover de `D:\Condor3\WorldCover`. Sans tuile couvrant la zone,
la détection se fait par le relief, qui trouve moins de lacs.

**Tout traiter** recherche automatiquement le dossier `Landscapes` sur les disques, puis parcourt
tous les fichiers `.trn` trouvés sous ce dossier. Un message d'avertissement rappelle que le traitement
peut prendre du temps selon la puissance de l'ordinateur avant de lancer. Les cartes existantes sont
écrasées. Le bouton **Stop** arrête le lot ; un rapport (`rapport_courbes.txt`) est écrit à la fin.

## Données nécessaires

Les données ne sont pas incluses dans le projet. Sans elles, le rendu reste possible mais incomplet.

| Dossier | Contenu | Utilité |
|---|---|---|
| `D:\Condor3\WorldCover` | Tuiles ESA WorldCover 2021 (`*.tif`) | Lacs, mer, zones urbaines |
| `D:\Condor3\OSM` | `routes_<paysage>.json` et `eau_<paysage>.json` | Routes, rivières |
| `D:\Condor3\Landscapes` | Paysages `.trn` et `.cup` | Source des cartes et des noms de villes |

Les chemins OSM/WorldCover sont fixés dans `src/carte_courbes.py` (`DOSSIER`), `src/worldcover.py` (`DOSSIER`)
et `src/osm_routes.py` (`DOSSIER`). Pour **Tout traiter**, le dossier des paysages (`Landscapes`)
est désormais recherché automatiquement sur les disques.

## Réglages des styles

Les styles sont des fichiers JSON à côté de l'exécutable. Quelques clés utiles :

- `courbes.couleur_maitresse`, `courbes.facteur_inter` : couleur et intensité des courbes.
- `saturation` : < 1 adoucit les couleurs.
- `nettete` : netteté après sur-échantillonnage.
- `urbain.couleur`, `urbain.opacite` : couleur des zones urbaines.

Dans `src/carte_courbes.py`, plusieurs seuils se règlent par constantes :

- `URBAIN_SURFACE_MIN` : taille minimale d'une zone urbaine (cellules de 90 m).
- `URBAIN_FLOU` : flou des bords des zones urbaines.
- `COURBES_LISSAGE`, `RUGOSITE_MIN`, `RUGOSITE_MAX` : lissage des courbes dans les zones plates.

## Reconstruire l'exécutable

Depuis le dossier `src` (PyInstaller requis) :

```bash
pyinstaller --noconfirm --onefile --windowed --name Carte_AE --icon carte_courbes.ico --add-data "../style_AE.json;." --add-data "carte_courbes.ico;." --add-data "../Installation_FR.pdf;." --add-data "../Installation_EN.pdf;." --hidden-import scipy.ndimage --exclude-module matplotlib --exclude-module rasterio Carte_courbes_gui.pyw
```

Copier ensuite `dist/Carte_AE.exe` à la racine du projet. Les fichiers `style_*.json` doivent rester
à côté de l'exécutable pour être proposés dans la liste des styles.

## Dépendances (exécution depuis les sources)

Python 3 avec `numpy`, `scipy`, `Pillow`, `ijson` (et `rasterio` pour préparer WorldCover).
Voir `requirements.txt`.

## Organisation du dossier de travail

- `src/` : code source (à modifier ici).
- `style_AE.json`, `style_AEb.json` (variante), `style_DGT.json` : styles.
- `tests/Lancer_test.bat` : lancement de test.
- `exemples/` : `parametres.json` et `rapport_courbes.txt` (réglages et rapport d'exécution).
- `historique/` : anciennes versions (`v1.41_precedent/` : `carte_courbes.py` et `style_AE.json` d'avant la fusion).

Les données volumineuses (OSM ~3 Go) restent dans `D:\Condor3`.

WorldCover : les tuiles 2021 v200 (`*_Map.tif`) sont dans `WorldCover\` (ce projet). Pour chaque
tuile, les grilles `*_eau.npy` (lacs et mer) et `*_bati.npy` (zones urbaines) sont créées à côté
(`worldcover.preparer_tuiles`). Si une tuile manque ici, l'outil cherche dans `D:\Condor3\WorldCover`.
La zone couverte pour la France métropolitaine (41–51,5° N) est complète : 30 tuiles.

### Historique des fusions

Deux copies existaient : `D:\Condor3\Convertisseur_carte_AE` (GUI 1.41, 7 nov.) et
`F:\...\Convertisseur_carte_AE` (`carte_courbes.py` et `style_AE.json` du 4 nov.).
Version retenue : GUI 1.41 + `carte_courbes.py` du 4 nov. (paramètres optionnels `texte` et `halo`
pour `dessiner_villes`) + `style_AE.json` du 4 nov. (clé `villes`).

Non récupérés : GUI 1.40 du 4 nov., son README et l'ancien `Carte_AE.exe` du 28 oct. Ils étaient
dans ce dossier et ont été écrasés lors de la copie. Les archives `Carte-AE.rar` pourraient les
contenir, mais ne sont lisibles qu'avec WinRAR ou 7-Zip.
