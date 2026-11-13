<p align="center">
  <img src="logo.png" alt="Carte AE" width="160">
</p>

# Carte AE : convertisseur de cartes Condor

Programme : `Carte_AE.exe`, version **2.11** (13/11/2026)

Outil Windows qui transforme les paysages **Condor 3** (`.trn` / `.raw`) en cartes BMP 32 bits : teinte d'altitude, ombrage, courbes de niveau, mer, lacs, rivières, routes, zones urbaines, noms de villes et légende « By Dicxit(AE) ».

- [Tutoriel d'installation (FR)](Installation_FR.pdf) · [Installation tutorial (EN)](Installation_EN.pdf)

---

## 1. Ce qu'il vous faut

- Un PC **Windows** (10 ou 11).
- Le dossier du programme, contenant :
  - `Carte_AE.exe` : le programme ;
  - `style_AE.json`, `style_AEb.json`, `style_DGT.json` : les styles de couleurs ;
  - `Installation_FR.pdf` / `Installation_EN.pdf` : tutoriels.
- Un paysage **Condor 3** installé (fichiers `.trn`, dossier `Landscapes`).

**Vous n'avez pas besoin d'installer Python** : le programme est un exécutable autonome.

---

## 2. Installation rapide

1. Copiez le dossier du programme dans un emplacement avec droits d'écriture (ex. `C:\Carte_AE\`).
2. Gardez les fichiers `style_*.json` **à côté** de l'exécutable.
3. Double-cliquez sur `Carte_AE.exe`.

> **Évitez** `C:\Program Files\` : le programme écrit ses réglages et ses rapports à côté de lui.

> **SmartScreen** : si Windows affiche « Windows a protégé votre PC », cliquez sur **Informations complémentaires** puis **Exécuter quand même** (programme non signé).

Au premier lancement, le programme crée à côté de lui `parametres.json` (réglages) et, après un lot, `rapport_courbes.txt`.

---

## 3. Utilisation

1. **Fichier TRN / RAW** : choisissez le fichier `.trn` du paysage (par défaut le programme propose `D:\Condor3\Landscapes\`).
2. **Carte BMP à créer** : le nom se remplit automatiquement (`<paysage>_AE.bmp` ou `_DGT.bmp`) à côté du `.trn`.
3. **Style** : AE (vert) ou DGT (couleurs claires, villes en orange). Le suffixe du nom s'adapte au style.
4. Réglez courbes (ex. 500 / 250 m), rivières & lacs, noms de villes, qualité.
5. Cliquez sur **Créer la carte**. La carte est enregistrée à côté du `.trn`.

Noms de villes : lus depuis le fichier `.cup` du paysage (à côté du `.trn` ou dans le dossier du paysage). Sans `.cup`, la carte est créée sans noms de villes.

---

## 4. Tout traiter

La fonction **« Tout traiter »** :
- recherche automatiquement le dossier **`Landscapes`** sur les disques de l’ordinateur ;
- trouve et traite **tous les fichiers `.trn`** présents sous ce dossier (un par un) ;
- affiche un **message d’avertissement** (FR/EN) rappelant que le traitement peut prendre du temps selon la puissance de l’ordinateur — il faut valider pour continuer.

Les cartes existantes sont écrasées. Le bouton **Stop** arrête le lot et un rapport `rapport_courbes.txt` est écrit à la fin.

---

## 5. Données facultatives

Les données ci-dessous ne sont pas incluses. Sans elles, le rendu reste possible mais incomplet.

| Dossier | Contenu | Ce qu'il ajoute |
|---|---|---|
| `Landscapes` (détecté automatiquement pour « Tout traiter ») | Paysages `.trn` et `.cup` | Source des cartes et des noms de villes. |
| `D:\Condor3\WorldCover` (facultatif) | Tuiles ESA WorldCover 2021 (`*.tif`) | Lacs, mer, zones urbaines réelles. |
| `D:\Condor3\OSM` (facultatif) | `routes_<paysage>.json`, `eau_<paysage>.json` | Routes et rivières. |

> Sans les dossiers facultatifs, le programme fonctionne, mais sans ces détails.

---

## 6. Mise à jour et désinstallation

- **Mise à jour** : remplacez `Carte_AE.exe` par la nouvelle version. Conservez vos `parametres.json` et `style_*.json` personnalisés.
- **Désinstallation** : supprimez le dossier du programme. Les cartes déjà créées (à côté des paysages Condor) ne sont pas supprimées.

---

## 7. Avertissement (non-responsabilité)

- Le programme est fourni **« tel quel »**, sans garantie d'aucune sorte. L'auteur ne peut être tenu responsable des dommages, pertes de données ou erreurs de navigation liés à son usage.
- **Les cartes ne sont pas des documents de navigation.** Elles ne remplacent ni une carte officielle, ni une carte aéronautique, ni les instruments de bord.
- Le programme **lit** les fichiers Condor et **crée** des fichiers BMP. Il ne modifie pas les paysages.
- Outil personnel, **non affilié, ni approuvé, ni soutenu** par les créateurs du simulateur Condor.

---

## 8. Copyright et crédits

- Programme : © Dicxit (AE), v2.11. Tous droits réservés sauf mention contraire.
- Condor est un simulateur de vol à voile ; son nom et ses fichiers appartiennent à leurs auteurs respectifs.
- Données OpenStreetMap : © contributeurs OpenStreetMap, licence ODbL.
- Données ESA WorldCover 2021 : © ESA WorldCover project, licence CC BY 4.0.
- Le texte « By Dicxit(AE) » imprimé sur les cartes est un crédit : ne pas le retirer en cas de diffusion.

---

## Pour les développeurs

- **Sources** : `src/Carte_courbes_gui.pyw` (GUI), `src/carte_courbes.py` (moteur), `src/worldcover.py`, `src/osm_routes.py`.
- **Dépendances** (exécution depuis les sources) : Python 3, `numpy`, `scipy`, `Pillow`, `ijson` (voir `requirements.txt`).
- **Reconstruction de l’exécutable** (depuis `src/`, PyInstaller requis) :

```bash
pyinstaller --noconfirm --onefile --windowed --name Carte_AE --icon carte_courbes.ico --add-data "../style_AE.json;." --add-data "carte_courbes.ico;." --add-data "../Installation_FR.pdf;." --add-data "../Installation_EN.pdf;." --hidden-import scipy.ndimage --exclude-module matplotlib --exclude-module rasterio Carte_courbes_gui.pyw
```

Copier ensuite `dist/Carte_AE.exe` à la racine du projet. Les fichiers `style_*.json` doivent rester à côté de l’exécutable.
