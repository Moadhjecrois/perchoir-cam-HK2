"""Réglages du projet. Modifie ce fichier (pas serveur.py)."""

# ================= CAMÉRA =================
# Adresse RTSP (HUSKYLENS 2) ou numéro (0, 1, 2...) pour une webcam / un appareil photo en USB
CAMERA = "rtsp://192.168.88.1:8554/live"
CAMERA_LARGEUR = 1280      # webcam USB seulement
CAMERA_HAUTEUR = 720       # webcam USB seulement
CAMERA_FPS = 30            # webcam USB seulement
DELAI_FLUX_GELE = 6        # secondes sans image avant de se reconnecter

# ================= DÉTECTION =================
# Zone du perchoir, en fractions de l'image : (gauche, haut, droite, bas)
ZONE = (0.25, 0.25, 0.75, 0.75)
SEUIL = 0.02               # part de la zone qui doit bouger (0.02 = 2 %)
PAUSE = 5                  # secondes minimum entre deux analyses
DELAI = 0.7                # attente après le mouvement avant la photo
FPS_MOUVEMENT = 10         # calculs de mouvement par seconde (économise le processeur)
APPRENTISSAGE = 3          # secondes d'apprentissage du fond après chaque connexion

# Que garder ? "oiseaux", "animaux" ou "tout". Le reste est ignoré.
FILTRE = "animaux"
SCORE_MINI = 0.30          # confiance minimale pour accepter un résultat

# ================= 100 % LOCAL =================
HORS_LIGNE = True          # le modèle ne se connecte jamais à internet (voir LISEZMOI)
KIWIX_ACTIF = True         # noms français via Kiwix (Wikipédia hors ligne)
KIWIX_URL = "http://127.0.0.1:8080"
KIWIX_LIVRE = ""           # laisse vide pour détecter le livre Wikipédia FR tout seul
KIWIX_DELAI = 5            # secondes d'attente maximum pour Kiwix

# ================= ESPACE DISQUE =================
GARDER_IMAGES = True       # False = n'enregistre aucune image (seulement le CSV)
MAX_IMAGES = 300
MAX_MO = 200
CAPTURE_LARGEUR_MAX = 800
CAPTURE_QUALITE = 80

# ================= PAGE WEB =================
STREAM_FPS = 8
STREAM_LARGEUR = 960
STREAM_QUALITE = 65
PORT = 5000
DEBUG = False

# ================= MOTEUR D'ANALYSE =================
DELAI_CHARGEMENT = 900     # secondes max pour charger le modèle
DELAI_ANALYSE = 180        # secondes max pour une analyse
