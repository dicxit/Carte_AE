"""
carte_courbes.py - Carte BMP 32 bits avec teinte d'altitude, ombrage et courbes
de niveau, a partir d'un fichier .raw de paysage Condor.

Utilisation :
  python carte_courbes.py                       (fenetres de choix de fichiers)
  python carte_courbes.py Cajamarca_Peru3.raw   (sortie : Cajamarca_Peru3_AE.bmp, ou _DGT selon le style)
  python carte_courbes.py fichier.raw -o sortie.bmp --maitresse 500 --inter 250

Convertir un .trn en .raw 16 bits sans en-tete, nord en haut (pour Photoshop) :
  python carte_courbes.py --convertir Cajamarca_Peru3.trn -o Cajamarca_Peru3.raw

Apprendre un nouveau style a partir d'une carte existante et de son .raw :
  python carte_courbes.py --apprendre modele.bmp modele.raw -p mon_style.json
"""
import argparse
import json
import os
import struct
import sys

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
if getattr(sys, "frozen", False):  # version .exe : reglages a cote de l'exe, ressources dans l'exe
    ICI = os.path.dirname(sys.executable)
    RESSOURCES = sys._MEIPASS
    # le style livre dans l'exe est recopie a cote de lui (dossier stable, modifiable)
    if not os.path.exists(os.path.join(ICI, "style_AE.json")):
        try:
            import shutil
            shutil.copy(os.path.join(RESSOURCES, "style_AE.json"), ICI)
        except OSError:
            pass
else:
    ICI = RESSOURCES = os.path.dirname(os.path.abspath(__file__))
STYLE_DEFAUT = next(p for p in (os.path.join(ICI, "style_AE.json"),
                                os.path.join(os.path.dirname(ICI), "style_AE.json"),  # mode source : styles a la racine du projet
                                os.path.join(RESSOURCES, "style_AE.json")) if os.path.exists(p))
RES_M = 90.0  # taille d'un point du .raw Condor, en metres


def suffixe_style(chemin_style):
    """Suffixe des cartes selon le style : style_AE.json -> _AE, style_DGT.json -> _DGT."""
    nom = os.path.splitext(os.path.basename(chemin_style))[0]
    return "_" + (nom[len("style_"):] if nom.startswith("style_") else nom)


class Arret(Exception):
    """Calcul arrete par l'utilisateur (bouton Stop)."""


# ---------------------------------------------------------------- lecture / ecriture

def lire_raw(chemin):
    """Lit un .trn Condor (ou sa copie renommee en .raw) et retourne la grille
    d'altitudes (m), orientee nord en haut comme la carte."""
    with open(chemin, "rb") as f:
        donnees = f.read()
    largeur, hauteur = struct.unpack("<ii", donnees[:8])
    if not (0 < largeur < 100000 and 0 < hauteur < 100000
            and len(donnees) == 36 + largeur * hauteur * 2):
        raise ValueError(f"{os.path.basename(chemin)} n'est pas un fichier .trn Condor "
                         "(un .raw deja converti n'a plus d'en-tete : utilisez le .trn)")
    alt = np.frombuffer(donnees, "<u2", count=largeur * hauteur, offset=36)
    # stocke par colonnes : rotation 90 deg + symetrie pour remettre le nord en haut
    return alt.reshape(largeur, hauteur).T[::-1, ::-1].astype(np.float32)


def lire_entete(chemin):
    """Calage du .trn : coin sud-est en UTM (m), fuseau, hemisphere."""
    with open(chemin, "rb") as f:
        w, h, _, _, _, e0, n0, zone, hemi = struct.unpack("<ii5fii", f.read(36))
    return {"w": w, "h": h, "est": e0, "nord": n0, "zone": zone, "sud": chr(hemi) == "S"}


def latlon_vers_utm(lat, lon, zone, sud):
    a, f, k0 = 6378137.0, 1 / 298.257223563, 0.9996
    e2 = f * (2 - f)
    ep2 = e2 / (1 - e2)
    la = np.radians(lat)
    lo = np.radians(lon - (zone * 6 - 183))
    n = a / np.sqrt(1 - e2 * np.sin(la) ** 2)
    t = np.tan(la) ** 2
    c = ep2 * np.cos(la) ** 2
    A = np.cos(la) * lo
    m = a * ((1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256) * la
             - (3 * e2 / 8 + 3 * e2 ** 2 / 32 + 45 * e2 ** 3 / 1024) * np.sin(2 * la)
             + (15 * e2 ** 2 / 256 + 45 * e2 ** 3 / 1024) * np.sin(4 * la)
             - (35 * e2 ** 3 / 3072) * np.sin(6 * la))
    x = k0 * n * (A + (1 - t + c) * A ** 3 / 6
                  + (5 - 18 * t + t * t + 72 * c - 58 * ep2) * A ** 5 / 120) + 500000
    y = k0 * (m + n * np.tan(la) * (A * A / 2 + (5 - t + 9 * c + 4 * c * c) * A ** 4 / 24
                                    + (61 - 58 * t + t * t + 600 * c - 330 * ep2) * A ** 6 / 720))
    return x, y + (10000000 if sud else 0)


# Le .cup ne distingue pas les villes des sommets, cols, lacs... : tri par mots du nom.
MOTS_PAS_VILLE = {
    # sommets
    "cote", "cerro", "cerros", "nevado", "pic", "pico", "piz", "pizzo", "cima", "punta", "gipfel",
    "spitze", "kogel", "monte", "mont", "mount", "mt", "shan", "peak", "volcan", "aiguille",
    "sierra", "cordillera", "nordspi", "sudspi", "oyu", "himal", "hermanos", "frailes",
    # cols
    "col", "colle", "pass", "passo", "paso", "joch", "sattel", "passe", "la",
    # eau, glaciers
    "lago", "lac", "laguna", "lagune", "lag", "see", "rio", "glaciar", "glacia", "glacier",
    "gletscher", "ghiacciaio", "embalse", "represa", "diga", "barrage", "stausee", "lake",
    # batiments isoles, installations
    "refuge", "rifugio", "hutte", "huette", "hütte", "haus", "cabane", "drehr", "mina", "mine",
    "foret", "castello", "chateau", "schloss", "burg", "tunnel", "antenne", "sender", "mast",
    "ul", "flugplatz", "aerodrome", "airport", "aeropuerto", "lift", "bergstation", "talstation",
    "kloster", "abbaye", "wallfa", "relais", "ferme", "hof",
}
SUFFIXES_VILLE = {"gare", "bf", "bahnhof", "stazione", "chp", "kirche", "chiesa", "eglise", "eg",
                  "village", "dorf", "district", "n", "s", "e", "w", "ne", "nw", "se", "sw", "ost",
                  "west", "nord", "sud", "sued", "centre", "zentrum", "pont", "brucke", "ponte",
                  "c", "stift", "kir", "sce"}


