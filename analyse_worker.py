"""Moteur d'analyse (BioCLIP 2), lancé par serveur.py dans un processus séparé.

Il tourne à priorité réduite pour ne jamais bloquer la lecture de la caméra.
Protocole : serveur.py envoie un chemin d'image par ligne ; ce programme répond
par une ligne "@@{json}". Les autres lignes (messages des bibliothèques) sont ignorées.
"""
import json
import os
import sys
import tempfile


def envoyer(obj):
    sys.stdout.write("@@" + json.dumps(obj, ensure_ascii=True) + "\n")
    sys.stdout.flush()


def main():
    try:
        import torch
        torch.set_num_threads(max(1, (os.cpu_count() or 4) // 2))
        from bioclip import Rank, TreeOfLifeClassifier
        from PIL import Image

        classifier = TreeOfLifeClassifier()
        # Échauffement : la première analyse est toujours la plus lente
        fichier = os.path.join(tempfile.gettempdir(), "perchoir_warmup.jpg")
        Image.new("RGB", (224, 224)).save(fichier)
        classifier.predict(fichier, Rank.SPECIES)
    except Exception as e:
        envoyer({"pret": False, "erreur": "{}: {}".format(type(e).__name__, e)})
        return 1

    envoyer({"pret": True})
    for ligne in sys.stdin:
        chemin = ligne.strip()
        if not chemin:
            continue
        if chemin == "QUIT":
            break
        try:
            res = classifier.predict(chemin, Rank.SPECIES)[0]
            envoyer({
                "ok": True,
                "species": str(res.get("species", "")),
                "common_name": str(res.get("common_name", "")),
                "kingdom": str(res.get("kingdom", "")),
                "class": str(res.get("class", "")),
                "score": float(res.get("score", 0.0)),
            })
        except Exception as e:
            envoyer({"ok": False, "erreur": "{}: {}".format(type(e).__name__, e)})
    return 0


if __name__ == "__main__":
    sys.exit(main())
