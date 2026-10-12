"""Tests sans réseau : un faux classeur remplace Google Sheets.

Lancement : python -m pytest -q tests
"""
from __future__ import annotations

import io
import sys
from datetime import date
from pathlib import Path
from unittest import mock

import pytest

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

import photos  # noqa: E402
import sheets  # noqa: E402
from sheets import Saisie  # noqa: E402


# ------------------------------------------------------------ faux Google Sheet

class FausseFeuille:
    def __init__(self, valeurs, row_count=1000):
        self.valeurs = [list(l) for l in valeurs]
        self.row_count = row_count
        self.ecritures = []

    def _cell(self, r, c):
        if r - 1 < len(self.valeurs) and c - 1 < len(self.valeurs[r - 1]):
            return self.valeurs[r - 1][c - 1]
        return ""

    def get_all_values(self):
        return [list(l) for l in self.valeurs]

    def col_values(self, c):
        vals = [self._cell(r, c) for r in range(1, len(self.valeurs) + 1)]
        while vals and vals[-1] == "":
            vals.pop()
        return vals

    def get(self, rng):
        # "A2:P" ou "A10:O10"
        debut, fin = rng.split(":")
        r1 = int("".join(ch for ch in debut if ch.isdigit()))
        r2 = "".join(ch for ch in fin if ch.isdigit())
        r2 = int(r2) if r2 else len(self.valeurs)
        ncol = ord(fin[0]) - ord("A") + 1
        out = [[self._cell(r, c) for c in range(1, ncol + 1)] for r in range(r1, r2 + 1)]
        return out

    def update(self, range_name, values, value_input_option):
        assert value_input_option == "USER_ENTERED"
        r = int("".join(ch for ch in range_name.split(":")[0] if ch.isdigit()))
        assert range_name in (f"A{r}:O{r}", f"Q{r}:R{r}"), "on n'écrit jamais dans la colonne P"
        while len(self.valeurs) < r:
            self.valeurs.append([])
        ligne = (self.valeurs[r - 1] + [""] * 18)[:18]
        debut = ord(range_name[0]) - ord("A")
        for i, v in enumerate(values[0]):
            v = str(v)
            ligne[debut + i] = v[1:] if v.startswith("'") else v
        self.valeurs[r - 1] = ligne
        self.ecritures.append((r, values[0]))

    def add_rows(self, n):
        self.row_count += n


class FauxClasseur:
    def __init__(self, feuilles):
        self.feuilles = feuilles

    def worksheet(self, nom):
        return self.feuilles[nom]


ENTETE = sheets.COLONNES + ["ID marchand"]
LISTES = [
    ["Agents", "Canal", "Catégories", "Villes", "Résultats"],
    ["Aina", "Appel", "Pharmacie", "Antananarivo", "Accepté"],
    ["Miharintsoa", "Descente", "Épicerie", "Antsirabe", "À relancer"],
    ["Équipe M&A", "", "Particulier", "", "Refusé"],
]


def journal_exemple():
    return [
        ENTETE,
        ["30/09/2026", "Aina", "Descente", "Boutique Soa", "Épicerie", "Antananarivo",
         "+261 34 11 111 11", "", "", "Accepté", "", "", "-18.9", "47.5", "Formulaire",
         "boutique soa | antananarivo"],
        [],                       # trou au milieu du Journal (comme les lignes 277-278)
        [],
        ["01/10/2026", "Miharintsoa", "Appel", "Pharmacie Zo", "Pharmacie", "Antsirabe",
         "+261 33 22 222 22", "", "", "À relancer", "", "", "", "", "Historique",
         "pharmacie zo | antsirabe"],
    ]


@pytest.fixture
def classeur():
    return FauxClasseur({"Journal": FausseFeuille(journal_exemple()), "Listes": FausseFeuille(LISTES)})


