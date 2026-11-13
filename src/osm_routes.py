"""Routes OpenStreetMap (grands axes) convertis en fichiers .npz compacts, un par paysage.

Chaque fichier contient :
  coords : (N, 2) lat, lon en degres (float32)
  debut  : index de debut de chaque route dans coords
  majeure: 1 pour autoroute/nationale, 0 pour les autres routes
Le .json brut d'OpenStreetMap est lu en flux (ijson) pour tenir en memoire.
"""
import os

import numpy as np

DOSSIER = r"D:\Condor3\OSM"
MAJEURES = {"motorway", "trunk", "primary"}


def convertir(nom):
    """routes_<nom>.json -> routes_<nom>.npz (sans effet si deja fait)."""
    import ijson
    source = os.path.join(DOSSIER, f"routes_{nom}.json")
    sortie = os.path.join(DOSSIER, f"routes_{nom}.npz")
    if os.path.exists(sortie):
        return sortie
    coords, debut, majeure = [], [], []
    total = 0
    with open(source, "rb") as f:
        for element in ijson.items(f, "elements.item"):
            geom = element.get("geometry")
            if not geom or len(geom) < 2:
                continue
            debut.append(total)
            majeure.append(1 if element.get("tags", {}).get("highway") in MAJEURES else 0)
            coords.extend((p["lat"], p["lon"]) for p in geom)
            total += len(geom)
    np.savez_compressed(sortie,
                        coords=np.asarray(coords, np.float32),
                        debut=np.asarray(debut, np.int64),
                        majeure=np.asarray(majeure, np.int8))
    return sortie


def charger(nom):
    """Routes du paysage 'nom' (None si pas de fichier)."""
    chemin = os.path.join(DOSSIER, f"routes_{nom}.npz")
    if not os.path.exists(chemin):
        return None
    d = np.load(chemin)
    return d["coords"], d["debut"], d["majeure"]


def convertir_eau(nom):
    """eau_<nom>.json (cours d'eau OSM) -> eau_<nom>.npz. Retourne le chemin ou None."""
    import ijson
    source = os.path.join(DOSSIER, f"eau_{nom}.json")
    sortie = os.path.join(DOSSIER, f"eau_{nom}.npz")
    if not os.path.exists(source):
        return None
    if os.path.exists(sortie):
        return sortie
    coords, debut, grande = [], [], []
    total = 0
    with open(source, "rb") as f:
        for element in ijson.items(f, "elements.item"):
            geom = element.get("geometry")
            if not geom or len(geom) < 2:
                continue
            debut.append(total)
            grande.append(1 if element.get("tags", {}).get("waterway") == "river" else 0)
            coords.extend((p["lat"], p["lon"]) for p in geom)
            total += len(geom)
    np.savez_compressed(sortie,
                        coords=np.asarray(coords, np.float32),
                        debut=np.asarray(debut, np.int64),
                        grande=np.asarray(grande, np.int8))
    return sortie


def charger_eau(nom):
    """Cours d'eau du paysage 'nom' : (coords, debut, grande) ou None."""
    chemin = os.path.join(DOSSIER, f"eau_{nom}.npz")
    if not os.path.exists(chemin):
        return None
    d = np.load(chemin)
    return d["coords"], d["debut"], d["grande"]
