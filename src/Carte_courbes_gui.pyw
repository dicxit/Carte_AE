"""Utilitaire Windows : carte BMP 32 bits avec courbes de niveau a partir d'un .raw Condor."""
import json
import os
import glob
import glob
import threading
import time
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

import carte_courbes as cc

VERSION = "2.11 du 13/11/2026"
PARAMETRES = os.path.join(cc.ICI, "parametres.json")
RAPPORT = os.path.join(cc.ICI, "rapport_courbes.txt")
# Tutoriels : cherches a cote de l'exe, puis dans l'exe, puis dans D:\Condor3\Carte-AE
TUTORIELS = {"FR": "Installation_FR.pdf", "EN": "Installation_EN.pdf"}
DOSSIER_TUTORIELS = r"D:\Condor3\Carte-AE"


def _lecteurs_disponibles():
    """Lettres des disques accessibles sous Windows (C:, D:, ...)."""
    if os.name == "nt":
        import ctypes, string
        try:
            masque = ctypes.windll.kernel32.GetLogicalDrives()
        except Exception:
            masque = 0
        lecteurs = [f"{l}:\\" for i, l in enumerate(string.ascii_uppercase) if masque & (1 << i)]
        if lecteurs:
            return lecteurs
        return [f"{l}:\\" for l in "CDEFGHIJKLMNOPQRSTUVWXYZ"]
    return ["/"]


def trouver_dossier_paysages(preferes=None):
    """Trouve le dossier des paysages (Landscapes) en cherchant sur les disques.
    Retourne (chemin, raison) ou (None, None)."""
    candidats = []
    for base in preferes or []:
        if not base:
            continue
        base = os.path.normpath(base)
        nom = os.path.basename(base).lower()
        if nom == "landscapes" and os.path.isdir(base):
            candidats.append(base)
        if nom == "condor3":
            p = os.path.join(base, "Landscapes")
            if os.path.isdir(p):
                candidats.append(p)
    # recherche large (profondeur limitee) : tout dossier nomme "Landscapes"
    for lecteur in _lecteurs_disponibles():
        p = os.path.join(lecteur, "Condor3", "Landscapes")
        if os.path.isdir(p):
            candidats.append(p)
        racine = lecteur
        try:
            for courant, dirs, _ in os.walk(racine):
                try:
                    profondeur = os.path.relpath(courant, racine).count(os.sep)
                except ValueError:
                    profondeur = 0
                if profondeur >= 5:
                    dirs[:] = []
                    continue
                dirs[:] = [d for d in dirs if d.lower() not in {
                    "windows", "$recycle.bin", "system volume information",
                    "program files", "program files (x86)", "programdata", "appdata"}]
                for d in list(dirs):
                    if d.lower() == "landscapes":
                        candidats.append(os.path.join(courant, d))
        except Exception:
            continue

    vus = set()
    uniques = []
    for c in candidats:
        k = os.path.normcase(os.path.normpath(c))
        if k not in vus:
            vus.add(k)
            uniques.append(os.path.normpath(c))
    if not uniques:
        return None, None
    # preferer celui qui contient le plus de .trn
    def score(d):
        try:
            return len(glob.glob(os.path.join(d, "*", "*.trn"))) + len(glob.glob(os.path.join(d, "**", "*.trn"), recursive=True))
        except Exception:
            return 0
    uniques.sort(key=score, reverse=True)
    return uniques[0], uniques