def saisie(**kw):
    base = dict(date=date(2026, 10, 7), agent="Aina", canal="Descente", marchand="Épicerie Fanja",
                categorie="Épicerie", ville="Antananarivo", telephone="034 12 345 67",
                latitude=-18.9075971, longitude=47.5253594)
    base.update(kw)
    return Saisie(**base)


# ------------------------------------------------------------ utilitaires

@pytest.mark.parametrize("entree,attendu", [
    ("034 12 345 67", "+261 34 12 345 67"),
    ("+261341234567", "+261 34 12 345 67"),
    ("261 34 12 345 67", "+261 34 12 345 67"),
    ("+261 0344134483", "+261 34 41 344 83"),
    ("0320215814", "+261 32 02 158 14"),
])
def test_normaliser_telephone(entree, attendu):
    assert sheets.normaliser_telephone(entree) == attendu
    assert sheets.telephone_valide(entree)


@pytest.mark.parametrize("entree", ["", "12345", "+261 79 577 77", "Mme Domoina"])
def test_telephone_invalide(entree):
    assert not sheets.telephone_valide(entree)


def test_coordonnees_et_emprise():
    assert sheets.lire_coordonnees("-18.907597, 47.525359") == (-18.907597, 47.525359)
    assert sheets.lire_coordonnees("-18,907597; 47,525359") == (-18.907597, 47.525359)
    assert sheets.lire_coordonnees("-18,9075644 47,5259717") == (-18.9075644, 47.5259717)
    assert sheets.lire_coordonnees("n'importe quoi") is None
    assert sheets.position_plausible(-18.9, 47.5)
    assert not sheets.position_plausible(18.908793, 47.526465)   # signe oublié
    assert not sheets.position_plausible(47.03, -19.85)           # lat/long inversées


def test_email():
    assert sheets.email_valide("")
    assert sheets.email_valide("contact@floribis.com")
    assert not sheets.email_valide("contact floribis")


# ------------------------------------------------------------ lecture

def test_listes_sans_equipes(classeur):
    L = sheets.lire_listes(classeur)
    assert L.agents == ["Aina", "Miharintsoa"]
    assert L.canaux == ["Appel", "Descente"]
    assert "Particulier" in L.categories
    assert L.resultats == ["Accepté", "À relancer", "Refusé"]


def test_doublons(classeur):
    j = sheets.lire_journal(classeur)
    assert len(j) == 2
    assert sheets.doublons(j, saisie()) == []
    # même nom + ville, casse et espaces différents
    assert len(sheets.doublons(j, saisie(marchand="  boutique SOA ", telephone="038 00 000 00"))) == 1
    # même téléphone écrit autrement
    assert len(sheets.doublons(j, saisie(marchand="Autre", telephone="0332222222"))) == 1


# ------------------------------------------------------------ écriture

def test_ecriture_apres_le_trou(classeur):
    n = sheets.ajouter(classeur, saisie(resultat="À relancer", date_rappel=date(2026, 10, 9),
                                        commentaire="Rappeler vendredi", email=" a@b.mg "))
    feuille = classeur.worksheet("Journal")
    assert n == 6, "doit écrire après la dernière ligne remplie, pas dans le trou"
    ligne = feuille.valeurs[n - 1]
    assert ligne[:12] == ["07/10/2026", "Aina", "Descente", "Épicerie Fanja", "Épicerie",
                          "Antananarivo", "+261 34 12 345 67", "", "a@b.mg", "À relancer",
                          "09/10/2026", "Rappeler vendredi"]
    assert ligne[12:15] == ["-18.907597", "47.525359", "Streamlit"]
    assert ligne[15] == "", "la colonne P (formule) n'est jamais touchée"
    # l'apostrophe garde le téléphone en texte côté Google Sheets
    assert feuille.ecritures[0][1][6] == "'+261 34 12 345 67"


def test_ecriture_sans_gps(classeur):
    n = sheets.ajouter(classeur, saisie(canal="Appel", latitude=None, longitude=None))
    assert classeur.worksheet("Journal").valeurs[n - 1][12:14] == ["", ""]


