"""Accès au Google Sheet « Onboarding marchand » (onglets Journal et Listes).

Ce module ne dépend pas de Streamlit : il est testable avec un faux classeur.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime

JOURNAL = "Journal"
LISTES = "Listes"
MARCHANDS = "Marchands"
ORIGINE = "Streamlit"

# Colonnes A à O du Journal (P est calculée par formule : on n'y écrit jamais)
COLONNES = [
    "Date", "Agent", "Canal", "Marchand", "Catégorie", "Ville", "Téléphone",
    "Responsable / contact", "Email", "Résultat", "Date de rappel",
    "Commentaire", "Latitude", "Longitude", "Origine",
]
# Colonnes Q et R : liens Drive des photos (après la colonne P calculée)
COLONNES_PHOTOS = ["Photo devanture", "Photo produits"]

# Emprise de Madagascar, pour détecter une position aberrante
LAT_MIN, LAT_MAX = -25.7, -11.9
LON_MIN, LON_MAX = 43.1, 50.6


@dataclass
class Listes:
    agents: list[str] = field(default_factory=list)
    canaux: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    villes: list[str] = field(default_factory=list)
    resultats: list[str] = field(default_factory=list)


@dataclass
class Marchand:
    """Un marchand accepté, vu par la carte (onglet Marchands + photos du Journal)."""
    id: str
    nom: str
    categorie: str = ""
    ville: str = ""
    telephone: str = ""
    agent: str = ""
    canal: str = ""
    date_acceptation: date | None = None
    latitude: float | None = None
    longitude: float | None = None
    photo_devanture: str = ""     # lien Google Drive
    photo_produits: str = ""


@dataclass
class Saisie:
    date: date
    agent: str
    canal: str
    marchand: str
    categorie: str = ""
    ville: str = ""
    telephone: str = ""
    responsable: str = ""
    email: str = ""
    resultat: str = "Accepté"
    date_rappel: date | None = None
    commentaire: str = ""
    latitude: float | None = None
    longitude: float | None = None
    photo_devanture: str = ""     # lien Google Drive
    photo_produits: str = ""

    def identifiant(self) -> str:
        """Même clé que la colonne P du Journal : « marchand | ville » en minuscules."""
        return identifiant(self.marchand, self.ville)

    def en_ligne(self) -> list:
        """Ligne A:O prête pour l'API (saisie USER_ENTERED, locale fr_FR)."""
        tel = normaliser_telephone(self.telephone)
        return [
            self.date.strftime("%d/%m/%Y"),
            self.agent,
            self.canal,
            self.marchand.strip(),
            self.categorie,
            self.ville.strip(),
            ("'" + tel) if tel else "",          # apostrophe : reste du texte
            self.responsable.strip(),
            self.email.strip(),
            self.resultat,
            self.date_rappel.strftime("%d/%m/%Y") if self.date_rappel else "",
            self.commentaire.strip(),
            round(self.latitude, 6) if self.latitude is not None else "",
            round(self.longitude, 6) if self.longitude is not None else "",
            ORIGINE,
        ]


# --------------------------------------------------------------- utilitaires

def identifiant(marchand: str, ville: str) -> str:
    return f"{marchand.strip().lower()} | {ville.strip().lower()}"


def chiffres(tel: str) -> str:
    """Les 9 chiffres significatifs d'un numéro malgache, ou '' si invalide."""
    c = re.sub(r"\D", "", tel or "")
    if c.startswith("261"):
        c = c[3:]
    if c.startswith("0"):
        c = c[1:]
    return c if len(c) == 9 else ""


def normaliser_telephone(tel: str) -> str:
    """034 12 345 67 / +261341234567 / 261 34... -> +261 34 12 345 67."""
    c = chiffres(tel)
    if not c:
        return (tel or "").strip()
    return f"+261 {c[:2]} {c[2:4]} {c[4:7]} {c[7:]}"


def telephone_valide(tel: str) -> bool:
    return bool(chiffres(tel))


def email_valide(email: str) -> bool:
    return not email or bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email.strip()))


def position_plausible(lat: float | None, lon: float | None) -> bool:
    if lat is None or lon is None:
        return False
    return LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX


def lire_coordonnees(texte: str) -> tuple[float, float] | None:
    """Accepte « -18.9075, 47.5253 », « -18,9075; 47,5253 » ou « -18,9075 47,5253 »."""
    m = re.search(r"(-?\d{1,2}[.,]\d+)\s*[,; ]\s*(-?\d{1,3}[.,]\d+)", texte or "")
    if not m:
        return None
    return float(m.group(1).replace(",", ".")), float(m.group(2).replace(",", "."))


# --------------------------------------------------------------- lecture

def _colonne(valeurs: list[list[str]], idx: int) -> list[str]:
    out = []
    for ligne in valeurs[1:]:
        if len(ligne) > idx and str(ligne[idx]).strip():
            out.append(str(ligne[idx]).strip())
    return out


def lire_listes(classeur) -> Listes:
    valeurs = classeur.worksheet(LISTES).get_all_values()
    agents = [a for a in _colonne(valeurs, 0) if not a.startswith("Équipe")]
    return Listes(
        agents=agents,
        canaux=_colonne(valeurs, 1) or ["Appel", "Descente"],
        categories=_colonne(valeurs, 2),
        villes=_colonne(valeurs, 3),
        resultats=_colonne(valeurs, 4),
    )


