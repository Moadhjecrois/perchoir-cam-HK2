import os

import config

# Options FFmpeg (flux RTSP) : paquets abîmés jetés, délai maximum réduit
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
    "rtsp_transport;tcp|fflags;discardcorrupt|max_delay;500000|stimeout;5000000")
os.environ["OPENCV_FFMPEG_LOGLEVEL"] = "-8"
os.environ["OPENCV_LOG_LEVEL"] = "ERROR"

import atexit
import csv
import json
import logging
import queue
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path

import cv2
from flask import Flask, Response, jsonify

import noms_fr

DOSSIER = Path(__file__).parent
CAPTURES = DOSSIER / "captures"
CAPTURES.mkdir(exist_ok=True)
TMP = DOSSIER / "_tmp.jpg"
CSV_FICHIER = DOSSIER / "resultats.csv"

verrou = threading.Lock()
derniere_image = None
declencher = threading.Event()
occupe = threading.Event()
dernier = {"t": 0.0}
clients = {"n": 0}
historique = []

etat = {
    "camera": "Connexion...",
    "modele": "Chargement du modèle...",
    "worker_pret": False,
    "largeur": 0, "hauteur": 0, "fps": 0.0,
    "derniere_image_t": 0.0,
    "mouvement": 0.0, "dernier_mouvement": "aucun",
    "analyses": 0, "retenus": 0, "reconnexions": 0,
    "images": 0, "disque_mo": 0.0,
    "pause": False, "debut": time.time(),
}

noyau = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))


# ---------- Disque ----------
def calculer_disque():
    fichiers = list(CAPTURES.glob("*.jpg"))
    etat["images"] = len(fichiers)
    etat["disque_mo"] = round(sum(f.stat().st_size for f in fichiers) / 1048576, 1)
    return fichiers


def nettoyer():
    fichiers = sorted(calculer_disque())
    total = sum(f.stat().st_size for f in fichiers)
    while fichiers and (len(fichiers) > config.MAX_IMAGES
                        or total > config.MAX_MO * 1048576):
        ancien = fichiers.pop(0)
        total -= ancien.stat().st_size
        ancien.unlink(missing_ok=True)
    calculer_disque()


def charger_historique():
    if not CSV_FICHIER.exists():
        return
    try:
        with open(CSV_FICHIER, newline="", encoding="utf-8-sig") as f:
            lignes = list(csv.reader(f, delimiter=";"))[1:]
        for ligne in reversed(lignes[-30:]):
            if len(ligne) >= 3:
                historique.append({"date": ligne[0], "heure": ligne[1], "nom": ligne[2]})
    except Exception as e:
        print("Historique illisible :", e)


# ---------- Caméra et mouvement ----------
def coordonnees_zone(image):
    h, l = image.shape[:2]
    z = config.ZONE
    return int(z[0] * l), int(z[1] * h), int(z[2] * l), int(z[3] * h)


def part_mouvement(fond, zone):
    h, l = zone.shape[:2]
    if h < 10 or l < 10:
        return 0.0
    petit = cv2.resize(zone, (160, max(10, int(160 * h / l))))
    petit = cv2.GaussianBlur(petit, (5, 5), 0)
    masque = fond.apply(petit)
    masque = cv2.morphologyEx(masque, cv2.MORPH_OPEN, noyau)
    return cv2.countNonZero(masque) / masque.size


def ouvrir_camera():
    c = config.CAMERA
    if isinstance(c, int):
        cap = None
        if os.name == "nt":
            cap = cv2.VideoCapture(c, cv2.CAP_DSHOW)
        if cap is None or not cap.isOpened():
            cap = cv2.VideoCapture(c)
        if cap.isOpened():
            # MJPG : beaucoup plus léger pour le processeur sur une caméra USB
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_LARGEUR)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HAUTEUR)
            cap.set(cv2.CAP_PROP_FPS, config.CAMERA_FPS)
        return cap
    try:
        return cv2.VideoCapture(
            c, cv2.CAP_FFMPEG,
            [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000,
             cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000])
    except Exception:
        return cv2.VideoCapture(c, cv2.CAP_FFMPEG)


