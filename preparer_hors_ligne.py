"""À lancer UNE SEULE FOIS, avec internet : télécharge BioCLIP 2 sur ce PC.
Ensuite, le projet n'a plus besoin d'internet (HORS_LIGNE = True dans config.py)."""
import os
import tempfile

os.environ.pop("HF_HUB_OFFLINE", None)
os.environ.pop("TRANSFORMERS_OFFLINE", None)

from bioclip import Rank, TreeOfLifeClassifier
from PIL import Image

print("Téléchargement du modèle (peut être long, une seule fois)...")
classifier = TreeOfLifeClassifier()
fichier = os.path.join(tempfile.gettempdir(), "perchoir_prepa.jpg")
Image.new("RGB", (224, 224)).save(fichier)
classifier.predict(fichier, Rank.SPECIES)
print("OK : le modèle est enregistré sur ce PC. Tu peux couper internet.")
