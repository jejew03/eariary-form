"""Formulaire d'enrôlement marchand eAriary.

Alimente l'onglet « Journal » du Google Sheet « Onboarding marchand ».
Les coordonnées GPS sont prises automatiquement depuis le téléphone de l'agent.
Lancement local : streamlit run app.py
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials

import photos
import sheets
from sheets import Saisie

TZ = ZoneInfo("Indian/Antananarivo")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
PRECISION_MAX = 100  # mètres : au-delà, on signale une position imprécise

# Position haute précision (GPS du téléphone), délai 20 s, pas de cache
JS_POSITION = """
new Promise((resolve) => {
  if (!navigator.geolocation) {
    resolve({error: {code: 0, message: "Navigateur sans géolocalisation"}});
    return;
  }
  navigator.geolocation.getCurrentPosition(
    (p) => resolve({lat: p.coords.latitude, lon: p.coords.longitude,
                    precision: p.coords.accuracy, t: p.timestamp}),
    (e) => resolve({error: {code: e.code, message: e.message}}),
    {enableHighAccuracy: true, timeout: 20000, maximumAge: 0}
  );
})
"""
ERREURS_GPS = {
    1: "Accès à la position refusé. Autorisez la localisation pour ce site "
       "dans le navigateur (icône cadenas à gauche de l'adresse), puis réessayez.",
    2: "Position introuvable. Activez le GPS du téléphone et sortez si possible à découvert.",
    3: "Délai dépassé. Réessayez, le GPS met parfois quelques secondes à se fixer.",
}

st.set_page_config(page_title="Enrôlement eAriary", layout="centered")


# ------------------------------------------------------------ Google Sheet

@st.cache_resource
def classeur():
    creds = Credentials.from_service_account_info(dict(st.secrets["gcp_service_account"]), scopes=SCOPES)
    return gspread.authorize(creds).open_by_key(st.secrets["sheet_id"])


def envoyer_photo(fichier, saisie: Saisie, type_photo: str) -> str:
    """Compresse la photo et l'envoie au script Google ; renvoie le lien Drive."""
    return photos.envoyer(st.secrets["photos_url"], st.secrets["photos_secret"],
                          photos.nom_fichier(saisie, type_photo), photos.compresser(fichier.getvalue()))


@st.cache_data(ttl=600, show_spinner=False)
def listes() -> sheets.Listes:
    return sheets.lire_listes(classeur())


@st.cache_data(ttl=60, show_spinner=False)
def journal() -> list[list[str]]:
    return sheets.lire_journal(classeur())


# ------------------------------------------------------------ état de la page

ss = st.session_state
ss.setdefault("gps_essai", 0)        # change la clé du composant pour relancer la mesure
ss.setdefault("gps", None)           # dernière position valide {lat, lon, precision}
ss.setdefault("gps_erreur", None)
ss.setdefault("form_id", 0)          # change les clés des champs pour vider le formulaire
ss.setdefault("derniere_saisie", None)


def lancer_gps():
    ss.gps_essai += 1
    ss.gps = None
    ss.gps_erreur = None


def mesurer_position():
    """Demande la position au navigateur ; le résultat arrive au rendu suivant."""
    from streamlit_js_eval import streamlit_js_eval

    res = streamlit_js_eval(js_expressions=JS_POSITION, key=f"gps_{ss.gps_essai}")
    if not res:
        return
    if "error" in res:
        code = res["error"].get("code", 0)
        ss.gps_erreur = ERREURS_GPS.get(code, res["error"].get("message", "Erreur de localisation"))
    else:
        ss.gps = {"lat": res["lat"], "lon": res["lon"], "precision": res.get("precision")}
        ss.gps_erreur = None


# ------------------------------------------------------------ interface

st.title("Enrôlement marchand eAriary")

try:
    L = listes()
except Exception as e:  # secrets absents, Sheet non partagé, réseau...
    st.error("Connexion au Google Sheet impossible. Vérifiez les secrets et le partage du Sheet "
             f"avec le compte de service.\n\nDétail : {e}")
    st.stop()

# Agent mémorisé dans l'adresse (?agent=Aina) pour ne pas le ressaisir
agent_url = st.query_params.get("agent")
idx_agent = L.agents.index(agent_url) if agent_url in L.agents else None
agent = st.selectbox("Agent", L.agents, index=idx_agent, placeholder="Choisissez votre nom")
if agent and agent != agent_url:
    st.query_params["agent"] = agent

if ss.derniere_saisie:
    st.success(ss.derniere_saisie)
    ss.derniere_saisie = None

k = ss.form_id
aujourd_hui = datetime.now(TZ).date()

# ---- Marchand
st.subheader("1. Marchand")
marchand = st.text_input("Nom du marchand *", key=f"marchand_{k}",
                         help="Nom de l'enseigne, ou NOM Prénom pour un vendeur sans enseigne.")

# ---- Position GPS
st.subheader("2. Position du marchand")
st.button("Capturer ma position", on_click=lancer_gps, type="primary", width="stretch")
if ss.gps_essai and not ss.gps and not ss.gps_erreur:
    mesurer_position()
    if not ss.gps and not ss.gps_erreur:
        st.info("Localisation en cours… Autorisez l'accès à la position si le navigateur le demande.")

