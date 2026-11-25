"""Noms français des espèces, 100 % local.

Ordre de recherche :
  1. noms_perso.csv          (tes propres noms)
  2. liste intégrée          (oiseaux courants)
  3. noms_fr_cache.json      (noms déjà trouvés via Kiwix)
  4. Kiwix                   (Wikipédia français hors ligne, sur ce PC)

Aucune connexion à internet : seul Kiwix (127.0.0.1) est interrogé.
"""
import csv
import html
import json
import re
import threading
import time
import urllib.parse
from pathlib import Path

import requests

import config

DOSSIER = Path(__file__).parent
CACHE = DOSSIER / "noms_fr_cache.json"
PERSO = DOSSIER / "noms_perso.csv"

NOMS_INTEGRES = {
    "Parus major": "Mésange charbonnière",
    "Cyanistes caeruleus": "Mésange bleue",
    "Periparus ater": "Mésange noire",
    "Lophophanes cristatus": "Mésange huppée",
    "Poecile palustris": "Mésange nonnette",
    "Aegithalos caudatus": "Mésange à longue queue",
    "Erithacus rubecula": "Rougegorge familier",
    "Turdus merula": "Merle noir",
    "Turdus philomelos": "Grive musicienne",
    "Turdus viscivorus": "Grive draine",
    "Fringilla coelebs": "Pinson des arbres",
    "Carduelis carduelis": "Chardonneret élégant",
    "Chloris chloris": "Verdier d'Europe",
    "Passer domesticus": "Moineau domestique",
    "Passer montanus": "Moineau friquet",
    "Pica pica": "Pie bavarde",
    "Garrulus glandarius": "Geai des chênes",
    "Corvus corone": "Corneille noire",
    "Corvus frugilegus": "Corbeau freux",
    "Columba palumbus": "Pigeon ramier",
    "Columba livia": "Pigeon biset",
    "Streptopelia decaocto": "Tourterelle turque",
    "Sitta europaea": "Sittelle torchepot",
    "Certhia brachydactyla": "Grimpereau des jardins",
    "Dendrocopos major": "Pic épeiche",
    "Picus viridis": "Pic vert",
    "Sturnus vulgaris": "Étourneau sansonnet",
    "Prunella modularis": "Accenteur mouchet",
    "Troglodytes troglodytes": "Troglodyte mignon",
    "Phoenicurus ochruros": "Rougequeue noir",
    "Phylloscopus collybita": "Pouillot véloce",
    "Sylvia atricapilla": "Fauvette à tête noire",
    "Coccothraustes coccothraustes": "Grosbec casse-noyaux",
    "Pyrrhula pyrrhula": "Bouvreuil pivoine",
    "Spinus spinus": "Tarin des aulnes",
    "Buteo buteo": "Buse variable",
    "Falco tinnunculus": "Faucon crécerelle",
    "Ardea cinerea": "Héron cendré",
    "Anas platyrhynchos": "Canard colvert",
    "Cygnus olor": "Cygne tuberculé",
    "Gallinula chloropus": "Gallinule poule-d'eau",
    "Hirundo rustica": "Hirondelle rustique",
    "Apus apus": "Martinet noir",
    "Alauda arvensis": "Alouette des champs",
    "Motacilla alba": "Bergeronnette grise",
    "Emberiza citrinella": "Bruant jaune",
    "Alcedo atthis": "Martin-pêcheur d'Europe",
}

_verrou = threading.Lock()
_charge = False
_cache = {}
_perso = {}
_livre = {"nom": None, "essai": 0.0}
_etat = {"kiwix": "pas encore utilisé"}