def lire_journal(classeur) -> list[list[str]]:
    """Lignes de données A:P (sans l'en-tête), complétées à 16 colonnes."""
    valeurs = classeur.worksheet(JOURNAL).get("A2:P")
    return [(list(l) + [""] * 16)[:16] for l in valeurs if len(l) > 3 and str(l[3]).strip()]


def doublons(journal: list[list[str]], saisie: Saisie) -> list[list[str]]:
    """Lignes existantes pour le même marchand (nom + ville) ou le même téléphone."""
    cle = saisie.identifiant()
    tel = chiffres(saisie.telephone)
    trouves = []
    for l in journal:
        meme_marchand = identifiant(l[3], l[5]) == cle
        meme_tel = bool(tel) and chiffres(l[6]) == tel
        if meme_marchand or meme_tel:
            trouves.append(l)
    return trouves


# --------------------------------------------------------------- écriture

def _premiere_ligne_libre(feuille) -> int:
    """Ligne juste après la dernière ligne ayant un nom de marchand (colonne D).

    On n'utilise pas append_row : l'API « append » s'arrête au premier trou
    du tableau et peut écrire au milieu des données.
    """
    col_d = feuille.col_values(4)            # inclut l'en-tête
    derniere = 1
    for i, v in enumerate(col_d, start=1):
        if str(v).strip():
            derniere = i
    return derniere + 1


def ajouter(classeur, saisie: Saisie, tentatives: int = 3) -> int:
    """Écrit la saisie dans le Journal (A:O, puis Q:R pour les photos) et renvoie le numéro de ligne."""
    feuille = classeur.worksheet(JOURNAL)
    ligne = saisie.en_ligne()
    for _ in range(tentatives):
        n = _premiere_ligne_libre(feuille)
        if n > feuille.row_count:
            feuille.add_rows(200)
        feuille.update(range_name=f"A{n}:O{n}", values=[ligne], value_input_option="USER_ENTERED")
        # Contrôle anti-collision : deux agents peuvent viser la même ligne
        relu = feuille.get(f"A{n}:O{n}")
        relu = (relu[0] if relu else []) + [""] * 15
        if relu[1] == saisie.agent and relu[3].strip() == saisie.marchand.strip():
            if saisie.photo_devanture or saisie.photo_produits:
                feuille.update(range_name=f"Q{n}:R{n}",
                               values=[[saisie.photo_devanture, saisie.photo_produits]],
                               value_input_option="USER_ENTERED")
            return n
    raise RuntimeError("Écriture non confirmée après plusieurs tentatives, réessayez.")


# --------------------------------------------------------------- carte

def _nombre(texte) -> float | None:
    """« -18,901233 » (locale fr_FR) ou « -18.901233 » -> float, sinon None."""
    try:
        return float(str(texte).strip().replace(",", "."))
    except ValueError:
        return None


def _date(texte) -> date | None:
    try:
        return datetime.strptime(str(texte).strip(), "%d/%m/%Y").date()
    except ValueError:
        return None


def _par_entete(valeurs: list[list[str]]) -> list[dict[str, str]]:
    """Lignes sous forme {en-tête: valeur} ; les en-têtes sont débarrassés des espaces."""
    if not valeurs:
        return []
    entete = [str(h).strip() for h in valeurs[0]]
    return [{h: str(l[i]).strip() if i < len(l) else "" for i, h in enumerate(entete)}
            for l in valeurs[1:]]


def lire_carte(classeur) -> list[Marchand]:
    """Marchands au statut final « Accepté » (onglet Marchands), avec leurs photos.

    Les photos ne sont que dans le Journal : on garde, par marchand, le dernier lien
    non vide de chaque type. Les marchands sans position ont latitude/longitude à None.
    """
    photos: dict[str, list[str]] = {}
    for l in _par_entete(classeur.worksheet(JOURNAL).get_all_values()):
        cle = l.get("ID marchand") or identifiant(l.get("Marchand", ""), l.get("Ville", ""))
        p = photos.setdefault(cle, ["", ""])
        for i, col in enumerate(COLONNES_PHOTOS):
            if l.get(col):
                p[i] = l[col]

    marchands = []
    for l in _par_entete(classeur.worksheet(MARCHANDS).get_all_values()):
        if l.get("Statut final") != "Accepté" or not l.get("Marchand"):
            continue
        cle = l.get("ID marchand") or identifiant(l["Marchand"], l.get("Ville", ""))
        lat, lon = _nombre(l.get("Latitude", "")), _nombre(l.get("Longitude", ""))
        if not position_plausible(lat, lon):
            lat = lon = None
        devanture, produits = photos.get(cle, ["", ""])
        marchands.append(Marchand(
            id=cle, nom=l["Marchand"], categorie=l.get("Catégorie", ""), ville=l.get("Ville", ""),
            telephone=l.get("Téléphone", ""), agent=l.get("Agent crédité", ""),
            canal=l.get("Canal", ""), date_acceptation=_date(l.get("Date d'acceptation", "")),
            latitude=lat, longitude=lon, photo_devanture=devanture, photo_produits=produits,
        ))
    return marchands
