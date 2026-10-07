"""Formulaire d'enrôlement marchand eAriary.

Alimente l'onglet « Journal » du Google Sheet « Compte rendu _ Appel ».
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
ss.setdefault("confirmer_doublon", False)


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

# ---- Position GPS
st.subheader("1. Position du marchand")
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
                          key=f"coord_{ss.form_id}")
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
    st.map(pd.DataFrame({"lat": [lat], "lon": [lon]}), zoom=16, size=8)
elif not ss.gps_erreur:
    st.caption("Appuyez sur le bouton devant le commerce du marchand. La position est facultative pour un appel.")

# ---- Informations
st.subheader("2. Marchand")
k = ss.form_id
aujourd_hui = datetime.now(TZ).date()

col1, col2 = st.columns(2)
date_contact = col1.date_input("Date", value=aujourd_hui, max_value=aujourd_hui, format="DD/MM/YYYY", key=f"date_{k}")
canal = col2.radio("Canal", L.canaux, index=L.canaux.index("Descente") if "Descente" in L.canaux else 0,
                   horizontal=True, key=f"canal_{k}")
marchand = st.text_input("Nom du marchand *", key=f"marchand_{k}",
                         help="Nom de l'enseigne, ou NOM Prénom pour un vendeur sans enseigne.")
col1, col2 = st.columns(2)
categorie = col1.selectbox("Catégorie *", L.categories, index=None, placeholder="Choisir", key=f"cat_{k}")
ville_choix = col2.selectbox("Ville *", L.villes + ["Autre…"], index=None, placeholder="Choisir", key=f"ville_{k}")
ville = ville_choix
if ville_choix == "Autre…":
    ville = st.text_input("Nom de la ville *", key=f"ville_autre_{k}")
telephone = st.text_input("Téléphone *", placeholder="034 12 345 67", key=f"tel_{k}")
col1, col2 = st.columns(2)
responsable = col1.text_input("Responsable / contact", key=f"resp_{k}")
email = col2.text_input("Email", key=f"email_{k}")

st.subheader("3. Résultat")
resultat = st.radio("Résultat *", L.resultats, index=0, horizontal=True, key=f"res_{k}")
date_rappel = None
if resultat in ("À relancer", "Injoignable"):
    date_rappel = st.date_input("Date de rappel", value=None, min_value=aujourd_hui,
                                format="DD/MM/YYYY", key=f"rappel_{k}")
commentaire = st.text_area("Commentaire", key=f"comm_{k}", height=80)

# ---- Contrôles
erreurs = []
if not agent:
    erreurs.append("Choisissez votre nom d'agent en haut de la page.")
if not marchand.strip():
    erreurs.append("Le nom du marchand est obligatoire.")
if not categorie:
    erreurs.append("Choisissez une catégorie.")
if not (ville or "").strip():
    erreurs.append("Choisissez une ville.")
if not sheets.telephone_valide(telephone):
    erreurs.append("Téléphone invalide : il faut 9 chiffres après 0 ou +261 (exemple : 034 12 345 67).")
if not sheets.email_valide(email):
    erreurs.append("Adresse email invalide.")
if canal == "Descente" and lat is None:
    erreurs.append("En descente, capturez la position du marchand avant d'enregistrer.")
if lat is not None and not sheets.position_plausible(lat, lon):
    erreurs.append("La position est hors de Madagascar : corrigez-la avant d'enregistrer.")

saisie = Saisie(
    date=date_contact, agent=agent or "", canal=canal, marchand=marchand, categorie=categorie or "",
    ville=ville or "", telephone=telephone, responsable=responsable, email=email, resultat=resultat,
    date_rappel=date_rappel, commentaire=commentaire, latitude=lat, longitude=lon,
)

existants = []
if marchand.strip() and (ville or "").strip() or sheets.telephone_valide(telephone):
    try:
        existants = sheets.doublons(journal(), saisie)
    except Exception:
        existants = []
if existants:
    acceptes = [l for l in existants if l[9] == "Accepté"]
    msg = (f"Ce marchand ou ce numéro figure déjà {len(existants)} fois dans le Journal"
           + (f", dont {len(acceptes)} fois « Accepté »" if acceptes else "") + ".")
    st.warning(msg)
    st.dataframe(pd.DataFrame([[l[0], l[1], l[3], l[5], l[6], l[9]] for l in existants],
                              columns=["Date", "Agent", "Marchand", "Ville", "Téléphone", "Résultat"]),
                 hide_index=True, width="stretch")
    st.checkbox("C'est bien un nouveau contact (relance ou autre marchand), enregistrer quand même",
                key=f"doublon_ok_{k}")

if st.button("Enregistrer", type="primary", width="stretch"):
    if existants and not ss.get(f"doublon_ok_{k}"):
        erreurs.append("Cochez la case de confirmation du doublon pour enregistrer.")
    if erreurs:
        for e in erreurs:
            st.error(e)
    else:
        with st.spinner("Enregistrement dans le Google Sheet…"):
            try:
                ligne = sheets.ajouter(classeur(), saisie)
            except Exception as e:
                st.error(f"L'enregistrement a échoué, rien n'a été écrit. Réessayez.\n\nDétail : {e}")
                st.stop()
        journal.clear()
        ss.derniere_saisie = (f"{saisie.marchand.strip()} enregistré ({saisie.resultat}) "
                              f"à la ligne {ligne} du Journal.")
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
    acceptes = sum(1 for l in lignes if l[9] == "Accepté")
    st.subheader(f"Mes saisies du jour : {len(lignes)} contact(s), {acceptes} accepté(s)")
    if lignes:
        st.dataframe(pd.DataFrame([[l[3], l[4], l[5], l[9]] for l in lignes][::-1],
                                  columns=["Marchand", "Catégorie", "Ville", "Résultat"]),
                     hide_index=True, width="stretch")