saisie_manuelle = st.toggle("Saisir les coordonnées à la main", value=False)
lat = lon = None
precision = None
if saisie_manuelle:
    texte = st.text_input("Coordonnées (latitude, longitude)", placeholder="-18.907597, 47.525359",
                          key=f"coord_{k}")
    coords = sheets.lire_coordonnees(texte)
    if texte and not coords:
        st.warning("Format attendu : latitude, longitude (exemple : -18.907597, 47.525359)")
    if coords:
        lat, lon = coords
elif ss.gps:
    lat, lon, precision = ss.gps["lat"], ss.gps["lon"], ss.gps["precision"]

if ss.gps_erreur and not saisie_manuelle:
    st.error(ss.gps_erreur)

if lat is not None:
    c1, c2, c3 = st.columns(3)
    c1.metric("Latitude", f"{lat:.6f}")
    c2.metric("Longitude", f"{lon:.6f}")
    c3.metric("Précision", f"± {precision:.0f} m" if precision else "manuelle")
    if not sheets.position_plausible(lat, lon):
        st.warning("Cette position est hors de Madagascar. Vérifiez le signe de la latitude (elle doit être négative).")
    elif precision and precision > PRECISION_MAX:
        st.warning(f"Position imprécise (± {precision:.0f} m). Activez le GPS et recapturez si possible.")
    st.caption("Coordonnées à copier (bouton de copie à droite du cadre) :")
    st.code(f"{lat:.6f}, {lon:.6f}", language=None)
    st.map(pd.DataFrame({"lat": [lat], "lon": [lon]}), zoom=16, size=8)
elif not ss.gps_erreur:
    st.caption("Appuyez sur le bouton devant le commerce du marchand.")

# ---- Photos
st.subheader("3. Photos")
photos_actives = "photos_url" in st.secrets and "photos_secret" in st.secrets
if not photos_actives:
    st.caption("Envoi des photos non configuré (photos_url / photos_secret absents des secrets).")
AIDE_PHOTO = "Sur le téléphone, choisissez « Appareil photo » pour prendre la photo maintenant."
col1, col2 = st.columns(2)
photo_devanture = col1.file_uploader("Photo de la devanture", type=["jpg", "jpeg", "png", "webp"],
                                     key=f"photo_dev_{k}", help=AIDE_PHOTO, disabled=not photos_actives)
photo_produits = col2.file_uploader("Photo des produits", type=["jpg", "jpeg", "png", "webp"],
                                    key=f"photo_prod_{k}", help=AIDE_PHOTO, disabled=not photos_actives)
if photo_devanture:
    col1.image(photo_devanture, width="stretch")
if photo_produits:
    col2.image(photo_produits, width="stretch")

# ---- Contrôles
erreurs = []
if not agent:
    erreurs.append("Choisissez votre nom d'agent en haut de la page.")
if not marchand.strip():
    erreurs.append("Le nom du marchand est obligatoire.")
if lat is None:
    erreurs.append("Capturez la position du marchand avant d'enregistrer.")
elif not sheets.position_plausible(lat, lon):
    erreurs.append("La position est hors de Madagascar : corrigez-la avant d'enregistrer.")

# Chaque enregistrement est un enrôlement fait sur place : « Accepté » le compte dans le tableau de bord
saisie = Saisie(date=aujourd_hui, agent=agent or "", canal="Descente", marchand=marchand,
                resultat="Accepté", latitude=lat, longitude=lon)

if st.button("Enregistrer", type="primary", width="stretch"):
    if erreurs:
        for e in erreurs:
            st.error(e)
    else:
        if photo_devanture or photo_produits:
            with st.spinner("Envoi des photos…"):
                try:
                    if photo_devanture:
                        saisie.photo_devanture = envoyer_photo(photo_devanture, saisie, "devanture")
                    if photo_produits:
                        saisie.photo_produits = envoyer_photo(photo_produits, saisie, "produits")
                except Exception as e:
                    st.error(f"L'envoi des photos a échoué, rien n'a été écrit dans le Journal. "
                             f"Réessayez.\n\nDétail : {e}")
                    st.stop()
        with st.spinner("Enregistrement dans le Google Sheet…"):
            try:
                ligne = sheets.ajouter(classeur(), saisie)
            except Exception as e:
                st.error(f"L'enregistrement a échoué, rien n'a été écrit. Réessayez.\n\nDétail : {e}")
                st.stop()
        journal.clear()
        ss.derniere_saisie = f"{saisie.marchand.strip()} enregistré à la ligne {ligne} du Journal."
        ss.form_id += 1          # vide le formulaire
        ss.gps = None
        ss.gps_essai = 0
        st.rerun()

# ---- Récapitulatif de l'agent
if agent:
    st.divider()
    try:
        lignes = [l for l in journal() if l[1] == agent and l[0] == aujourd_hui.strftime("%d/%m/%Y")]
    except Exception:
        lignes = []
    st.subheader(f"Mes saisies du jour : {len(lignes)} marchand(s)")
    if lignes:
        st.dataframe(pd.DataFrame([[l[3], l[12], l[13]] for l in lignes][::-1],
                                  columns=["Marchand", "Latitude", "Longitude"]),
                     hide_index=True, width="stretch")