def nom_de_ville(nom):
    """Nom de ville/village nettoye, ou None si le point n'est pas une localite."""
    mots = nom.replace("-", " ").split()
    bas = [m.lower().strip(".,()") for m in mots]
    if not mots or any(m in MOTS_PAS_VILLE for m in bas):
        return None
    if any(ch.isdigit() for ch in nom) or (nom.isupper() and len(nom) > 2):
        return None  # codes de balises, altitudes
    while len(mots) > 1 and bas[-1] in SUFFIXES_VILLE:
        mots.pop()
        bas.pop()
    return " ".join(mots)


def utm_vers_latlon(x, y, zone, sud):
    """Inverse de latlon_vers_utm (formules de Snyder)."""
    a, f, k0 = 6378137.0, 1 / 298.257223563, 0.9996
    e2 = f * (2 - f)
    ep2 = e2 / (1 - e2)
    x = x - 500000.0
    y = y - (10000000.0 if sud else 0.0)
    m = y / k0
    mu = m / (a * (1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256))
    e1 = (1 - np.sqrt(1 - e2)) / (1 + np.sqrt(1 - e2))
    phi1 = (mu + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * np.sin(2 * mu)
            + (21 * e1 ** 2 / 16 - 55 * e1 ** 4 / 32) * np.sin(4 * mu)
            + (151 * e1 ** 3 / 96) * np.sin(6 * mu)
            + (1097 * e1 ** 4 / 512) * np.sin(8 * mu))
    n1 = a / np.sqrt(1 - e2 * np.sin(phi1) ** 2)
    t1 = np.tan(phi1) ** 2
    c1 = ep2 * np.cos(phi1) ** 2
    r1 = a * (1 - e2) / (1 - e2 * np.sin(phi1) ** 2) ** 1.5
    d = x / (n1 * k0)
    lat = phi1 - (n1 * np.tan(phi1) / r1) * (
        d ** 2 / 2 - (5 + 3 * t1 + 10 * c1 - 4 * c1 ** 2 - 9 * ep2) * d ** 4 / 24
        + (61 + 90 * t1 + 298 * c1 + 45 * t1 ** 2 - 252 * ep2 - 3 * c1 ** 2) * d ** 6 / 720)
    lon = ((zone * 6 - 183) * np.pi / 180
           + (d - (1 + 2 * t1 + c1) * d ** 3 / 6
              + (5 - 2 * c1 + 28 * t1 - 3 * c1 ** 2 + 8 * ep2 + 24 * t1 ** 2) * d ** 5 / 120)
           / np.cos(phi1))
    return np.degrees(lat), np.degrees(lon)


def lacs_worldcover(trn):
    """Lacs (eau de l'interieur des terres) selon ESA WorldCover, meme grille que le
    .trn. Retourne None si les tuiles WorldCover ne couvrent pas ce paysage."""
    return masque_worldcover(trn, "_eau.npy")


def bati_worldcover(trn):
    """Zones baties (urbain) selon ESA WorldCover, meme grille que le .trn.
    Retourne None si les tuiles WorldCover 'bati' ne couvrent pas ce paysage."""
    return masque_worldcover(trn, "_bati.npy")


def masque_worldcover(trn, suffixe):
    """Masque WorldCover (classe eau ou bati selon le suffixe) sur la grille du .trn."""
    try:
        import worldcover
    except ImportError:
        return None
    if not worldcover.tuiles_disponibles(suffixe):
        return None
    entete = lire_entete(trn)
    w, h, e0, n0 = entete["w"], entete["h"], entete["est"], entete["nord"]
    eau = np.zeros((h, w), bool)
    couvert = np.zeros((h, w), bool)
    colonnes = e0 - w * RES_M + (np.arange(w) + 0.5) * RES_M
    for r0 in range(0, h, 400):
        lignes_ = np.arange(r0, min(r0 + 400, h))
        y = n0 + (h - 1 - lignes_ + 0.5) * RES_M
        x, yy = np.meshgrid(colonnes, y)
        lat, lon = utm_vers_latlon(x, yy, entete["zone"], entete["sud"])
        masque, trouve = worldcover.masque_eau((len(lignes_), w), lat, lon, suffixe)
        eau[lignes_] = masque
        couvert[lignes_] = trouve
    if not couvert.any():
        return None
    return eau & couvert


def lire_villes(cup, entete):
    """Villes et villages du .cup -> [(nom, colonne, ligne)]."""
    def degres(s):  # 0654.485S / 07951.822W
        nd = len(s.split(".")[0]) - 2
        v = int(s[:nd]) + float(s[nd:-1]) / 60
        return -v if s[-1] in "SW" else v
    villes = []
    with open(cup, encoding="latin-1") as f:
        for ligne in f:
            p = ligne.strip().split(",")
            if len(p) < 7 or not p[3][:1].isdigit():
                continue
            nom = nom_de_ville(p[0].strip('"'))
            if not nom:
                continue
            x, y = latlon_vers_utm(degres(p[3]), degres(p[4]), entete["zone"], entete["sud"])
            col = (x - (entete["est"] - entete["w"] * RES_M)) / RES_M
            lig = entete["h"] - 1 - (y - entete["nord"]) / RES_M
            if 0 <= col < entete["w"] and 0 <= lig < entete["h"]:
                villes.append((nom, int(col), int(lig)))
    return villes


def mer(alt):
    """Mer = zones a 0 m reliees au bord de la carte ; les terres basses isolees
    (deltas, polders a 0 m) et les fils etroits ne comptent pas."""
    from scipy import ndimage
    zero = ndimage.binary_opening(alt <= 0, iterations=2)
    zones, n = ndimage.label(zero)
    if n == 0:
        return alt <= 0
    bords = np.unique(np.concatenate([zones[0], zones[-1], zones[:, 0], zones[:, -1]]))
    garde = np.zeros(n + 1, bool)
    garde[bords] = True
    garde[0] = False
    return ndimage.binary_closing(garde[zones], iterations=2) & (alt <= 0) | garde[zones]