EXPLICATION_FR = """\
À QUOI SERT CE LOGICIEL ?
Il fabrique une carte en image (fichier .bmp) à partir d'un paysage Condor.
La carte montre le relief en couleurs, les courbes de niveau, l'ombrage,
la mer, les lacs, les rivières, les routes, les villes et une légende.

CRÉER UNE CARTE, PAS À PAS
1. Fichier TRN / RAW : cliquez sur « ... » et choisissez le fichier .trn
   du paysage (dans D:\\Condor3\\Landscapes\\<paysage>\\).
2. Carte BMP à créer : le nom se remplit tout seul (<paysage>_AE.bmp),
   à côté du .trn. Cliquez sur « ... » pour le changer si besoin.
3. Style : choisissez AE (vert) ou DGT (couleurs claires, villes en orange).
4. Courbes maîtresses et courbes fines : l'écart en mètres entre deux
   courbes. 500 et 250 conviennent bien. 0 = pas de courbes.
5. Cochez « Rivières et lacs » et « Noms de villes » si vous les voulez.
6. Qualité : Normale (rapide), Haute, ou Maximale (plus lent, plus net).
   Le temps de calcul peut varier selon la puissance de l'ordinateur :
   sur un PC moins puissant, une carte peut prendre beaucoup plus de temps.
7. Cliquez sur « Créer la carte ». La barre verte avance et le temps
   restant s'affiche. Un aperçu apparaît à la fin.
8. « Voir la carte en taille réelle » ouvre la carte créée.
   « Ouvrir le dossier » ouvre le dossier où elle se trouve.

LES AUTRES BOUTONS
- Tout traiter : recherche automatiquement le dossier Landscapes
  sur les disques, puis crée la carte de TOUS les fichiers .trn trouvés
  sous ce dossier (un par un). Les anciennes cartes sont remplacées.
  Un message d'attention rappelle que cela peut prendre du temps selon la
  puissance de l'ordinateur. Cela peut prendre plusieurs heures.
- Stop : arrête le travail en cours. Un rapport est écrit à la fin
  (rapport_courbes.txt, à côté du programme).
- Le rond jaune qui clignote, en bas à droite : un rappel important.
- Le « © » en bas : affiche ou cache l'outil de conversion .trn -> .raw
  (pour ouvrir le relief dans Photoshop). Vous n'en avez pas besoin
  pour créer une carte.

LE MENU PARAMÈTRES
- Dossier d'ouverture des fichiers : le dossier proposé quand vous
  cherchez un paysage.
- Dossier des RAW convertis : où ranger les fichiers .raw.
- Afficher les dossiers actuels : rappelle ces réglages.

BON À SAVOIR
- Les routes et rivières viennent d'OpenStreetMap (dossier
  D:\\Condor3\\OSM), sans les petits ruisseaux.
- Les lacs, la mer et les villes viennent d'ESA WorldCover (dossier
  D:\\Condor3\\WorldCover). Sans ces dossiers, la carte est faite quand
  même, mais sans ces détails.
- Le logiciel ne modifie jamais vos paysages Condor.
- Ces cartes ne sont pas des cartes de navigation officielles.
"""

EXPLICATION_EN = """\
WHAT DOES THIS PROGRAM DO?
It makes a map picture (.bmp file) from a Condor landscape.
The map shows the terrain in colours, contour lines, hill shading,
sea, lakes, rivers, roads, towns and a legend.

MAKING A MAP, STEP BY STEP
1. TRN / RAW file: click "..." and pick the landscape .trn file
   (in D:\\Condor3\\Landscapes\\<landscape>\\).
2. BMP map to create: the name fills in by itself (<landscape>_AE.bmp),
   next to the .trn. Click "..." to change it if needed.
3. Style: choose AE (green) or DGT (light colours, towns in orange).
4. Main contours and fine contours: the gap in metres between two
   lines. 500 and 250 work well. 0 = no lines.
5. Tick "Rivers and lakes" and "Town names" if you want them.
6. Quality: Normal (fast), High, or Maximum (slower, sharper).
   Processing time can vary depending on the power of the computer:
   on a less powerful PC, a map can take much longer.
7. Click "Create the map". The green bar moves and
   the time left is shown. A preview appears at the end.
8. "See the map full size" opens the new map.
   "Open the folder" opens the folder where it is saved.

THE OTHER BUTTONS
- Process all: automatically searches for the Landscapes folder
  on your disks, then makes the map for EVERY .trn file found under that
  folder, one after the other. Old maps are replaced. A warning message
  reminds you that this may take time depending on your computer's
  performance. This can take several hours.
- Stop: stops the current work. A report is written at the end
  (rapport_courbes.txt, next to the program).
- The blinking yellow circle, bottom right: an important reminder.
- The "©" at the bottom: shows or hides the .trn -> .raw converter
  (to open the terrain in Photoshop). You do not need it to make a map.

THE SETTINGS MENU
- Files opening folder: the folder shown when you look for a landscape.
- Converted RAW folder: where .raw files are saved.
- Show current folders: reminds you of these settings.

GOOD TO KNOW
- Roads and rivers come from OpenStreetMap (folder D:\\Condor3\\OSM),
  without small streams.
- Lakes, sea and towns come from ESA WorldCover (folder
  D:\\Condor3\\WorldCover). Without these folders the map is still made,
  but without those details.
- The program never changes your Condor landscapes.
- These maps are not official navigation charts.
"""
RAPPEL_FR = ("IMPORTANT :\n- Les rivieres viennent d'OpenStreetMap, sans les ruisseaux.\n"
             "- Le temps de calcul peut varier selon la puissance de l'ordinateur.")
RAPPEL_EN = ("IMPORTANT:\n- Rivers come from OpenStreetMap, without small streams.\n"
             "- Processing time can vary depending on the power of the computer.")
DEFAUTS = {"dossier_ouverture": r"D:\Condor3\Landscapes",
           "dossier_raw": "", "langue": "FR"}
LANGUE = "FR"  # "FR" ou "EN", lu dans parametres.json au demarrage


def T(fr, en):
    """Texte dans la langue choisie (menu Langue / Language)."""
    return en if LANGUE == "EN" else fr


# noms des qualites affiches en anglais (les cles du moteur restent en francais)
QUALITES_EN = {"Normale": "Normal", "Haute": "High", "Maximale": "Maximum"}  # vide = a cote du .trn, dans le dossier du paysage