# ---------- Fichiers locaux ----------
def _charger():
    global _charge
    if _charge:
        return
    _charge = True
    try:
        if CACHE.exists():
            _cache.update(json.loads(CACHE.read_text(encoding="utf-8")))
    except Exception as e:
        print("Cache des noms illisible :", e)
    try:
        if PERSO.exists():
            with open(PERSO, newline="", encoding="utf-8-sig") as f:
                lignes = [l for l in f if l.strip() and not l.lstrip().startswith("#")]
            for ligne in csv.reader(lignes, delimiter=";"):
                if len(ligne) >= 2 and ligne[0].strip().lower() != "espece":
                    _perso[ligne[0].strip()] = ligne[1].strip()
    except Exception as e:
        print("noms_perso.csv illisible :", e)


def _sauver_cache():
    try:
        CACHE.write_text(json.dumps(_cache, ensure_ascii=False, indent=1),
                         encoding="utf-8")
    except Exception as e:
        print("Cache des noms non écrit :", e)


# ---------- Kiwix ----------
def _base():
    return config.KIWIX_URL.rstrip("/")


def _trouver_livre():
    """Nom du livre Wikipédia FR dans kiwix-serve (ex. wikipedia_fr_all_maxi_2026-01)."""
    if config.KIWIX_LIVRE:
        return config.KIWIX_LIVRE
    if _livre["nom"]:
        return _livre["nom"]
    if time.time() - _livre["essai"] < 30:
        return None
    _livre["essai"] = time.time()
    for chemin in ("/catalog/v2/entries?count=-1", "/"):
        try:
            r = requests.get(_base() + chemin, timeout=config.KIWIX_DELAI)
        except requests.RequestException:
            _etat["kiwix"] = "injoignable (kiwix-serve est-il lancé ?)"
            return None
        noms = re.findall(r"/content/([^\"'/<>\s?#]+)", r.text)
        for nom in noms:
            nom = urllib.parse.unquote(nom)
            if "wikipedia_fr" in nom.lower():
                _livre["nom"] = nom
                _etat["kiwix"] = "connecté (" + nom + ")"
                return nom
    _etat["kiwix"] = "connecté, mais aucun livre Wikipédia FR trouvé"
    return None


def _titre_page(texte):
    m = re.search(r"<title[^>]*>(.*?)</title>", texte, re.I | re.S)
    if not m:
        return ""
    titre = html.unescape(m.group(1)).strip()
    titre = re.sub(r"\s*[-–—|]\s*Wikip[ée]dia.*$", "", titre, flags=re.I)
    titre = re.sub(r"\s*\(.*?\)\s*$", "", titre)
    return titre.strip()


def _chercher_kiwix(espece):
    livre = _trouver_livre()
    if not livre:
        return ""
    titre = espece.strip().replace(" ", "_")
    for chemin in ("A/" + titre, titre):
        url = "{}/content/{}/{}".format(
            _base(), urllib.parse.quote(livre, safe=""),
            urllib.parse.quote(chemin, safe="/"))
        try:
            r = requests.get(url, timeout=config.KIWIX_DELAI, allow_redirects=True)
        except requests.RequestException:
            _etat["kiwix"] = "injoignable (kiwix-serve est-il lancé ?)"
            _livre["nom"] = None
            return ""
        if r.status_code != 200:
            continue
        _etat["kiwix"] = "connecté (" + livre + ")"
        texte = r.content.decode("utf-8", errors="replace")
        # on vérifie que la page parle bien de cette espèce
        if espece.lower() not in texte.lower():
            continue
        nom = _titre_page(texte)
        if nom and nom.lower() != espece.lower():
            return nom
    return ""


# ---------- Interface publique ----------
def nom_francais(espece):
    """Nom français de l'espèce, ou '' si introuvable."""
    if not espece:
        return ""
    with _verrou:
        _charger()
        for source in (_perso, NOMS_INTEGRES, _cache):
            if espece in source:
                return source[espece]
    if config.KIWIX_ACTIF:
        nom = _chercher_kiwix(espece)
        if nom:
            with _verrou:
                _cache[espece] = nom
                _sauver_cache()
            return nom
    return ""


def etat_kiwix():
    if not config.KIWIX_ACTIF:
        return "désactivé"
    return _etat["kiwix"]