def lacs(alt, surface_min=40, bord_bas_max=0.05, rive_min=6.0):
    """Lacs = grandes zones parfaitement plates, entourees de terrain plus haut.
    Une plaine plate (Po, Baviere...) a des voisins plus bas : ce n'est pas un lac."""
    from scipy import ndimage
    plat = (ndimage.minimum_filter(alt, 3) == ndimage.maximum_filter(alt, 3)) & (alt > 0)
    zones, n = ndimage.label(plat)
    if n == 0:
        return np.zeros(alt.shape, bool)
    taille = np.bincount(zones.ravel(), minlength=n + 1)
    candidat = taille >= surface_min
    candidat[0] = False
    zones = np.where(candidat[zones], zones, 0)
    # bord exterieur de chaque zone : part des voisins plus bas que la surface du lac
    proche = ndimage.grey_dilation(zones, size=5)
    bord = (zones == 0) & (proche > 0)
    niveau = ndimage.maximum(alt, zones, np.arange(n + 1))
    niveau = np.nan_to_num(np.asarray(niveau, float))
    lb = proche[bord]
    plus_bas = alt[bord] < niveau[lb] - 0.5
    total = np.bincount(lb, minlength=n + 1)
    bas = np.bincount(lb, weights=plus_bas, minlength=n + 1)
    # la rive doit monter franchement (un creux de plaine ne monte que d'un ou deux metres)
    anneau = ndimage.grey_dilation(zones, size=11)
    anneau_px = (zones == 0) & (anneau > 0)
    la = anneau[anneau_px]
    # float forces : bincount renvoie des entiers quand la liste est vide (carte sans rive)
    montee = np.bincount(la, weights=np.clip(alt[anneau_px] - niveau[la], 0, 40),
                         minlength=n + 1).astype(float)
    compte = np.bincount(la, minlength=n + 1).astype(float)
    montee = montee / np.maximum(compte, 1)
    lac = candidat & (bas <= bord_bas_max * np.maximum(total, 1)) & (montee >= rive_min)
    lac[0] = False
    return ndimage.binary_dilation(lac[zones])


