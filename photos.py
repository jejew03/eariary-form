"""Photos du marchand (devanture, produits) : compression puis envoi dans Google Drive.

L'envoi passe par le script Google `apps_script/Code.gs`, publié en application web
depuis le compte propriétaire du Sheet : les photos vont dans son Drive.
Ce module ne dépend pas de Streamlit : il est testable avec une fausse fonction d'envoi.
"""
from __future__ import annotations

import base64
import io
import re
import unicodedata

import requests
from PIL import Image, ImageOps

TAILLE_MAX = 1600     # pixels, plus grand côté : lisible et ~300 Ko au lieu de 3-5 Mo
QUALITE = 80


def compresser(contenu: bytes) -> bytes:
    """JPEG redressé (orientation EXIF du téléphone) et réduit à TAILLE_MAX."""
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(contenu)))
    img = img.convert("RGB")
    img.thumbnail((TAILLE_MAX, TAILLE_MAX))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=QUALITE, optimize=True)
    return out.getvalue()


def _slug(texte: str) -> str:
    t = unicodedata.normalize("NFKD", texte or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "-", t).strip("-").lower()[:40] or "sans-nom"


def nom_fichier(saisie, type_photo: str) -> str:
    """2026-10-07_epicerie-fanja_antananarivo_devanture.jpg"""
    return f"{saisie.date:%Y-%m-%d}_{_slug(saisie.marchand)}_{_slug(saisie.ville)}_{type_photo}.jpg"


def rafraichir_formulaire(url: str, secret: str, post=requests.post) -> bool:
    """Demande au script Google de recharger tout de suite le formulaire des détails.

    Sans conséquence si ça échoue : le script recharge de toute façon toutes les 10 minutes.
    """
    try:
        rep = post(url, json={"secret": secret, "action": "maj"}, timeout=60)
        return bool(rep.json().get("ok"))
    except Exception:
        return False


def id_drive(lien: str) -> str:
    """Identifiant du fichier dans un lien Drive (…/file/d/<id>/view ou …?id=<id>), sinon ''."""
    m = re.search(r"/d/([\w-]{20,})|[?&]id=([\w-]{20,})", lien or "")
    return (m.group(1) or m.group(2)) if m else ""


def telecharger(url: str, secret: str, id_fichier: str, post=requests.post) -> bytes:
    """Récupère une photo par le script Google (les photos restent privées dans le Drive)."""
    rep = post(url, json={"secret": secret, "action": "photo", "id": id_fichier}, timeout=60)
    rep.raise_for_status()
    try:
        res = rep.json()
    except ValueError:
        raise RuntimeError("Le script photos ne répond pas correctement (vérifiez sa publication).")
    if not res.get("ok"):
        raise RuntimeError(f"Le script photos a refusé la lecture : {res.get('erreur')}")
    return base64.b64decode(res["data"])


def envoyer(url: str, secret: str, nom: str, contenu: bytes, post=requests.post) -> str:
    """Envoie un JPEG au script Google et renvoie le lien Drive de la photo."""
    rep = post(url, json={"secret": secret, "nom": nom, "data": base64.b64encode(contenu).decode()},
               timeout=60)
    if rep.status_code in (401, 403):
        raise RuntimeError("Le script photos refuse les appels : son déploiement doit avoir "
                           "« Qui a accès : Tout le monde ».")
    rep.raise_for_status()
    try:
        res = rep.json()
    except ValueError:   # page HTML : script non publié ou accès « Tout le monde » non coché
        raise RuntimeError("Le script photos ne répond pas correctement (vérifiez sa publication).")
    if not res.get("ok"):
        raise RuntimeError(f"Le script photos a refusé l'envoi : {res.get('erreur')}")
    return res["url"]
