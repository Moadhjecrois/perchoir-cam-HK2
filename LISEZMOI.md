# Perchoir-cam : patch « 100 % local »

Ce zip contient le projet complet mis à jour. Pour l'appliquer sur ton dossier actuel :
décompresse-le par-dessus (remplace `serveur.py`) et ajoute les nouveaux fichiers.
Tes anciens `resultats.csv` et `captures/` ne sont pas touchés.

## Ce qui change

| Avant | Maintenant |
|---|---|
| Noms français via Wikidata (internet) | Noms français via **Kiwix** (Wikipédia hors ligne sur ton PC) |
| Le modèle pouvait contacter Hugging Face | Mode hors ligne : le modèle est téléchargé une fois, puis plus aucune connexion |
| L'analyse tournait dans le même programme que la caméra | L'analyse tourne dans un **processus séparé à priorité réduite** : la caméra ne gèle plus pendant l'analyse |
| Réglages dans `serveur.py` | Tous les réglages sont dans **`config.py`** |

### Correctifs caméra

- Paquets vidéo abîmés jetés (`discardcorrupt`), messages d'erreur FFmpeg masqués.
- Délais maximum à l'ouverture et à la lecture : un flux figé ne bloque plus le programme.
- Flux figé plus de `DELAI_FLUX_GELE` secondes : reconnexion automatique, avec attente croissante (1, 2, 4... 15 s).
- Le fond de la détection de mouvement est réappris à chaque reconnexion (`APPRENTISSAGE`).
- Le mouvement n'est calculé que `FPS_MOUVEMENT` fois par seconde (moins de processeur).
- Webcam / appareil photo USB : ouverture en DirectShow, format MJPG, résolution et FPS réglables.
- Le moteur d'analyse est relancé tout seul s'il plante ou ne répond plus.
- Une erreur d'écriture (CSV ouvert dans Excel) ne fait plus tomber le programme.

## Installation (première fois, avec internet)

1. Installe Python 3.10 ou plus (coche « Add python.exe to PATH »).
2. Double-clique sur **`installer.bat`**. Il crée l'environnement, installe les paquets et télécharge BioCLIP 2.
   Il se termine par « OK : le modèle est enregistré ». Après ça, tu peux couper internet.

## Kiwix (noms français hors ligne)

1. Télécharge **kiwix-serve** (outils Kiwix) sur le site officiel : https://www.kiwix.org
2. Télécharge le fichier **Wikipédia français** (`.zim`) depuis https://library.kiwix.org
   (cherche « wikipedia fr » ; vérifie la taille : la version avec images est très lourde,
   prends une version sans images si elle est proposée).
3. Ouvre **`lancer_kiwix.bat`** avec le Bloc-notes, mets les bons chemins pour `KIWIX` et `ZIM`, enregistre.
4. Double-clique dessus et laisse la fenêtre ouverte.

Le programme détecte tout seul le livre Wikipédia FR. Si ça ne marche pas, mets son nom
dans `KIWIX_LIVRE` (`config.py`) : c'est le nom qui apparaît dans l'adresse
`http://127.0.0.1:8080/content/NOM_DU_LIVRE/...` quand tu ouvres le ZIM dans ton navigateur.

Ordre de recherche d'un nom : `noms_perso.csv` (tes noms) > liste intégrée de 47 oiseaux courants >
`noms_fr_cache.json` (noms déjà trouvés) > Kiwix. Les noms trouvés via Kiwix sont mémorisés :
ils continuent de marcher même si Kiwix est éteint. Sans nom trouvé, le nom scientifique est affiché.

## Lancer

1. (Si tu veux les noms Kiwix) lance `lancer_kiwix.bat`.
2. Double-clique sur **`lancer.bat`**. La page s'ouvre sur http://localhost:5000.

La page n'utilise aucune ressource externe et n'écoute que sur ton PC (127.0.0.1).

## Ce que le programme contacte

- `127.0.0.1:8080` (Kiwix) : sur ton PC.
- Ta caméra (HUSKYLENS 2 : réseau local, ou webcam USB).
- Rien d'autre. `HORS_LIGNE = True` interdit au modèle toute connexion.

## Si quelque chose ne va pas

- **« ERREUR de chargement » dans la page** : le modèle n'est pas encore téléchargé. Relance `installer.bat` avec internet.
- **Noms en latin** : Kiwix n'est pas lancé ou le livre n'est pas détecté. Regarde la carte « Noms français (Kiwix) » dans la page.
- **Rien n'est jamais retenu** : mets `FILTRE = "tout"` dans `config.py` pour tester (le filtre suppose que le résultat contient les champs `kingdom` et `class`).
- **Ça gèle encore** : regarde les cartes FPS, « Retard image » et « Reconnexions ». Préfère la connexion USB du HUSKYLENS 2 au Wi-Fi.

## Ce qui a été testé, et ce qui ne l'a pas été

Testé (avec des simulations) : la recherche de noms via un faux serveur Kiwix (redirections,
titres nettoyés, cache, Kiwix éteint) ; le serveur complet avec une vidéo simulée (détection de
mouvement, filtre animaux, CSV, captures, reconnexion après la fin du flux, redémarrage du
moteur d'analyse quand il est tué, bouton pause).

**Non testé** : BioCLIP 2 réel, un vrai Kiwix, le vrai HUSKYLENS 2, les fichiers `.bat` sous Windows.
Si une étape échoue, copie le message d'erreur complet.

## Licence

MIT (voir `LICENSE`, remplace « TON NOM »). BioCLIP 2 et pybioclip sont sous licence MIT,
mais Wikipédia (via Kiwix) a ses propres licences : ce projet n'en redistribue aucun contenu.