def ecoulement(alt, max_pixels=8_000_000):
    """Surface drainee (en pixels de la carte). Inondation par priorite depuis la mer
    et les bords : les creux se remplissent, les rivieres restent continues."""
    import heapq
    f = int(np.ceil(np.sqrt(alt.size / max_pixels)))  # grandes cartes : calcul reduit
    if f > 1:
        alt = alt[:alt.shape[0] // f * f, :alt.shape[1] // f * f]
        alt = alt.reshape(alt.shape[0] // f, f, alt.shape[1] // f, f).min(axis=(1, 3))
    h, w = alt.shape
    n = h * w
    z = alt.ravel().tolist()
    vu = bytearray(n)
    aval = [-1] * n
    depart = np.zeros(alt.shape, bool)
    depart[0] = depart[-1] = depart[:, 0] = depart[:, -1] = True
    depart |= alt <= 0
    tas = []
    for i in np.flatnonzero(depart).tolist():
        vu[i] = 1
        tas.append((z[i], i))
    heapq.heapify(tas)
    ordre = []
    voisins = (-w - 1, -w, -w + 1, -1, 1, w - 1, w, w + 1)
    while tas:
        zc, i = heapq.heappop(tas)
        ordre.append(i)
        x = i % w
        for d in voisins:
            j = i + d
            if j < 0 or j >= n or vu[j] or abs(j % w - x) > 1:
                continue
            vu[j] = 1
            aval[j] = i
            heapq.heappush(tas, (max(z[j], zc), j))
    surface = [1.0] * n
    for i in reversed(ordre):
        if aval[i] >= 0:
            surface[aval[i]] += surface[i]
    return np.array(surface) * f * f, np.array(aval), w, f


def segments_rivieres(alt, seuil=None):
    """Rivieres : segments de chaque point vers son point aval (coordonnees en pixels
    de la carte), plus epais quand la surface drainee augmente."""
    seuil = seuil or SEUIL_RIVIERE
    surface, aval, w, f = ecoulement(alt)
    morceaux = []
    for facteur, epaisseur in ((1, 0.8), (15, 1.4), (100, 2.0)):
        i = np.flatnonzero((surface > seuil * facteur) & (aval >= 0))
        j = aval[i]
        morceaux.append(np.stack([(i % w + 0.5) * f, (i // w + 0.5) * f,
                                  (j % w + 0.5) * f, (j // w + 0.5) * f,
                                  np.full(len(i), epaisseur)], 1))
    return np.concatenate(morceaux)


def tracer_rivieres(riv, origine, forme, q):
    """Masque des rivieres pour un bloc (origine en pixels de carte, forme sur-echantillonnee)."""
    from PIL import ImageDraw
    ox, oy = origine
    hh, ww = forme[0] / q, forme[1] / q
    dedans = ((np.maximum(riv[:, 0], riv[:, 2]) >= ox - 3) & (np.minimum(riv[:, 0], riv[:, 2]) <= ox + ww + 3)
              & (np.maximum(riv[:, 1], riv[:, 3]) >= oy - 3) & (np.minimum(riv[:, 1], riv[:, 3]) <= oy + hh + 3))
    masque = Image.new("L", (forme[1], forme[0]), 0)
    d = ImageDraw.Draw(masque)
    for x0, y0, x1, y1, e in riv[dedans].tolist():
        larg = max(1, round(e * q))
        pts = [(x0 - ox) * q, (y0 - oy) * q, (x1 - ox) * q, (y1 - oy) * q]
        d.line(pts, fill=255, width=larg)
        if larg > 2:  # jonctions arrondies
            r = larg / 2
            d.ellipse((pts[2] - r, pts[3] - r, pts[2] + r, pts[3] + r), fill=255)
    return np.asarray(masque) > 0


LISERE = 0.7  # epaisseur du lisere blanc autour des lettres, en pixels de carte


ESPACE_LETTRES = 9  # ecart entre lettres, en pixels de dessin (10 par pixel de carte)


def largeur_espacee(texte, police, espace):
    return sum(police.getlength(c) for c in texte) + espace * (len(texte) - 1)


def ecrire_espace(dessin, xy, texte, police, espace, **kw):
    """Ecrit le texte lettre par lettre, avec un ecart fixe entre elles."""
    x, y = xy
    for c in texte:
        dessin.text((x, y), c, font=police, **kw)
        x += police.getlength(c) + espace


def dessiner_villes(rgb, villes, taille=9, lisere=LISERE, texte=(0, 0, 0), halo=(255, 255, 255)):
    """Noms en Arial (noir par defaut), avec un fin lisere autour des lettres.
    Chaque nom est dessine 10x plus grand puis reduit : le lisere peut etre plus fin
    qu'un pixel. Un nom qui chevaucherait un nom deja ecrit est omis."""
    from PIL import ImageDraw, ImageFont
    E = 10  # facteur de dessin
    try:
        police = ImageFont.truetype("arial.ttf", taille * E)
    except OSError:
        police = ImageFont.load_default()
    corps = 0  # pas d epaississement du noir : Arial normal, lettres fines
    trait = corps + max(1, round(lisere * E))
    sortie = rgb.astype(np.float32)
    h, w = rgb.shape[:2]
    pris = np.zeros((h, w), bool)
    mesure = ImageDraw.Draw(Image.new("L", (1, 1)))
    for nom, x, y in villes:
        _, t, _, b = mesure.textbbox((0, 0), nom, font=police, stroke_width=trait)
        r = largeur_espacee(nom, police, ESPACE_LETTRES) + 2 * trait
        # boite du nom + point, en pixels de carte
        bx0, by0 = int(x) - 3, int(y - taille / 2) - 3
        bw = int(np.ceil((r + 4 * E) / E)) + 6
        bh = int(np.ceil(max(b, 6 * E) / E)) + 6
        zone = (slice(max(by0, 0), min(by0 + bh, h)), slice(max(bx0, 0), min(bx0 + bw, w)))
        if pris[zone].any() or zone[0].start >= zone[0].stop or zone[1].start >= zone[1].stop:
            continue
        pris[zone] = True
        dehors = Image.new("L", (bw * E, bh * E), 0)
        dedans = Image.new("L", (bw * E, bh * E), 0)
        dd, di = ImageDraw.Draw(dehors), ImageDraw.Draw(dedans)
        px, py = (x - bx0) * E, (y - by0) * E  # le point de la ville
        tx, ty = px + 3 * E, py - taille * E / 2 - E
        ecrire_espace(dd, (tx, ty), nom, police, ESPACE_LETTRES, fill=0, stroke_width=trait, stroke_fill=255)
        ecrire_espace(di, (tx, ty), nom, police, ESPACE_LETTRES, fill=255, stroke_width=corps, stroke_fill=255)
        rp = 1.5 * E
        dd.ellipse((px - rp - trait, py - rp - trait, px + rp + trait, py + rp + trait), fill=255)
        di.ellipse((px - rp, py - rp, px + rp, py + rp), fill=255)
        a_blanc = np.asarray(dehors.resize((bw, bh), Image.BOX), np.float32) / 255 * (120 / 255)
        a_noir = np.asarray(dedans.resize((bw, bh), Image.BOX), np.float32) / 255
        # decoupe si le nom deborde du bord de la carte
        oy, ox = zone[0].start - by0, zone[1].start - bx0
        sl = (slice(oy, oy + zone[0].stop - zone[0].start), slice(ox, ox + zone[1].stop - zone[1].start))
        ab, an = a_blanc[sl][..., None], a_noir[sl][..., None]
        bloc = sortie[zone]
        bloc = bloc * (1 - ab) + np.array(halo, np.float32) * ab
        sortie[zone] = bloc * (1 - an) + np.array(texte, np.float32) * an
    return np.clip(np.rint(sortie), 0, 255).astype(np.uint8)


def convertir_trn(trn, raw):
    """.trn Condor -> .raw 16 bits sans en-tete, nord en haut (pour Photoshop)."""
    alt = lire_raw(trn)
    alt.astype("<u2").tofile(raw)
    return alt.shape[1], alt.shape[0]


def ecrire_bmp32(chemin, rgb):
    """BMP 32 bits non compresse, identique au format des cartes Condor."""
    h, w, _ = rgb.shape
    taille = w * h * 4
    pixels = np.zeros((h, w, 4), np.uint8)
    pixels[..., 0] = rgb[..., 2]
    pixels[..., 1] = rgb[..., 1]
    pixels[..., 2] = rgb[..., 0]
    entete = struct.pack("<2sIHHI", b"BM", 54 + taille, 0, 0, 54)
    info = struct.pack("<IiiHHIIiiII", 40, w, h, 1, 32, 0, taille, 2834, 2834, 0, 0)
    with open(chemin, "wb") as f:
        f.write(entete + info)
        f.write(pixels[::-1].tobytes())  # lignes de bas en haut


# ---------------------------------------------------------------- calculs

def relief(alt, res=RES_M):
    gy, gx = np.gradient(alt, res)
    return np.arctan(np.hypot(gx, gy)), np.arctan2(-gx, gy)


def ombrage(pente, aspect, azimut, hauteur):
    zen = np.radians(90 - hauteur)
    return (np.cos(zen) * np.cos(pente)
            + np.sin(zen) * np.sin(pente) * np.cos(np.radians(azimut) - aspect))


def lignes(alt, pas, epaisseur=1):
    """Pixels situes juste au-dessous d'un multiple de `pas` (trait de 1 pixel),
    ou bande de `epaisseur` pixels de part et d'autre en rendu sur-echantillonne."""
    if epaisseur > 1:
        from scipy import ndimage
        niveau = np.floor(alt / pas)
        return ((ndimage.maximum_filter(niveau, epaisseur + 1)
                 != ndimage.minimum_filter(niveau, epaisseur + 1)) & (alt > 0))
    niveau = np.pad(np.floor(alt / pas), 1, mode="edge")
    centre = niveau[1:-1, 1:-1]
    trait = ((centre < niveau[:-2, 1:-1]) | (centre < niveau[2:, 1:-1])
             | (centre < niveau[1:-1, :-2]) | (centre < niveau[1:-1, 2:]))
    return trait & (alt > 0)


COULEUR_RIVIERE = (35, 95, 165)
SEUIL_RIVIERE = 800  # surface drainee minimale, en pixels de 90 m (~6.5 km2) : rivieres fines


# altitude (m) -> (couleur RGB ou None = couleur de la courbe maitresse, opacite,
#                  surepaisseur : part d'une bande supplementaire peinte en plus)
SURLIGNAGE = {
    1000: (None, 0.4, 0.05),
    2000: ((0, 200, 0), 0.25, 0.0),
    3000: ((128, 0, 32), 0.15, 0.05),
}
# altitudes a ne pas surligner (ex. 4000 m est aussi multiple de 1000 et de 2000)
EXCLUSIONS = {1000: (4000,), 2000: (4000,)}
QUALITES = {"Normale": 1, "Haute": 2, "Maximale": 4}
URBAIN_SURFACE_MIN = 250  # taille minimale d'une zone urbaine, en cellules de 90 m (~2 km2)
URBAIN_FLOU = 0.5         # flou des bords des zones urbaines, en pixels
COURBES_LISSAGE = 2.0     # lissage du relief avant les courbes, en pixels de 90 m (bruit du .trn)
RUGOSITE_MIN = 15.0       # ecart-type local (m) en dessous duquel le relief est considere plat
RUGOSITE_MAX = 40.0       # au-dessus, le relief est intact (pas de lissage)
TUILE = 512  # rendu par morceaux : la memoire reste faible meme en qualite maximale


def fabriquer_carte(alt, style, maitresse, inter, eau=True, villes=(), qualite=1,
                    progression=None, lacs_wc=None, routes=None, cours_eau=None, bati=None):
    """Rendu de la carte. qualite = facteur de sur-echantillonnage : chaque pixel est
    calcule sur qualite x qualite points (relief interpole en bicubique), puis moyenne.
    Courbes, cotes, rivieres et lacs sont alors lisses et sans escaliers."""
    from scipy import ndimage
    q = int(qualite)
    h, w = alt.shape
    mer_ = mer(alt)
    # eau : privilegier le masque raster WorldCover pour les surfaces d'eau (formes naturelles),
    # et les cours d'eau OSM (lisses, sans ruisseaux) pour garantir la visibilite des rivieres/fleuves.
    eau_wc = lacs_wc if (eau and lacs_wc is not None and getattr(lacs_wc, "any", lambda: False)()) else None
    if eau:
        if eau_wc is not None:
            lac = eau_wc > 0.5
            # retirer seulement les tres petits elements (ruisseaux/residus), sans eroder les rivieres
            etiquettes, n = ndimage.label(lac)
            if n:
                tailles = np.bincount(etiquettes.ravel())
                garde = tailles >= 25
                garde[0] = False
                lac = garde[etiquettes]
            # leger lissage des contours des surfaces d'eau raster
            lac = ndimage.gaussian_filter(lac.astype(np.float32), sigma=0.8) > 0.45
            riv = None  # pas de rivieres en segments ; garder cours_eau OSM (lisse) si disponible
        else:
            lac = lacs_wc if lacs_wc is not None else lacs(alt)
            riv = None
    else:
        lac = None
        riv = None
        cours_eau = None
    # fort denivele : le point le plus haut prend la couleur la plus haute du modele
    # et le degrade descend jusqu'en bas (sinon tout ce qui depasse le modele est uniforme)
    plafond = len(style["couleurs"]) * style["pas"]
    etirement = min(1.0, plafond / max(float(alt.max()), 1.0))
    sortie = np.empty((h, w, 3), np.uint8)
    marge = 16  # assez large pour que le lissage des courbes ne laisse pas de couture entre tuiles
    tuiles = [(y, x) for y in range(0, h, TUILE) for x in range(0, w, TUILE)]
    for n, (y0, x0) in enumerate(tuiles):
        y1, x1 = min(y0 + TUILE, h), min(x0 + TUILE, w)
        a0, b0 = max(y0 - marge, 0), max(x0 - marge, 0)
        a1, b1 = min(y1 + marge, h), min(x1 + marge, w)
        bloc = rendre_bloc(alt[a0:a1, b0:b1], style, maitresse, inter, q,
                           mer_[a0:a1, b0:b1], None if lac is None else lac[a0:a1, b0:b1],
                           riv, (b0, a0), etirement)
        sortie[y0:y1, x0:x1] = bloc[y0 - a0:y1 - a0, x0 - b0:x1 - b0]
        if progression:
            progression((n + 1) / len(tuiles))
    if q > 1 and style.get("nettete"):
        # le sur-echantillonnage adoucit : on rend la texture fine du relief comme le modele
        from PIL import ImageFilter
        sortie = np.asarray(Image.fromarray(sortie).filter(
            ImageFilter.UnsharpMask(radius=1, percent=style["nettete"], threshold=0)))
    if bati is not None and style.get("urbain"):
        # zones urbaines (WorldCover) en aplat, hors mer et lacs ; riviere et routes par-dessus
        u = style["urbain"]
        zone = bati & ~mer_
        if lac is not None:
            zone &= ~lac
        # on garde les agglomerations (villes, villages) : les petites taches isolees partent
        etiquettes, n = ndimage.label(zone)
        if n:
            tailles = np.bincount(etiquettes.ravel())
            garde = tailles >= URBAIN_SURFACE_MIN
            garde[0] = False
            zone = garde[etiquettes]
        couleur = np.array(u["couleur"], np.float32)
        # bords estompes : le masque est flou, la couleur se fond dans le relief autour
        alpha = ndimage.gaussian_filter(zone.astype(np.float32), sigma=URBAIN_FLOU) * u.get("opacite", 1.0)
        alpha = np.clip(alpha, 0, 1)[..., None]
        sortie = np.rint(sortie * (1 - alpha) + couleur * alpha).astype(np.uint8)
    if eau and cours_eau is not None:
        # ne pas exclure les surfaces d'eau raster pour que les rivieres OSM lissees restent visibles
        sortie = dessiner_cours_eau(sortie, cours_eau, exclure=mer_)
    if routes is not None:
        sortie = dessiner_routes(sortie, routes)
    sat = style.get("saturation", 1.0)  # <1 : couleurs plus douces
    if sat != 1.0:
        gris = sortie.astype(np.float32) @ np.array([0.299, 0.587, 0.114], np.float32)
        sortie = np.clip(np.rint(gris[..., None] + (sortie.astype(np.float32) - gris[..., None]) * sat), 0, 255).astype(np.uint8)
    if villes:
        v = style.get("villes", {})
        sortie = dessiner_villes(sortie, villes, texte=v.get("texte", (0, 0, 0)), halo=v.get("halo", (255, 255, 255)))
    return dessiner_legende(sortie, style)


COULEUR_ROUTE = (230, 220, 170)


def routes_du_paysage(trn):
    """Routes OpenStreetMap du paysage, projetees sur la grille de la carte.
    Retourne None si aucune route n'a ete telechargee pour ce paysage."""
    import osm_routes
    nom = os.path.splitext(os.path.basename(trn))[0]
    donnees = osm_routes.charger(nom)
    if donnees is None:
        return None
    coords, debut, majeure = donnees
    e = lire_entete(trn)
    x, y = latlon_vers_utm(coords[:, 0].astype(float), coords[:, 1].astype(float),
                           e["zone"], e["sud"])
    colonne = (x - (e["est"] - e["w"] * RES_M)) / RES_M
    ligne = (e["h"] - 1) - (y - e["nord"]) / RES_M
    pts = np.stack([colonne, ligne], 1)
    fin = np.append(debut[1:], len(coords))
    return pts, debut, fin, majeure


def cours_eau_du_paysage(trn):
    """Cours d'eau OpenStreetMap du paysage, projetes sur la grille de la carte.
    Retourne None si aucun cours d'eau n'a ete telecharge pour ce paysage."""
    import osm_routes
    nom = os.path.splitext(os.path.basename(trn))[0]
    donnees = osm_routes.charger_eau(nom)
    if donnees is None:
        return None
    coords, debut, grande = donnees
    e = lire_entete(trn)
    x, y = latlon_vers_utm(coords[:, 0].astype(float), coords[:, 1].astype(float),
                           e["zone"], e["sud"])
    colonne = (x - (e["est"] - e["w"] * RES_M)) / RES_M
    ligne = (e["h"] - 1) - (y - e["nord"]) / RES_M
    pts = np.stack([colonne, ligne], 1)
    fin = np.append(debut[1:], len(coords))
    return pts, debut, fin, grande


def lisser(pts, passes=3):
    """Lissage de Chaikin : chaque segment est coupe au quart et aux trois quarts."""
    for _ in range(passes):
        if len(pts) < 3:
            break
        a, b = pts[:-1], pts[1:]
        q = 0.75 * a + 0.25 * b
        r = 0.25 * a + 0.75 * b
        nouveaux = np.empty((2 * len(a), 2), float)
        nouveaux[0::2] = q
        nouveaux[1::2] = r
        pts = np.vstack([pts[:1], nouveaux, pts[-1:]])
    return pts


def _tracer_lisse(rgb, pts, debut, fin, classe, niveaux, couleur, exclure=None):
    """Polylignes lissees (Chaikin), dessinees a double resolution puis reduites :
    contours continus, sans escaliers. niveaux[k] = (opacite, largeur) pour la classe k."""
    from PIL import ImageDraw
    S = 2
    h, w = rgb.shape[:2]
    sortie = rgb.astype(np.float32)
    for k, (opacite, largeur) in enumerate(niveaux):
        if opacite <= 0:
            continue
        masque = Image.new("L", (w * S, h * S), 0)
        dessin = ImageDraw.Draw(masque)
        for i in np.flatnonzero(classe == k):
            segment = pts[debut[i]:fin[i]].astype(float)
            if len(segment) < 2:
                continue
            segment = lisser(segment) * S
            dessin.line([(float(p[0]), float(p[1])) for p in segment],
                        fill=255, width=max(1, round(largeur * S)))
        masque = masque.resize((w, h), Image.BOX)
        alpha = np.asarray(masque, np.float32)[..., None] / 255 * opacite
        if exclure is not None:  # pas de trait sur les lacs
            alpha = alpha * (~exclure)[..., None]
        sortie = sortie * (1 - alpha) + np.array(couleur, np.float32) * alpha
    return np.clip(np.rint(sortie), 0, 255).astype(np.uint8)


def dessiner_cours_eau(rgb, cours, exclure=None):
    """Cours d'eau OpenStreetMap : rivieres plus marquees que les petits cours d'eau."""
    pts, debut, fin, grande = cours
    return _tracer_lisse(rgb, pts, debut, fin, grande,
                         [(0, 1), (0.7, 1.4)], COULEUR_RIVIERE, exclure=exclure)  # ruisseaux non dessines


def dessiner_routes(rgb, routes):
    """Routes nationales seulement, lissees et anti-crenelees."""
    pts, debut, fin, majeure = routes
    return _tracer_lisse(rgb, pts, debut, fin, majeure,
                         [(0, 0), (0.35, 1)], COULEUR_ROUTE)


def dessiner_legende(rgb, style):
    """Lexique des courbes colorees dans le coin inferieur gauche, et mention du createur."""
    from PIL import ImageDraw, ImageFont
    h, w = rgb.shape[:2]
    img = Image.fromarray(rgb).convert("RGBA")
    calque = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(calque)
    try:
        police = ImageFont.truetype("arial.ttf", 12)
        petite = ImageFont.truetype("arial.ttf", 8)
    except OSError:
        police = petite = ImageFont.load_default()
    entrees = [(f"{alt} m", couleur or style["courbes"]["couleur_maitresse"], opacite)
               for alt, (couleur, opacite, _) in sorted(SURLIGNAGE.items())]
    marge, ligne = 10, 18
    hauteur = 10 + ligne * len(entrees) + 16
    x0, y0 = marge, h - marge - hauteur
    d.rounded_rectangle((x0, y0, x0 + 96, y0 + hauteur), 6, fill=(255, 255, 255, 255))
    for k, (texte, couleur, opacite) in enumerate(entrees):
        y = y0 + 10 + k * ligne
        nette = tuple(int(v) for v in couleur)  # couleur pleine, reconnaissable
        d.rectangle((x0 + 8, y + 3, x0 + 30, y + 9), fill=nette + (255,))
        d.text((x0 + 36, y), texte, font=police, fill=(0, 0, 0, 255))
    d.text((x0 + 8, y0 + hauteur - 14), "By Dicxit(AE)", font=petite, fill=(70, 70, 70, 255))
    return np.asarray(Image.alpha_composite(img, calque).convert("RGB"))


def relief_courbes(terre, q):
    """Relief pour les courbes : lisse dans les zones plates (le bruit du .trn y fait des
    points et des boucles), intact dans le relief, ou le lissage effacerait les courbes."""
    from scipy import ndimage
    lisse = ndimage.gaussian_filter(terre, COURBES_LISSAGE * q)
    s = 3.0 * q
    moyenne = ndimage.gaussian_filter(terre, s)
    ecart = np.sqrt(np.maximum(ndimage.gaussian_filter(terre * terre, s) - moyenne * moyenne, 0))
    plat = np.clip((RUGOSITE_MAX - ecart) / (RUGOSITE_MAX - RUGOSITE_MIN), 0, 1)
    return terre * (1 - plat) + lisse * plat


def rendre_bloc(alt, style, maitresse, inter, q, mer, lac, riv, origine, etirement=1.0):
    from scipy import ndimage
    if q > 1:
        zoom = dict(zoom=q, grid_mode=True, mode="nearest")
        alt = ndimage.zoom(alt, order=3, **zoom)
        mer = ndimage.zoom(mer.astype(np.float32), order=1, **zoom) > 0.5
        if lac is not None:
            lac = ndimage.zoom(lac.astype(np.float32), order=1, **zoom) > 0.5
    terre = np.maximum(alt, 0)
    # courbes calculees sur un relief lisse : le bruit du .trn (quelques metres) ne forme plus
    # de petites boucles ni de points noirs autour de chaque niveau
    courbes = relief_courbes(terre, q)

    # teinte continue (interpolation entre les tranches de la palette)
    pas = style["pas"]
    couleurs = np.array(style["couleurs"], np.float32)
    centres = (np.arange(len(couleurs)) + 0.5) * pas
    rgb = np.stack([np.interp(terre * etirement, centres, couleurs[:, c]) for c in range(3)], -1)

    o = style["ombrage"]
    hs = ombrage(*relief(alt, RES_M / q), o["azimut"], o["hauteur"])
    rgb *= (np.clip(o["k"] * hs + o["b"], 0.3, 2.5) * o.get("gain", 1.0))[..., None]

    rgb[mer] = style["mer"]
    c = style["courbes"]
    trait = max(1, round(q * 0.75)) if q > 1 else 1  # ~1 pixel de carte apres moyenne
    if inter:
        rgb[lignes(courbes, inter, trait) & ~mer] *= c["facteur_inter"]
    avant = rgb.copy()  # relief sans courbes maitresses : sert aux courbes surlignees
    if maitresse:
        rgb[lignes(courbes, maitresse, trait) & ~mer] = c["couleur_maitresse"]
    # courbes d'altitudes remarquables, par-dessus les courbes maitresses
    for altitude, (couleur, opacite, surep) in SURLIGNAGE.items():
        couleur = np.array(couleur or c["couleur_maitresse"], np.float32)
        base = lignes(courbes, altitude, trait) & ~mer
        for exclue in EXCLUSIONS.get(altitude, ()):
            base &= ~lignes(courbes, exclue, trait)
        if surep:  # bande d'epaisseur en plus, peinte a faible opacite
            anneau = (lignes(courbes, altitude, trait + 1) & ~mer) & ~base
            rgb[anneau] = rgb[anneau] * (1 - surep) + couleur * surep
        rgb[base] = avant[base] * (1 - opacite) + couleur * opacite
    if riv is not None:
        rgb[tracer_rivieres(riv, origine, alt.shape, q) & ~mer] = COULEUR_RIVIERE
    if lac is not None:
        rgb[lac] = style["mer"]
    if q > 1:  # moyenne de chaque groupe q x q -> anticrenelage
        hh, ww = rgb.shape[0] // q, rgb.shape[1] // q
        rgb = rgb[:hh * q, :ww * q].reshape(hh, q, ww, q, 3).mean(axis=(1, 3))
    return np.clip(np.rint(rgb), 0, 255).astype(np.uint8)


def villes_du_paysage(chemin):
    """Cherche le .cup a cote du .trn, ou dans Landscapes/<nom>/ pour une copie .raw."""
    nom = os.path.splitext(os.path.basename(chemin))[0]
    for cup in (os.path.splitext(chemin)[0] + ".cup",
                os.path.join(r"D:\Condor3\Landscapes", nom, nom + ".cup")):
        if os.path.exists(cup):
            return lire_villes(cup, lire_entete(chemin))
    return []


# ---------------------------------------------------------------- apprentissage d'un style

def apprendre(bmp, raw, sortie, maitresse=500, inter=250, pas=10):
    alt = lire_raw(raw)
    img = np.asarray(Image.open(bmp).convert("RGB")).astype(np.float32)
    if img.shape[:2] != alt.shape:
        sys.exit(f"Dimensions differentes : carte {img.shape[:2]}, raw {alt.shape}")
    r, g, b = img[..., 0], img[..., 1], img[..., 2]
    lum = img.sum(2)
    eau = (b > r + 20) & (b > g)
    terre = (alt > 0) & ~eau

    # couleur mediane par tranche d'altitude, sans les traits sombres
    tranche = (alt // pas).astype(int)
    n = tranche.max() + 1
    t, cols, l = tranche[terre], img[terre], lum[terre]
    ordre = np.argsort(t, kind="stable")
    t, cols, l = t[ordre], cols[ordre], l[ordre]
    debut = np.searchsorted(t, np.arange(n))
    fin = np.searchsorted(t, np.arange(n), "right")
    couleurs = np.full((n, 3), np.nan)
    for k in range(n):
        if fin[k] - debut[k] >= 500:
            ll = l[debut[k]:fin[k]]
            garde = ll > 0.7 * np.median(ll)
            couleurs[k] = np.median(cols[debut[k]:fin[k]][garde], 0)
    # les tranches traversees par les courbes sont faussees : on interpole
    h = np.arange(n) * pas
    douteux = np.isnan(couleurs[:, 0])
    if inter:
        douteux |= ((h + 50) % inter) < 70
    bon = ~douteux
    for c in range(3):
        couleurs[douteux, c] = np.interp(h[douteux], h[bon], couleurs[bon, c])
        couleurs[:, c] = np.convolve(np.pad(couleurs[:, c], 5, mode="edge"),
                                     np.ones(11) / 11, "valid")

    # ombrage : meilleure direction de lumiere
    lumref = couleurs.sum(1)[np.clip(tranche, 0, n - 1)]
    ratio = lum / np.maximum(lumref, 1)
    m = terre & (ratio > 0.6) & (ratio < 2.5)
    m &= np.random.default_rng(0).random(m.shape) < 0.1  # echantillon, pour aller plus vite
    pente, aspect, ratio = *(x[m] for x in relief(alt)), ratio[m]
    meilleur = None
    for az in range(0, 360, 15):
        for ht in (30, 45, 60):
            cor = np.corrcoef(ombrage(pente, aspect, az, ht), ratio)[0, 1]
            if meilleur is None or cor > meilleur[0]:
                meilleur = (cor, az, ht)
    cor, az, ht = meilleur
    # intensite : regression sur des champs lisses, pour ne pas confondre l'ombrage
    # avec la texture fine du modele (qui gonflerait le contraste)
    from scipy import ndimage
    ratio_plein = np.where(terre, lum / np.maximum(lumref, 1), 1)
    hs_plein = ombrage(*relief(alt), az, ht)
    lisse_r = ndimage.uniform_filter(np.clip(ratio_plein, 0.3, 3), 5)[m]
    lisse_h = ndimage.uniform_filter(hs_plein, 5)[m]
    k, b0 = np.polyfit(lisse_h, lisse_r, 1)
    # luminosite : meme moyenne que le modele sur les terres (hors traits sombres)
    prevu = lumref * np.clip(k * hs_plein + b0, 0.3, 2.5)
    clair = terre & (lum > 0.5 * lumref)
    gain = float(lum[clair].mean() / prevu[clair].mean())

    # couleur des courbes : les pixels du trait nettement plus sombres que la teinte attendue
    trait = lignes(alt, maitresse) & terre & (lum < 0.5 * lumref)
    # courbes fines : assombrissement median des pixels du trait par rapport au fond
    facteur_inter = 0.65
    if inter:
        fin_ = lignes(alt, inter) & ~lignes(alt, maitresse) & terre
        r_fin = lum[fin_] / np.maximum(prevu[fin_], 1)
        r_fin = r_fin[r_fin < 0.9]
        if r_fin.size > 1000:
            facteur_inter = round(float(np.median(r_fin)), 2)
    style = {
        "pas": pas,
        "mer": np.median(img[(alt <= 0) & eau], 0).round().tolist(),
        "ombrage": {"azimut": az, "hauteur": ht, "k": round(float(k), 3), "b": round(float(b0), 3),
                    "gain": round(gain, 3)},
        "nettete": 45,
        "courbes": {"maitresse": maitresse, "inter": inter,
                    "couleur_maitresse": np.median(img[trait], 0).round().tolist(),
                    "facteur_inter": facteur_inter},
        "couleurs": couleurs.round().astype(int).tolist(),
    }
    with open(sortie, "w") as f:
        json.dump(style, f)
    print(f"Style enregistre : {sortie} (lumiere {az} deg / {ht} deg)")


# ---------------------------------------------------------------- programme

def choisir_fichiers(style):
    import tkinter as tk
    from tkinter import filedialog
    tk.Tk().withdraw()
    raw = filedialog.askopenfilename(title="Fichier RAW du paysage",
                                     filetypes=[("Condor RAW", "*.raw")])
    if not raw:
        sys.exit()
    sortie = filedialog.asksaveasfilename(
        title="Enregistrer la carte", defaultextension=".bmp",
        initialfile=os.path.splitext(os.path.basename(raw))[0] + suffixe_style(style) + ".bmp",
        filetypes=[("BMP", "*.bmp")])
    if not sortie:
        sys.exit()
    return raw, sortie


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("raw", nargs="?", help="fichier .raw Condor")
    p.add_argument("-o", "--sortie", help="BMP a creer (defaut : <raw>_AE.bmp ou <raw>_DGT.bmp selon le style)")
    p.add_argument("-p", "--style", default=STYLE_DEFAUT, help="fichier de style JSON")
    p.add_argument("--maitresse", type=int, help="equidistance des courbes noires (m), 0 = aucune")
    p.add_argument("--inter", type=int, help="equidistance des courbes fines (m), 0 = aucune")
    p.add_argument("--apprendre", nargs=2, metavar=("MODELE.bmp", "MODELE.raw"),
                   help="creer un style a partir d'une carte existante")
    p.add_argument("-q", "--qualite", type=int, default=4,
                   help="sur-echantillonnage : 1 = normale, 2 = haute, 4 = maximale (defaut)")
    p.add_argument("--sans-eau", action="store_true", help="pas de rivieres ni de lacs")
    p.add_argument("--sans-villes", action="store_true", help="pas de noms de villes")
    p.add_argument("--convertir", metavar="FICHIER.trn",
                   help="convertir un .trn en .raw 16 bits sans en-tete, nord en haut")
    a = p.parse_args()

    if a.convertir:
        sortie = a.sortie or os.path.splitext(a.convertir)[0] + ".raw"
        w, h = convertir_trn(a.convertir, sortie)
        print(f"RAW enregistre : {sortie}\nPhotoshop : {w} x {h}, 1 couche, 16 bits, "
              "ordre IBM PC, en-tete 0")
        return

    if a.apprendre:
        apprendre(*a.apprendre, a.style, a.maitresse or 500, 250 if a.inter is None else a.inter)
        return

    if a.raw:
        raw, sortie = a.raw, a.sortie or os.path.splitext(a.raw)[0] + suffixe_style(a.style) + ".bmp"
    else:
        raw, sortie = choisir_fichiers(a.style)

    with open(a.style) as f:
        style = json.load(f)
    maitresse = style["courbes"]["maitresse"] if a.maitresse is None else a.maitresse
    inter = style["courbes"]["inter"] if a.inter is None else a.inter

    alt = lire_raw(raw)
    villes = [] if a.sans_villes else villes_du_paysage(raw)
    print(f"{os.path.basename(raw)} : {alt.shape[1]} x {alt.shape[0]}, "
          f"altitude {alt.min():.0f} a {alt.max():.0f} m, {len(villes)} villes")
    ecrire_bmp32(sortie, fabriquer_carte(alt, style, maitresse, inter,
                                         eau=not a.sans_eau, villes=villes, qualite=a.qualite,
                                         lacs_wc=None if a.sans_eau else lacs_worldcover(raw),
                                         bati=bati_worldcover(raw) if style.get("urbain") else None,
                                         routes=routes_du_paysage(raw),
                                         cours_eau=cours_eau_du_paysage(raw)))
    print(f"Carte enregistree : {sortie}")


if __name__ == "__main__":
    main()