def lire_camera():
    global derniere_image
    attente = 1
    while True:
        try:
            cap = ouvrir_camera()
            if not cap.isOpened():
                etat["camera"] = "Introuvable, nouvel essai dans {} s".format(attente)
                cap.release()
                time.sleep(attente)
                attente = min(attente * 2, 15)
                continue
            attente = 1
            try:
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            except Exception:
                pass
            etat["camera"] = "Connectée"
            fond = cv2.createBackgroundSubtractorMOG2(
                history=300, varThreshold=32, detectShadows=False)
            debut = derniere_ok = t0 = time.time()
            dernier_calcul, n = 0.0, 0
            while True:
                ok, image = cap.read()
                maintenant = time.time()
                if not ok or image is None or image.size == 0:
                    if maintenant - derniere_ok > config.DELAI_FLUX_GELE:
                        break
                    time.sleep(0.05)
                    continue
                derniere_ok = maintenant
                with verrou:
                    derniere_image = image
                etat["derniere_image_t"] = maintenant
                etat["hauteur"], etat["largeur"] = image.shape[:2]
                n += 1
                if maintenant - t0 >= 1:
                    etat["fps"] = round(n / (maintenant - t0), 1)
                    n, t0 = 0, maintenant

                # Le mouvement n'est calculé que FPS_MOUVEMENT fois par seconde
                if maintenant - dernier_calcul < 1.0 / config.FPS_MOUVEMENT:
                    continue
                dernier_calcul = maintenant
                x1, y1, x2, y2 = coordonnees_zone(image)
                part = part_mouvement(fond, image[y1:y2, x1:x2])
                etat["mouvement"] = round(part * 100, 1)
                if config.DEBUG and part > 0.005:
                    print("mouvement :", etat["mouvement"], "%")

                if (maintenant - debut > config.APPRENTISSAGE
                        and part >= config.SEUIL
                        and etat["worker_pret"]
                        and not etat["pause"]
                        and not occupe.is_set()
                        and maintenant - dernier["t"] > config.PAUSE):
                    dernier["t"] = maintenant
                    etat["dernier_mouvement"] = datetime.now().strftime("%H:%M:%S")
                    declencher.set()
            cap.release()
        except Exception as e:
            print("ERREUR CAMÉRA :", e)
        etat["camera"] = "Flux perdu, reconnexion..."
        etat["reconnexions"] += 1
        time.sleep(2)


# ---------- Moteur d'analyse (processus séparé) ----------
class Worker:
    def __init__(self):
        self.proc = None
        self.q = queue.Queue()

    def demarrer(self):
        self.arreter()
        self.q = queue.Queue()
        env = os.environ.copy()
        env["HF_HUB_DISABLE_TELEMETRY"] = "1"
        if config.HORS_LIGNE:
            env["HF_HUB_OFFLINE"] = "1"
            env["TRANSFORMERS_OFFLINE"] = "1"
        # Priorité réduite sous Windows : la caméra passe toujours en premier
        drapeaux = 0x00004000 if os.name == "nt" else 0
        self.proc = subprocess.Popen(
            [sys.executable, str(DOSSIER / "analyse_worker.py")],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            text=True, encoding="utf-8", bufsize=1, env=env,
            creationflags=drapeaux)
        threading.Thread(target=self._lire, args=(self.proc, self.q),
                         daemon=True).start()

    @staticmethod
    def _lire(proc, q):
        for ligne in proc.stdout:
            if ligne.startswith("@@"):
                try:
                    q.put(json.loads(ligne[2:]))
                except ValueError:
                    pass
        q.put({"fin": True})

    def attendre(self, delai):
        try:
            return self.q.get(timeout=delai)
        except queue.Empty:
            return None

    def analyser(self, chemin, delai):
        try:
            self.proc.stdin.write(chemin + "\n")
            self.proc.stdin.flush()
        except (OSError, ValueError):
            return None
        fin = time.time() + delai
        while time.time() < fin:
            msg = self.attendre(1)
            if msg is None:
                continue
            if msg.get("fin") or "ok" in msg:
                return msg
        return None

    def arreter(self):
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.stdin.write("QUIT\n")
                self.proc.stdin.flush()
                self.proc.wait(timeout=3)
            except Exception:
                self.proc.kill()
        self.proc = None


worker = Worker()
atexit.register(worker.arreter)


def accepte(res):
    if res.get("score", 0) < config.SCORE_MINI:
        return False
    if config.FILTRE == "oiseaux":
        return res.get("class") == "Aves"
    if config.FILTRE == "animaux":
        return res.get("kingdom") == "Animalia"
    return True