def test_ecriture_liens_photos(classeur):
    n = sheets.ajouter(classeur, saisie(photo_devanture="https://drive/d", photo_produits="https://drive/p"))
    feuille = classeur.worksheet("Journal")
    assert feuille.valeurs[n - 1][15:18] == ["", "https://drive/d", "https://drive/p"]
    assert [r for r, _ in feuille.ecritures] == [n, n]


def test_pas_d_ecriture_photos_sans_photo(classeur):
    sheets.ajouter(classeur, saisie())
    assert len(classeur.worksheet("Journal").ecritures) == 1


# ------------------------------------------------------------ photos

def _jpeg(largeur, hauteur, orientation=None):
    from PIL import Image

    img = Image.new("RGB", (largeur, hauteur), "red")
    buf = io.BytesIO()
    exif = Image.Exif()
    if orientation:
        exif[0x0112] = orientation
    img.save(buf, "JPEG", exif=exif)
    return buf.getvalue()


def test_compression_et_orientation():
    from PIL import Image

    # photo portrait prise téléphone couché : EXIF orientation 6 (rotation 90°)
    sortie = Image.open(io.BytesIO(photos.compresser(_jpeg(4000, 3000, orientation=6))))
    assert sortie.format == "JPEG"
    assert sortie.size == (1200, 1600)
    petite = Image.open(io.BytesIO(photos.compresser(_jpeg(800, 600))))
    assert petite.size == (800, 600), "pas d'agrandissement"


def test_nom_fichier():
    assert photos.nom_fichier(saisie(marchand="Épicerie d'Ankorondrano!"), "devanture") == \
        "2026-10-07_epicerie-d-ankorondrano_antananarivo_devanture.jpg"


def test_envoi_script_google():
    import base64

    post = mock.Mock()
    post.return_value.json.return_value = {"ok": True, "url": "https://drive.google.com/x"}
    lien = photos.envoyer("https://script/exec", "SECRET", "a.jpg", b"\xff\xd8donnees", post=post)
    assert lien == "https://drive.google.com/x"
    url, = post.call_args.args
    corps = post.call_args.kwargs["json"]
    assert url == "https://script/exec"
    assert corps["secret"] == "SECRET" and corps["nom"] == "a.jpg"
    assert base64.b64decode(corps["data"]) == b"\xff\xd8donnees"


def test_envoi_refuse_par_le_script():
    post = mock.Mock()
    post.return_value.json.return_value = {"ok": False, "erreur": "Accès refusé"}
    with pytest.raises(RuntimeError, match="Accès refusé"):
        photos.envoyer("https://script/exec", "MAUVAIS", "a.jpg", b"x", post=post)


def test_envoi_script_acces_restreint():
    post = mock.Mock()
    post.return_value.status_code = 401
    with pytest.raises(RuntimeError, match="Tout le monde"):
        photos.envoyer("https://script/exec", "S", "a.jpg", b"x", post=post)


def test_envoi_script_non_publie():
    post = mock.Mock()
    post.return_value.json.side_effect = ValueError("pas du JSON")
    with pytest.raises(RuntimeError, match="publication"):
        photos.envoyer("https://script/exec", "S", "a.jpg", b"x", post=post)


def test_ajoute_des_lignes_si_feuille_pleine():
    f = FausseFeuille(journal_exemple(), row_count=5)
    c = FauxClasseur({"Journal": f, "Listes": FausseFeuille(LISTES)})
    assert sheets.ajouter(c, saisie()) == 6
    assert f.row_count == 205


