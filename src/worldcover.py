"""Eau (lacs et mer) et zones baties a partir de ESA WorldCover 2021.
Classes utilisees : 80 = eau permanente, 50 = zones baties (urbain).

1. preparer_tuiles(classe, suffixe) : chaque tuile 3x3 deg -> grille de fraction
   de la classe (~83 m), enregistree en .npy a cote des .tif.
2. masque_eau(trn, suffixe) : pour chaque cellule de 90 m du paysage Condor, True si la
   cellule est majoritairement dans la classe demandee.
"""
import glob
import math
import os

import numpy as np

DOSSIER = r"F:\Claude travail\Condor3\Convertisseur_carte_AE\WorldCover"  # dossier du projet (prioritaire)
DOSSIER_SECOURS = r"D:\Condor3\WorldCover"  # utilise pour les tuiles absentes du dossier du projet
EAU = 80         # classe "permanent water bodies"
BATI = 50         # classe "built-up" (zones urbaines)
SUFFIXE_EAU = "_eau.npy"
SUFFIXE_BATI = "_bati.npy"
PAS = 9           # 36000 px (3 deg) -> 4000 px
COTE = 4000       # pixels par tuile dans la grille reduite


def nom_tuile(chemin):
    """'...N09E045_Map.tif' -> (lat_min, lon_min) en degres."""
    cle = os.path.basename(chemin).split("_v200_")[1].split("_Map")[0]
    lat = int(cle[1:3]) * (1 if cle[0] == "N" else -1)
    lon = int(cle[4:7]) * (1 if cle[3] == "E" else -1)
    return lat, lon


def preparer_tuiles(classe=EAU, suffixe=SUFFIXE_EAU):
    """Cree les grilles de fraction de la classe demandee, pour les tuiles manquantes."""
    import rasterio
    for tif in sorted(glob.glob(os.path.join(DOSSIER, "*.tif"))):
        sortie = tif[:-4] + suffixe
        if os.path.exists(sortie):
            continue
        with rasterio.open(tif) as src:
            fraction = np.zeros((COTE, COTE), np.uint8)
            bande = PAS * 500  # lignes lues d'un coup : memoire contenue
            for r0 in range(0, src.height, bande):
                lignes = min(bande, src.height - r0)
                bloc = src.read(1, window=((r0, r0 + lignes), (0, src.width)))
                voulu = (bloc == classe).astype(np.float32)
                voulu = voulu.reshape(lignes // PAS, PAS, COTE, PAS).mean(axis=(1, 3))
                fraction[r0 // PAS:r0 // PAS + voulu.shape[0]] = np.rint(voulu * 255).astype(np.uint8)
        np.save(sortie, fraction)
        print("ok", os.path.basename(sortie), flush=True)


def tuiles_disponibles(suffixe=SUFFIXE_EAU):
    """{(lat_min, lon_min): chemin .npy} pour les tuiles deja preparees.
    Le dossier du projet passe avant le dossier de secours : en cas de doublon, il gagne."""
    tuiles = {}
    for dossier in (DOSSIER, DOSSIER_SECOURS):
        for f in glob.glob(os.path.join(dossier, "*" + suffixe)):
            tuiles.setdefault(nom_tuile(f), f)
    return tuiles


def masque_eau(alt_shape, lat, lon, suffixe=SUFFIXE_EAU):
    """Masque True/False aux points (lat, lon) : True si la cellule est dans la classe.
    lat et lon sont des tableaux de meme forme que la carte."""
    tuiles = tuiles_disponibles(suffixe)
    sortie = np.zeros(alt_shape, np.float32)
    trouve = np.zeros(alt_shape, bool)
    for (la0, lo0), chemin in tuiles.items():
        dedans = (lat >= la0) & (lat < la0 + 3) & (lon >= lo0) & (lon < lo0 + 3)
        if not dedans.any():
            continue
        grille = np.load(chemin)
        r = np.clip(((la0 + 3 - lat[dedans]) / 3 * COTE).astype(int), 0, COTE - 1)
        c = np.clip(((lon[dedans] - lo0) / 3 * COTE).astype(int), 0, COTE - 1)
        sortie[dedans] = grille[r, c] / 255.0
        trouve |= dedans
    return sortie >= 0.5, trouve