def analyser_une_fois():
    """Renvoie False si le moteur d'analyse doit être redémarré."""
    time.sleep(config.DELAI)
    with verrou:
        image = derniere_image
    if image is None:
        return True
    x1, y1, x2, y2 = coordonnees_zone(image)
    zone = image[y1:y2, x1:x2]
    h, l = zone.shape[:2]
    if l > config.CAPTURE_LARGEUR_MAX:
        zone = cv2.resize(
            zone, (config.CAPTURE_LARGEUR_MAX, int(h * config.CAPTURE_LARGEUR_MAX / l)))
    cv2.imwrite(str(TMP), zone, [cv2.IMWRITE_JPEG_QUALITY, config.CAPTURE_QUALITE])

    maintenant = datetime.now()
    res = worker.analyser(str(TMP), config.DELAI_ANALYSE)
    if res is None or res.get("fin"):
        print("Le moteur d'analyse ne répond plus, redémarrage...")
        return False
    if not res.get("ok"):
        print("ERREUR ANALYSE :", res.get("erreur"))
        return True
    etat["analyses"] += 1

    if not accepte(res):
        print(maintenant.strftime("%H:%M:%S"), "-> ignoré")
        return True

    espece = res.get("species", "")
    francais = noms_fr.nom_francais(espece) or espece or "Inconnu"
    date = maintenant.strftime("%d/%m/%Y")
    heure = maintenant.strftime("%H:%M:%S")
    etat["retenus"] += 1

    try:
        nouveau = not CSV_FICHIER.exists()
        with open(CSV_FICHIER, "a", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f, delimiter=";")
            if nouveau:
                writer.writerow(["date", "heure", "nom_francais"])
            writer.writerow([date, heure, francais])
    except Exception as e:
        print("CSV non écrit (fichier ouvert dans Excel ?) :", e)

    if config.GARDER_IMAGES:
        try:
            TMP.replace(CAPTURES / (maintenant.strftime("%Y%m%d_%H%M%S") + ".jpg"))
            nettoyer()
        except Exception as e:
            print("Image non enregistrée :", e)

    historique.insert(0, {"date": date, "heure": heure, "nom": francais})
    del historique[30:]
    print(date, heure, "->", francais)
    return True


def boucle_analyse():
    while True:
        etat["worker_pret"] = False
        etat["modele"] = "Chargement du modèle..."
        try:
            worker.demarrer()
            msg = worker.attendre(config.DELAI_CHARGEMENT)
            while msg is not None and "pret" not in msg and not msg.get("fin"):
                msg = worker.attendre(config.DELAI_CHARGEMENT)
        except Exception as e:
            msg = {"pret": False, "erreur": str(e)}
        if not msg or not msg.get("pret"):
            etat["modele"] = "ERREUR de chargement (voir la console)"
            print("ERREUR MODÈLE :", (msg or {}).get("erreur", "pas de réponse"))
            print("Si c'est la première fois : lance installer.bat avec internet "
                  "pour télécharger le modèle une fois pour toutes.")
            worker.arreter()
            time.sleep(30)
            continue
        etat["modele"] = "Prêt"
        etat["worker_pret"] = True
        while True:
            declencher.wait()
            declencher.clear()
            occupe.set()
            try:
                continuer = analyser_une_fois()
            except Exception as e:
                print("ERREUR ANALYSE :", e)
                continuer = True
            finally:
                occupe.clear()
            if not continuer:
                break


# ---------- Flux vidéo pour la page ----------
def flux_mjpeg():
    clients["n"] += 1
    try:
        intervalle = 1.0 / config.STREAM_FPS
        while True:
            debut = time.time()
            try:
                with verrou:
                    image = derniere_image
                if image is not None:
                    h, l = image.shape[:2]
                    if l > config.STREAM_LARGEUR:
                        image = cv2.resize(
                            image, (config.STREAM_LARGEUR,
                                    int(h * config.STREAM_LARGEUR / l)))
                    else:
                        image = image.copy()
                    x1, y1, x2, y2 = coordonnees_zone(image)
                    bouge = etat["mouvement"] / 100 >= config.SEUIL
                    couleur = (0, 0, 255) if bouge else (0, 200, 0)
                    cv2.rectangle(image, (x1, y1), (x2, y2), couleur, 2)
                    ok, jpg = cv2.imencode(
                        ".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, config.STREAM_QUALITE])
                    if ok:
                        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
                               + jpg.tobytes() + b"\r\n")
            except GeneratorExit:
                raise
            except Exception as e:
                print("ERREUR FLUX :", e)
            reste = intervalle - (time.time() - debut)
            if reste > 0:
                time.sleep(reste)
    finally:
        clients["n"] -= 1