def lire_parametres():
    try:
        with open(PARAMETRES) as f:
            return {**DEFAUTS, **json.load(f)}
    except (OSError, ValueError):
        return dict(DEFAUTS)


def styles_disponibles():
    """Styles livres ou poses a cote de l'exe : {nom affiche: chemin}. Ex. 'AE', 'DGT'."""
    import glob
    styles = {}
    for dossier in (cc.ICI, cc.RESSOURCES):
        for chemin in sorted(glob.glob(os.path.join(dossier, "style_*.json"))):
            nom = os.path.splitext(os.path.basename(chemin))[0][len("style_"):]
            styles.setdefault(nom, chemin)
    return styles


def nom_du_style(chemin, styles):
    """Nom affiche pour un chemin de style ; le chemin brut si le style n'est pas dans la liste."""
    for nom, p in styles.items():
        if os.path.normcase(os.path.normpath(p)) == os.path.normcase(os.path.normpath(chemin)):
            return nom
    return os.path.splitext(os.path.basename(chemin))[0]


class Appli(tk.Tk):
    def __init__(self):
        super().__init__()
        self.relancer = False
        self.title(T("Carte Condor - courbes de niveau", "Condor map - contour lines") + f" - v{VERSION}")
        self.resizable(False, False)
        icone = os.path.join(cc.RESSOURCES, "carte_courbes.ico")
        if os.path.exists(icone):
            self.iconbitmap(icone)
        self.param = lire_parametres()

        menu = tk.Menu(self)
        # menu Parametres retire (demande de l'utilisateur) ; les reglages restent dans parametres.json
        aide = tk.Menu(menu, tearoff=0)
        aide.add_command(label="Tutoriel en francais", command=lambda: self.ouvrir_tutoriel("FR"))
        aide.add_command(label="Tutorial in English", command=lambda: self.ouvrir_tutoriel("EN"))
        menu.add_cascade(label=T("Tutoriels", "Tutorials"), menu=aide)
        langue = tk.Menu(menu, tearoff=0)
        langue.add_command(label="Francais", command=lambda: self.changer_langue("FR"))
        langue.add_command(label="English", command=lambda: self.changer_langue("EN"))
        menu.add_cascade(label="Langue / Language", menu=langue)
        self.config(menu=menu)
        self.raw = tk.StringVar()
        self.sortie = tk.StringVar()
        self.style = tk.StringVar(value=cc.STYLE_DEFAUT)
        self.maitresse = tk.IntVar(value=500)
        self.inter = tk.IntVar(value=250)
        self.etat = tk.StringVar(value=T("Choisissez un fichier .trn ou .raw", "Choose a .trn or .raw file"))

        f = ttk.Frame(self, padding=10)
        f.grid()
        for ligne, (texte, var, action) in enumerate([
                (T("Fichier TRN / RAW", "TRN / RAW file"), self.raw, self.choisir_raw),
                (T("Carte BMP a creer", "BMP map to create"), self.sortie, self.choisir_sortie),
                (T("Style (JSON)", "Style (JSON)"), self.style, self.choisir_style)]):
            ttk.Label(f, text=texte).grid(row=ligne, column=0, sticky="w")
            ttk.Entry(f, textvariable=var, width=70).grid(row=ligne, column=1, padx=5, pady=2)
            ttk.Button(f, text="...", width=3, command=action).grid(row=ligne, column=2)

        o = ttk.Frame(f)
        o.grid(row=3, column=0, columnspan=3, sticky="w", pady=6)
        ttk.Label(o, text=T("Courbes maitresses (m)", "Main contours (m)")).pack(side="left")
        ttk.Spinbox(o, from_=0, to=2000, increment=50, width=6,
                    textvariable=self.maitresse).pack(side="left", padx=(4, 16))
        ttk.Label(o, text=T("Courbes fines (m)", "Fine contours (m)")).pack(side="left")
        ttk.Spinbox(o, from_=0, to=1000, increment=50, width=6,
                    textvariable=self.inter).pack(side="left", padx=4)
        ttk.Label(o, text=T("(0 = aucune)", "(0 = none)")).pack(side="left", padx=4)
        self.eau = tk.BooleanVar(value=True)
        self.villes = tk.BooleanVar(value=True)
        ttk.Checkbutton(o, text=T("Rivieres et lacs", "Rivers and lakes"), variable=self.eau).pack(side="left", padx=(16, 4))
        ttk.Checkbutton(o, text=T("Noms de villes", "Town names"), variable=self.villes).pack(side="left", padx=4)
        # nom affiche -> cle du moteur (Normale, Haute, Maximale)
        self.qualites = {T(q, QUALITES_EN.get(q, q)): q for q in cc.QUALITES}
        self.qualite = tk.StringVar(value=T("Maximale", "Maximum"))
        ttk.Label(o, text=T("Qualite", "Quality")).pack(side="left", padx=(16, 4))
        ttk.Combobox(o, textvariable=self.qualite, values=list(self.qualites), width=9,
                     state="readonly").pack(side="left")
        self.styles = styles_disponibles()
        self.style_nom = tk.StringVar(value=nom_du_style(self.style.get(), self.styles))
        ttk.Label(o, text="Style").pack(side="left", padx=(16, 4))
        liste = ttk.Combobox(o, textvariable=self.style_nom, values=list(self.styles), width=8,
                             state="readonly")
        liste.pack(side="left")
        liste.bind("<<ComboboxSelected>>", self.choisir_style_liste)
        self.barre = ttk.Progressbar(f, length=300, maximum=1.0)
        self.barre.grid(row=7, column=0, columnspan=3, sticky="we", pady=(6, 0))
        pied = ttk.Frame(f)
        pied.grid(row=8, column=0, columnspan=3, sticky="e", pady=(6, 0))
        # clic sur le (c) : affiche / cache le cadre de conversion .trn -> .raw
        copyright = ttk.Label(pied, text="©", foreground="#555555", font=("Segoe UI", 9),
                              cursor="hand2")
        copyright.pack(side="left")
        copyright.bind("<Button-1>", self.basculer_conversion)
        ttk.Label(pied, text=f" Dicxit (AE) - v{VERSION}", foreground="#555555",
                  font=("Segoe UI", 9)).pack(side="left")
        self.creer_rappel(pied)

        b = ttk.Frame(f)
        b.grid(row=4, column=0, columnspan=3, sticky="we")
        self.bouton = ttk.Button(b, text=T("Creer la carte", "Create the map"), command=self.lancer)
        self.bouton.pack(side="left")
        self.bouton_tout = ttk.Button(b, text=T("Tout traiter", "Process all"), command=self.lancer_tout)
        self.bouton_tout.pack(side="left", padx=(6, 0))
        self.bouton_stop = ttk.Button(b, text=T("Stop", "Stop"), command=self.arreter, state="disabled")
        self.bouton_stop.pack(side="left", padx=6)
        self.temps = tk.StringVar()
        ttk.Label(b, textvariable=self.temps).pack(side="left", padx=6)
        self.arret = threading.Event()
        self.en_cours = False
        self.fraction, self.t0, self.index, self.total = 0.0, 0.0, 0, 1
        ttk.Button(b, text=T("Ouvrir le dossier", "Open the folder"), command=self.ouvrir_dossier).pack(side="left", padx=6)
        ttk.Label(b, textvariable=self.etat).pack(side="left", padx=10)

        c = ttk.LabelFrame(f, text=T("Convertir .trn -> .raw (rotation 90 + symetrie, nord en haut)",
                                  "Convert .trn -> .raw (90 rotation + mirror, north up)"),
                           padding=6)
        c.grid(row=5, column=0, columnspan=3, sticky="we", pady=(10, 0))
        c.grid_remove()  # cache par defaut, voir basculer_conversion
        self.cadre_conversion = c
        self.trn = tk.StringVar()
        self.raw_sortie = tk.StringVar()
        for ligne, (texte, var, action) in enumerate([
                (T("Fichier TRN", "TRN file"), self.trn, self.choisir_trn),
                (T("RAW a creer", "RAW to create"), self.raw_sortie, self.choisir_raw_sortie)]):
            ttk.Label(c, text=texte).grid(row=ligne, column=0, sticky="w")
            ttk.Entry(c, textvariable=var, width=66).grid(row=ligne, column=1, padx=5, pady=2)
            ttk.Button(c, text="...", width=3, command=action).grid(row=ligne, column=2)
        ttk.Button(c, text=T("Convertir", "Convert"), command=self.convertir).grid(row=2, column=0, pady=(4, 0))
        self.etat_trn = tk.StringVar()
        ttk.Label(c, textvariable=self.etat_trn).grid(row=2, column=1, sticky="w", padx=5)

        self.apercu = ttk.Label(f)
        self.apercu.grid(row=6, column=0, columnspan=3, pady=(10, 0))
        ttk.Button(f, text=T("Voir la carte en taille reelle", "See the map full size"), command=self.ouvrir_derniere).grid(row=9, column=0, columnspan=3, pady=(4, 0))

    def ouvrir_tutoriel(self, langue):
        nom = TUTORIELS[langue]
        for dossier in (cc.ICI, cc.RESSOURCES, DOSSIER_TUTORIELS):
            chemin = os.path.join(dossier, nom)
            if os.path.isfile(chemin):
                os.startfile(chemin)
                return
        messagebox.showerror(T("Tutoriel introuvable", "Tutorial not found"),
                             T(f"Le fichier {nom} est introuvable.\nPlacez-le a cote de Carte_AE.exe.",
                               f"The file {nom} was not found.\nPut it next to Carte_AE.exe."))

    def changer_langue(self, langue):
        """Enregistre la langue et rouvre la fenetre dans cette langue."""
        global LANGUE
        if langue == LANGUE:
            return
        if self.en_cours:
            messagebox.showinfo(T("Langue", "Language"),
                                T("Attendez la fin du calcul pour changer de langue.",
                                  "Wait until the map is finished to change the language."))
            return
        self.param["langue"] = langue
        with open(PARAMETRES, "w") as f:
            json.dump(self.param, f, indent=2)
        LANGUE = langue
        # on garde les fichiers deja choisis pour la nouvelle fenetre
        self.garder = {"raw": self.raw.get(), "sortie": self.sortie.get(), "style": self.style.get()}
        self.relancer = True
        self.destroy()

    def montrer_explication(self, titre, texte):
        """Petite fenetre de lecture, avec ascenseur et bouton Fermer."""
        fen = tk.Toplevel(self)
        fen.title(titre)
        fen.transient(self)
        cadre = ttk.Frame(fen, padding=8)
        cadre.pack(fill="both", expand=True)
        zone = tk.Text(cadre, width=78, height=32, wrap="word", font=("Segoe UI", 10),
                       padx=8, pady=6)
        ascenseur = ttk.Scrollbar(cadre, command=zone.yview)
        zone.configure(yscrollcommand=ascenseur.set)
        ascenseur.pack(side="right", fill="y")
        zone.pack(side="left", fill="both", expand=True)
        zone.insert("1.0", texte)
        zone.configure(state="disabled")
        ttk.Button(fen, text=T("Fermer", "Close"), command=fen.destroy).pack(pady=(0, 8))

    def basculer_conversion(self, event=None):
        if self.cadre_conversion.winfo_ismapped():
            self.cadre_conversion.grid_remove()
        else:
            self.cadre_conversion.grid()

    def changer_dossier(self, cle):
        titre = {"dossier_ouverture": T("Dossier d'ouverture des fichiers", "Files opening folder"),
                 "dossier_raw": T("Dossier des RAW convertis", "Converted RAW folder")}[cle]
        d = filedialog.askdirectory(title=titre, initialdir=self.param[cle]
                                    or self.param["dossier_ouverture"])
        if not d:
            return
        self.param[cle] = os.path.normpath(d)
        self.enregistrer_parametres()

    def raw_a_cote(self):
        self.param["dossier_raw"] = ""
        self.enregistrer_parametres()

    def enregistrer_parametres(self):
        with open(PARAMETRES, "w") as f:
            json.dump(self.param, f, indent=2)
        self.voir_dossiers()

    def voir_dossiers(self):
        raw = self.param['dossier_raw'] or T("dossier du .trn (paysage)", "folder of the .trn (landscape)")
        messagebox.showinfo(T("Dossiers par defaut", "Default folders"),
                            T("Ouverture des fichiers :", "Files opening:")
                            + f"\n{self.param['dossier_ouverture']}\n\n"
                            + T("RAW convertis :", "Converted RAW:") + f"\n{raw}")

    def choisir_trn(self):
        p = filedialog.askopenfilename(title=T("Fichier TRN du paysage", "Landscape TRN file"), initialdir=self.param["dossier_ouverture"],
                                       filetypes=[("Condor TRN", "*.trn")])
        if p:
            self.trn.set(os.path.normpath(p))
            nom = os.path.splitext(os.path.basename(p))[0] + ".raw"
            dossier = self.param["dossier_raw"] or os.path.dirname(p)  # vide = dossier du .trn
            self.raw_sortie.set(os.path.normpath(os.path.join(dossier, nom)))
            self.etat_trn.set("")

    def choisir_raw_sortie(self):
        p = filedialog.asksaveasfilename(title=T("Enregistrer le RAW", "Save the RAW"), defaultextension=".raw",
                                         initialfile=os.path.basename(self.raw_sortie.get()),
                                         initialdir=os.path.dirname(self.raw_sortie.get())
                                         or self.param["dossier_ouverture"],
                                         filetypes=[("RAW", "*.raw")])
        if p:
            self.raw_sortie.set(os.path.normpath(p))

    def convertir(self):
        trn, raw = self.trn.get(), self.raw_sortie.get()
        if not os.path.isfile(trn) or not raw:
            messagebox.showerror(T("Erreur", "Error"), T("Choisissez un fichier .trn et le .raw a creer.",
                                                         "Choose a .trn file and the .raw to create."))
            return
        if os.path.exists(raw) and not messagebox.askyesno(
                "Remplacer ?", f"{os.path.basename(raw)} existe deja.\nLe remplacer ?"):
            return
        try:
            w, h = cc.convertir_trn(trn, raw)
        except Exception as e:
            messagebox.showerror(T("Erreur", "Error"), str(e))
            return
        self.etat_trn.set(T(f"OK - Photoshop : {w} x {h}, 16 bits, IBM PC, en-tete 0",
                             f"OK - Photoshop: {w} x {h}, 16 bits, IBM PC, header 0"))

    def choisir_raw(self):
        p = filedialog.askopenfilename(title=T("Fichier TRN (ou copie .raw) du paysage", "Landscape TRN file (or .raw copy)"),
                                       initialdir=self.param["dossier_ouverture"],
                                       filetypes=[("Condor TRN / RAW", "*.trn *.raw")])
        if p:
            self.raw.set(os.path.normpath(p))
            self.sortie.set(os.path.splitext(self.raw.get())[0] + cc.suffixe_style(self.style.get()) + ".bmp")
            self.etat.set(T("Pret", "Ready"))

    def choisir_sortie(self):
        p = filedialog.asksaveasfilename(title=T("Enregistrer la carte", "Save the map"), defaultextension=".bmp",
                                         initialfile=os.path.basename(self.sortie.get()),
                                         initialdir=os.path.dirname(self.sortie.get()) or self.param["dossier_ouverture"],
                                         filetypes=[("BMP", "*.bmp")])
        if p:
            self.sortie.set(os.path.normpath(p))

    def maj_sortie_style(self):
        """Remplace le suffixe de la carte (_AE, _AEb, _DGT...) par celui du style choisi.
        Le dossier et le nom de base sont gardes ; un nom sans suffixe connu n'est pas touche."""
        s = self.sortie.get()
        if not s:
            return
        base, ext = os.path.splitext(s)
        suffixes = {cc.suffixe_style(v) for v in self.styles.values()} | {cc.suffixe_style(self.style.get())}
        for suf in sorted(suffixes, key=len, reverse=True):
            if base.endswith(suf):
                self.sortie.set(base[:-len(suf)] + cc.suffixe_style(self.style.get()) + ext)
                return

    def choisir_style_liste(self, event=None):
        self.style.set(self.styles[self.style_nom.get()])
        self.maj_sortie_style()

    def choisir_style(self):
        p = filedialog.askopenfilename(title=T("Fichier de style", "Style file"), initialdir=cc.ICI,
                                       filetypes=[("Style", "*.json")])
        if p:
            self.style.set(os.path.normpath(p))
            self.style_nom.set(nom_du_style(self.style.get(), self.styles))
            self.maj_sortie_style()

    def ouvrir_dossier(self):
        d = os.path.dirname(self.sortie.get() or self.raw.get()) or self.param["dossier_ouverture"]
        if os.path.isdir(d):
            os.startfile(d)

    def lancer(self):
        raw, sortie = self.raw.get(), self.sortie.get()
        if not os.path.isfile(raw):
            messagebox.showerror(T("Erreur", "Error"), T("Choisissez un fichier .raw existant.",
                                                         "Choose an existing .raw file."))
            return
        if not sortie:
            messagebox.showerror(T("Erreur", "Error"), T("Indiquez la carte BMP a creer.",
                                                         "Enter the BMP map to create."))
            return
        if os.path.exists(sortie) and not messagebox.askyesno(
                "Remplacer ?", f"{os.path.basename(sortie)} existe deja.\nLe remplacer ?"):
            return
        self.deja = []
        self.demarrer([(raw, sortie)], unique=True)

    def creer_rappel(self, parent):
        """Icone 'info' jaune entouree de rouge, qui clignote, avec le rappel important."""
        self.rappel = tk.Canvas(parent, width=22, height=22, highlightthickness=0,
                                bg=self.cget("bg"), cursor="hand2")
        self.rappel.pack(side="right", padx=4)
        self.rappel.create_oval(2, 2, 20, 20, outline="#D00000", width=3, fill="#FFD700")
        self.rappel.create_text(11, 11, text="i", fill="#D00000", font=("Arial", 10, "bold"))
        self.rappel.bind("<Button-1>", lambda e: messagebox.showinfo(
            T("Rappel important", "Important reminder"), T(RAPPEL_FR, RAPPEL_EN)))
        self.clignote = True
        self.faire_clignoter()

    def faire_clignoter(self):
        couleur = "#FFD700" if self.clignote else "#FFF3A0"
        self.rappel.itemconfigure(1, fill=couleur)
        self.clignote = not self.clignote
        self.after(500, self.faire_clignoter)

    def lancer_tout(self):
        """Traite tous les .trn trouves sous le dossier Landscapes (recherche sur les disques).
        Chaque carte <paysage>_AE.bmp (ou _DGT) est creee a cote du .trn ; si elle existe
        deja, elle est ecrasee."""
        if not messagebox.askokcancel(
                T("Attention", "Warning"),
                T("Attention : le traitement de tous les paysages peut prendre du temps, "
                  "en fonction de la puissance de votre ordinateur.\n\n"
                  "Voulez-vous continuer ?",
                  "Warning: processing all landscapes may take time, "
                  "depending on your computer's performance.\n\n"
                  "Do you want to continue?")):
            return
        dossier, _ = trouver_dossier_paysages([
            self.param.get("dossier_ouverture"),
            os.path.dirname(self.raw.get()) if self.raw.get() else "",
        ])
        if not dossier:
            messagebox.showerror(
                T("Erreur", "Error"),
                T("Impossible de trouver un dossier Landscapes sur les disques.\n"
                  "Verifiez l'installation des paysages Condor ou choisissez un .trn manuellement.",
                  "Could not find a Landscapes folder on any disk.\n"
                  "Check your Condor landscapes installation or choose a .trn file manually."))
            return
        # recherche recursive de tous les .trn sous Landscapes
        trn = sorted({os.path.normpath(p) for p in glob.glob(os.path.join(dossier, "**", "*.trn"), recursive=True)})
        if not trn:
            messagebox.showerror(
                T("Erreur", "Error"),
                T(f"Aucun fichier .trn trouve sous :\n{dossier}",
                  f"No .trn file found under:\n{dossier}"))
            return
        self.param["dossier_ouverture"] = dossier
        suffixe = cc.suffixe_style(self.style.get())
        travail = [(f, os.path.join(os.path.dirname(f),
                                    os.path.splitext(os.path.basename(f))[0] + suffixe + ".bmp"))
                   for f in trn]
        existantes = sum(os.path.exists(sortie) for _, sortie in travail)
        if not messagebox.askyesno(T("Confirmation : Tout traiter", "Confirm: Process all"),
                                   T(f"Dossier des paysages :\n{dossier}\n\n"
                                     f"{len(travail)} paysage(s) seront traites, un par un.\n"
                                     f"{existantes} carte(s) existante(s) seront ecrasee(s).\n\n"
                                     "A savoir :\n" + RAPPEL_FR + "\n\nLancer le traitement ?",
                                     f"Landscapes folder:\n{dossier}\n\n"
                                     f"{len(travail)} landscape(s) will be processed, one by one.\n"
                                     f"{existantes} existing map(s) will be overwritten.\n\n"
                                     "Good to know:\n" + RAPPEL_EN + "\n\nStart processing?")):
            return
        self.deja = []
        self.demarrer(travail, unique=False)

    def demarrer(self, travail, unique):
        # parametres lus ici, sur le fil principal, puis transmis au calcul
        params = dict(style=self.style.get(), maitresse=self.maitresse.get(),
                      inter=self.inter.get(), eau=self.eau.get(), villes=self.villes.get(),
                      qualite=cc.QUALITES[self.qualites[self.qualite.get()]])
        self.travail, self.unique = travail, unique
        self.crees, self.derniere = [], None
        # poids de chaque paysage = nombre de points : une grande carte compte davantage
        self.poids = []
        for raw, _ in travail:
            try:
                e = cc.lire_entete(raw)
                self.poids.append(max(1, e["w"] * e["h"]))
            except Exception:
                self.poids.append(1)
        self.total_w = float(sum(self.poids))
        self.done_w, self.cur_w, self.nom_courant = 0.0, float(self.poids[0]), ""
        self.arret.clear()
        self.en_cours = True
        self.fraction, self.index, self.total = 0.0, 0, len(travail)
        self.t0 = time.time()
        self.bouton.state(["disabled"])
        self.bouton_tout.state(["disabled"])
        self.bouton_stop.state(["!disabled"])
        self.barre.configure(value=0)
        self.etat.set(T("Calcul en cours...", "Working..."))
        self.temps.set(T("Preparation...", "Preparing..."))
        threading.Thread(target=self.calculer, args=(params,), daemon=True).start()
        self.after(1000, self.rafraichir_temps)

    def arreter(self):
        self.arret.set()
        self.etat.set(T("Arret demande...", "Stop requested..."))

    def _progres(self, v):
        """Appele par le moteur apres chaque morceau de carte."""
        if self.arret.is_set():
            raise cc.Arret()
        self.fraction = (self.done_w + v * self.cur_w) / self.total_w
        self.after(0, self.barre.configure, {"value": self.fraction})

    def rafraichir_temps(self):
        if not self.en_cours:
            return
        ecoule = time.time() - self.t0
        if self.fraction <= 0.001:
            self.temps.set(T(f"Preparation de {self.nom_courant} ({self.duree(ecoule)} ecoulees)",
                             f"Preparing {self.nom_courant} ({self.duree(ecoule)} elapsed)"))
        else:
            restant = max(0.0, ecoule * (1 - self.fraction) / self.fraction)
            fin = time.strftime("%H:%M", time.localtime(time.time() + restant))
            self.temps.set(T(f"{self.nom_courant} - temps restant : {self.duree(restant)}  (fin vers {fin})",
                             f"{self.nom_courant} - time left: {self.duree(restant)}  (ends about {fin})"))
        self.after(1000, self.rafraichir_temps)

    @staticmethod
    def duree(secondes):
        s = int(round(secondes))
        h, reste = divmod(s, 3600)
        m, s = divmod(reste, 60)
        return f"{h} h {m:02d} min {s:02d} s" if h else f"{m} min {s:02d} s"

    def calculer(self, params):
        faits, erreurs, img, arrete = 0, [], None, False
        try:
            with open(params["style"]) as f:
                style = json.load(f)
        except (OSError, ValueError) as e:
            self.after(0, self.fini, None, T(f"Erreur : style illisible ({e})", f"Error: unreadable style ({e})"), 0, [], False)
            return
        for i, (raw, sortie) in enumerate(self.travail):
            self.index = i
            self.cur_w = float(self.poids[i])
            self.nom_courant = os.path.basename(raw)
            try:
                alt = cc.lire_raw(raw)
                villes = cc.villes_du_paysage(raw) if params["villes"] else []
                rgb = cc.fabriquer_carte(
                    alt, style, params["maitresse"], params["inter"],
                    eau=params["eau"], villes=villes,
                    lacs_wc=cc.lacs_worldcover(raw) if params["eau"] else None,
                    bati=cc.bati_worldcover(raw) if style.get("urbain") else None,
                    routes=cc.routes_du_paysage(raw),
                    cours_eau=cc.cours_eau_du_paysage(raw),
                    qualite=params["qualite"], progression=self._progres)
                cc.ecrire_bmp32(sortie, rgb)
                self.crees.append(sortie)
                self.derniere = sortie
                faits += 1
                if self.unique:
                    img = Image.fromarray(rgb)
                    img.thumbnail((900, 600))
            except cc.Arret:
                arrete = True
                break
            except Exception as e:
                erreurs.append(f"{self.nom_courant} : {e}")
            self.done_w += self.cur_w
        self.after(0, self.fini, img, None, faits, erreurs, arrete)

    def fini(self, img, message, faits, erreurs, arrete):
        self.en_cours = False
        self.bouton.state(["!disabled"])
        self.bouton_tout.state(["!disabled"])
        self.bouton_stop.state(["disabled"])
        self.temps.set("")
        if faits and not arrete and not erreurs:
            self.barre.configure(value=1.0)
        if message is None:
            if arrete:
                message = T(f"Arrete : {faits} carte(s) creee(s) sur {self.total}",
                            f"Stopped: {faits} map(s) created out of {self.total}")
            elif erreurs:
                message = T(f"Termine : {faits} carte(s), {len(erreurs)} erreur(s)",
                            f"Done: {faits} map(s), {len(erreurs)} error(s)")
            else:
                message = T(f"Termine : {faits} carte(s) creee(s)", f"Done: {faits} map(s) created")
        self.etat.set(message)
        if img is not None:
            self.photo = ImageTk.PhotoImage(img)
            self.apercu.configure(image=self.photo)
        rapport = self.rapport(arrete, erreurs)
        try:
            with open(RAPPORT, "w", encoding="utf-8") as f:
                f.write(rapport)
        except OSError:
            pass
        if erreurs:
            messagebox.showerror(T("Erreurs pendant le traitement", "Errors during processing"), "\n".join(erreurs[:30]))
        if not self.unique:
            messagebox.showinfo(T("Traitement termine", "Processing finished"), rapport[:3500])

    def rapport(self, arrete, erreurs):
        """Liste de ce qui est fait, ignore, en erreur et pas encore fait."""
        crees = [os.path.basename(os.path.dirname(s)) for s in self.crees]
        noms_err = {e.split(" : ")[0] for e in erreurs}
        faits = set(self.crees)
        non_faits = [os.path.basename(os.path.dirname(r)) for r, s in self.travail
                     if s not in faits and os.path.basename(r) not in noms_err]
        lignes = [f"Rapport du {time.strftime('%d/%m/%Y a %H:%M')}", "",
                  f"CREEES ({len(crees)}) :"] + [f"  {c}" for c in crees]
        lignes += ["", f"IGNOREES, deja faites ({len(self.deja)}) :"] + [f"  {d}" for d in self.deja]
        lignes += ["", f"ERREURS ({len(erreurs)}) :"] + [f"  {e}" for e in erreurs]
        lignes += ["", f"NON FAITES ({len(non_faits)})" + (" - arret demande" if arrete else "") + " :"]
        lignes += [f"  {n}" for n in non_faits]
        return "\n".join(lignes)

    def ouvrir_derniere(self):
        if self.derniere and os.path.exists(self.derniere):
            os.startfile(self.derniere)
        else:
            messagebox.showinfo(T("Carte", "Map"), T("Aucune carte creee pour l'instant.",
                                                     "No map created yet."))

if __name__ == "__main__":
    os.chdir(cc.ICI)
    LANGUE = lire_parametres().get("langue", "FR")
    garder = None
    while True:
        appli = Appli()
        if garder:  # retour apres changement de langue : fichiers deja choisis
            appli.raw.set(garder["raw"])
            appli.sortie.set(garder["sortie"])
            appli.style.set(garder["style"])
            appli.style_nom.set(nom_du_style(garder["style"], appli.styles))
        appli.mainloop()
        if not appli.relancer:
            break
        garder = appli.garder