def test_collision_puis_reessai(classeur):
    """Un autre agent écrit sur la même ligne entre notre écriture et la relecture."""
    feuille = classeur.worksheet("Journal")
    update_orig = feuille.update
    etat = {"n": 0}

    def update_concurrent(range_name, values, value_input_option):
        update_orig(range_name, values, value_input_option)
        etat["n"] += 1
        if etat["n"] == 1:   # l'autre agent écrase notre ligne juste après
            update_orig(range_name, [["07/10/2026", "Maeva", "Descente", "Autre marchand"] + [""] * 11],
                        value_input_option)

    feuille.update = update_concurrent
    n = sheets.ajouter(classeur, saisie())
    assert n == 7
    assert feuille.valeurs[5][1] == "Maeva" and feuille.valeurs[6][3] == "Épicerie Fanja"


# ------------------------------------------------------------ interface (AppTest)

def lancer_app(classeur, gps=None):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(RACINE / "app.py"), default_timeout=30)
    at.secrets["sheet_id"] = "test"
    at.secrets["gcp_service_account"] = {"type": "service_account"}
    return at


@pytest.fixture
def app(classeur, monkeypatch):
    import gspread
    import streamlit as st
    from google.oauth2 import service_account

    st.cache_data.clear()        # chaque test repart de son propre faux classeur
    st.cache_resource.clear()

    monkeypatch.setattr(service_account.Credentials, "from_service_account_info",
                        staticmethod(lambda info, scopes: object()))
    client = mock.Mock()
    client.open_by_key.return_value = classeur
    monkeypatch.setattr(gspread, "authorize", lambda creds: client)
    import streamlit_js_eval
    monkeypatch.setattr(streamlit_js_eval, "streamlit_js_eval",
                        lambda js_expressions, key: {"lat": -18.9075971, "lon": 47.5253594,
                                                     "precision": 12.0, "t": 0})
    at = lancer_app(classeur)
    at.run()
    assert not at.exception, at.exception
    return at


def _par_label(widgets, label):
    return next(w for w in widgets if w.label.startswith(label))


def test_app_enregistre_nom_et_position(app, classeur):
    at = app
    _par_label(at.selectbox, "Agent").select("Aina").run()
    assert [w.label for w in at.text_input] == ["Nom du marchand *"], "seul champ texte restant"
    _par_label(at.text_input, "Nom du marchand").input("Épicerie Fanja").run()
    at.button[0].click().run()                       # Capturer ma position
    assert any("47.525359" in m.value for m in at.metric)
    assert any(c.value == "-18.907597, 47.525359" for c in at.code), "coordonnées copiables"
    _par_label(at.button, "Enregistrer").click().run()
    assert not at.exception, at.exception
    assert not at.error, [e.value for e in at.error]
    feuille = classeur.worksheet("Journal")
    ligne = feuille.valeurs[5]
    assert ligne[1:4] == ["Aina", "Descente", "Épicerie Fanja"]
    assert ligne[4:9] == [""] * 5, "catégorie, ville, téléphone, contact, email laissés vides"
    assert ligne[9] == "Accepté", "compté comme enrôlé dans le tableau de bord"
    assert ligne[10:12] == ["", ""]
    assert ligne[12:15] == ["-18.907597", "47.525359", "Streamlit"]
    assert any("enregistré" in s.value for s in at.success)
    # formulaire vidé après l'enregistrement
    assert _par_label(at.text_input, "Nom du marchand").value == ""


def test_app_refuse_sans_position(app, classeur):
    at = app
    _par_label(at.selectbox, "Agent").select("Aina").run()
    _par_label(at.text_input, "Nom du marchand").input("Épicerie Fanja").run()
    _par_label(at.button, "Enregistrer").click().run()
    assert any("position" in e.value for e in at.error)
    assert len(classeur.worksheet("Journal").ecritures) == 0


def test_app_refuse_sans_nom(app, classeur):
    at = app
    _par_label(at.selectbox, "Agent").select("Aina").run()
    at.button[0].click().run()
    _par_label(at.button, "Enregistrer").click().run()
    assert any("nom du marchand" in e.value for e in at.error)
    assert len(classeur.worksheet("Journal").ecritures) == 0