# ---------- Page web (aucune ressource externe) ----------
PAGE = """<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Détecteur d'animaux</title>
<style>
 body{font-family:system-ui,sans-serif;max-width:1000px;margin:16px auto;padding:0 12px;background:#fafafa;color:#222}
 header{display:flex;justify-content:space-between;align-items:baseline}
 h1{margin:0;font-size:22px} #horloge{color:#555}
 img{width:100%;border-radius:8px;background:#222;margin-top:10px}
 .boutons{margin:10px 0;display:flex;gap:8px;flex-wrap:wrap}
 button{padding:9px 16px;font-size:15px;cursor:pointer;border:1px solid #999;border-radius:6px;background:#fff}
 #infos{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:8px}
 .carte{background:#fff;border:1px solid #ddd;border-radius:8px;padding:8px 10px}
 .carte span{display:block;font-size:12px;color:#777} .carte b{font-size:15px}
 table{width:100%;border-collapse:collapse;margin-top:14px;background:#fff}
 td,th{border-bottom:1px solid #ddd;padding:6px 8px;text-align:left}
</style></head><body>
<header><h1>Détecteur d'animaux</h1><span id="horloge"></span></header>
<img src="/video" alt="Flux caméra">
<div class="boutons">
 <button onclick="fetch('/analyser',{method:'POST'})">Analyser maintenant</button>
 <button id="btnpause" onclick="fetch('/pause',{method:'POST'})">Mettre en pause</button>
</div>
<div id="infos"></div>
<table><thead><tr><th>Date</th><th>Heure</th><th>Animal</th></tr></thead>
<tbody id="lignes"></tbody></table>
<script>
function fmt(s){const h=Math.floor(s/3600),m=Math.floor(s%3600/60);return h+' h '+m+' min '+(s%60)+' s';}
function esc(t){return String(t).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
setInterval(()=>{document.getElementById('horloge').textContent=new Date().toLocaleString('fr-FR');},1000);
async function maj(){
 try{
  const r = await (await fetch('/etat')).json();
  const g = r.reglages;
  const cartes = [
   ['Caméra', r.camera],
   ['Résolution', r.largeur ? r.largeur+' × '+r.hauteur : '—'],
   ['FPS caméra', r.fps],
   ['Retard image', r.age===null ? '—' : r.age+' s'],
   ['Reconnexions', r.reconnexions],
   ['Flux dans la page', g.stream],
   ['Mouvement dans la zone', r.mouvement+' % (seuil '+g.seuil+' %)'],
   ['Dernier mouvement', r.dernier_mouvement],
   ['Moteur d analyse', r.modele],
   ['Noms français (Kiwix)', g.kiwix],
   ['Mode hors ligne', g.hors_ligne ? 'oui' : 'non'],
   ['Filtre', g.filtre],
   ['Analyses / retenus', r.analyses+' / '+r.retenus],
   ['Disque (captures)', r.disque_mo+' Mo, '+r.images+' images (max '+g.max_mo+' Mo)'],
   ['Détection', r.pause ? 'EN PAUSE' : 'active'],
   ['Spectateurs', r.spectateurs],
   ['En marche depuis', fmt(r.uptime)]
  ];
  document.getElementById('infos').innerHTML = cartes.map(
    c=>'<div class="carte"><span>'+esc(c[0])+'</span><b>'+esc(c[1])+'</b></div>').join('');
  document.getElementById('btnpause').textContent = r.pause ? 'Reprendre la détection' : 'Mettre en pause';
  document.getElementById('lignes').innerHTML = r.historique.map(
    l=>'<tr><td>'+esc(l.date)+'</td><td>'+esc(l.heure)+'</td><td>'+esc(l.nom)+'</td></tr>').join('');
 }catch(e){}
}
setInterval(maj,1000); maj();
</script></body></html>"""

app = Flask(__name__)
logging.getLogger("werkzeug").setLevel(logging.ERROR)


@app.route("/")
def accueil():
    return PAGE


@app.route("/video")
def video():
    return Response(flux_mjpeg(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/etat")
def route_etat():
    t = time.time()
    age = round(t - etat["derniere_image_t"], 1) if etat["derniere_image_t"] else None
    return jsonify({
        **etat,
        "age": age,
        "uptime": int(t - etat["debut"]),
        "spectateurs": clients["n"],
        "historique": historique,
        "reglages": {
            "stream": "{} px, {} im/s, qualité {}".format(
                config.STREAM_LARGEUR, config.STREAM_FPS, config.STREAM_QUALITE),
            "seuil": round(config.SEUIL * 100, 1),
            "max_mo": config.MAX_MO,
            "filtre": config.FILTRE,
            "kiwix": noms_fr.etat_kiwix(),
            "hors_ligne": config.HORS_LIGNE,
        },
    })


@app.route("/analyser", methods=["POST"])
def analyser():
    if etat["worker_pret"] and not occupe.is_set():
        declencher.set()
    return ("", 204)


@app.route("/pause", methods=["POST"])
def pause():
    etat["pause"] = not etat["pause"]
    return ("", 204)


if __name__ == "__main__":
    calculer_disque()
    charger_historique()
    threading.Thread(target=lire_camera, daemon=True).start()
    threading.Thread(target=boucle_analyse, daemon=True).start()
    threading.Timer(
        1.5, lambda: webbrowser.open("http://localhost:{}".format(config.PORT))).start()
    app.run(host="127.0.0.1", port=config.PORT, threaded=True, use_reloader=False)
