"""Carte des marchands onboardés eAriary.

Lit l'onglet « Marchands » du Google Sheet « Onboarding marchand » (statut final « Accepté »)
et les photos du Journal. Les photos restent privées dans le Drive : elles sont lues
par le script Google (action « photo », voir apps_script/Code.gs).
Lancement local : streamlit run carte.py
"""
from __future__ import annotations

import base64
from html import escape
from pathlib import Path

import folium
from folium.plugins import MarkerCluster
import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials
from streamlit_folium import st_folium

import photos
import sheets

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
LOGO = Path(__file__).parent / "assets" / "logo-eariary.png"

# Couleurs du logo
BLEU = "#147C90"
BLEU_FONCE = "#0D5664"
OLIVE = "#989B37"
ROUGE = "#CC3127"
FOND = "#F3F7F8"

st.set_page_config(page_title="Carte des marchands eAriary", layout="wide",
                   page_icon=str(LOGO) if LOGO.exists() else None)

st.markdown(f"""
<style>
  .stApp {{ background: {FOND}; }}
  .block-container {{ padding-top: 3.5rem; max-width: 1400px; }}
  iframe[title="streamlit_folium.st_folium"] {{ border-radius: 14px; box-shadow: 0 1px 3px rgba(13,86,100,.15); }}
  .leaflet-tooltip.infobulle {{ background: {BLEU_FONCE}; color: #fff; border: 0; border-radius: 8px;
                                padding: 7px 10px; font-size: 13px; }}
  h1, h2, h3 {{ color: {BLEU_FONCE}; }}
  [data-testid="stSidebar"] {{ background: #fff; border-right: 3px solid {BLEU}; }}
  [data-baseweb="tag"] {{ background: {BLEU} !important; }}

  .entete {{ display: flex; align-items: center; gap: 1.2rem; background: #fff;
             border-radius: 14px; padding: .9rem 1.4rem; margin-bottom: 1rem;
             border-bottom: 4px solid {BLEU}; box-shadow: 0 1px 3px rgba(13,86,100,.08); }}
  .entete img {{ height: 52px; }}
  .entete .titre {{ font-size: 1.45rem; font-weight: 700; color: {BLEU_FONCE}; line-height: 1.2; }}
  .entete .sous-titre {{ color: #5b6b70; font-size: .92rem; }}

  .kpi {{ background: #fff; border-radius: 12px; padding: .8rem 1rem;
          border-left: 5px solid var(--c); box-shadow: 0 1px 3px rgba(13,86,100,.08); }}
  .kpi .v {{ font-size: 1.8rem; font-weight: 700; color: var(--c); line-height: 1.1; }}
  .kpi .l {{ color: #5b6b70; font-size: .85rem; }}

  .fiche {{ background: #fff; border-radius: 14px; padding: 1.1rem 1.2rem;
            border-top: 5px solid {ROUGE}; box-shadow: 0 1px 3px rgba(13,86,100,.08); }}
  .fiche h3 {{ margin: 0 0 .4rem 0; font-size: 1.25rem; }}
  .fiche .badge {{ display: inline-block; background: {OLIVE}; color: #fff; border-radius: 999px;
                   padding: .1rem .7rem; font-size: .8rem; margin-bottom: .7rem; }}
  .fiche table {{ width: 100%; font-size: .9rem; border-collapse: collapse; }}
  .fiche td {{ padding: .28rem 0; border-bottom: 1px solid #edf1f2; vertical-align: top; }}
  .fiche td:first-child {{ color: #5b6b70; width: 38%; }}
  .fiche a {{ color: {BLEU}; font-weight: 600; text-decoration: none; }}
  .vide {{ background: #fff; border-radius: 14px; padding: 2rem 1.2rem; text-align: center;
           color: #5b6b70; border: 2px dashed #c9dadd; }}
  .legende {{ font-size: .85rem; color: #5b6b70; margin-top: .3rem; }}
  .legende span {{ display: inline-block; width: .8rem; height: .8rem; border-radius: 50%;
                   margin: 0 .3rem -.08rem .8rem; }}
</style>
""", unsafe_allow_html=True)


# ------------------------------------------------------------ données

@st.cache_resource
def classeur():
    creds = Credentials.from_service_account_info(dict(st.secrets["gcp_service_account"]), scopes=SCOPES)
    return gspread.authorize(creds).open_by_key(st.secrets["sheet_id"])


@st.cache_data(ttl=120, show_spinner="Lecture du Google Sheet…")
def marchands() -> pd.DataFrame:
    df = pd.DataFrame([vars(m) for m in sheets.lire_carte(classeur())])
    df["date_acceptation"] = pd.to_datetime(df["date_acceptation"])
    df["photos"] = (df["photo_devanture"] != "").astype(int) + (df["photo_produits"] != "").astype(int)
    return df


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def photo(id_fichier: str) -> bytes:
    return photos.telecharger(st.secrets["photos_url"], st.secrets["photos_secret"], id_fichier)


def logo_html() -> str:
    if not LOGO.exists():
        return ""
    return f'<img src="data:image/png;base64,{base64.b64encode(LOGO.read_bytes()).decode()}" alt="eAriary">'


def kpi(valeur, libelle: str, couleur: str) -> str:
    return f'<div class="kpi" style="--c:{couleur}"><div class="v">{valeur}</div><div class="l">{libelle}</div></div>'


def carte(places: pd.DataFrame, choisi: str | None) -> folium.Map:
    """Carte Leaflet (sans WebGL) : un cercle par marchand, le marchand choisi en rouge."""
    # Tuiles OpenStreetMap (sans clé API, contrairement à CARTO), désaturées pour faire ressortir les points
    m = folium.Map(location=[-18.9, 47.0], zoom_start=6, tiles="OpenStreetMap",
                   prefer_canvas=True, control_scale=True)
    m.get_root().header.add_child(folium.Element(
        "<style>.leaflet-tile-pane{filter:saturate(.3) brightness(1.05)}"
        f".groupe{{background:{BLEU};color:#fff;border:3px solid rgba(255,255,255,.85);border-radius:50%;"
        "display:flex;align-items:center;justify-content:center;font:700 13px sans-serif;"
        "box-shadow:0 1px 4px rgba(0,0,0,.3)}</style>"))
    # Points regroupés (avec leur nombre) tant qu'on n'a pas zoomé jusqu'au quartier
    groupes = MarkerCluster(
        options={"disableClusteringAtZoom": 16, "showCoverageOnHover": False, "maxClusterRadius": 45},
        icon_create_function="""function(g){var n=g.getChildCount(),t=n<10?30:n<100?38:46;
          return L.divIcon({html:'<div class="groupe" style="width:'+t+'px;height:'+t+'px">'+n+'</div>',
                            className:'',iconSize:[t,t]});}""",
    ).add_to(m)
    for r in places.itertuples():
        info = (f"<b>{escape(r.nom)}</b><br>{escape(r.categorie)} · {escape(r.ville)}"
                f"<br><span style='opacity:.8'>{escape(r.agent)} · {r.date_txt}</span>")
        est_choisi = r.id == choisi
        folium.CircleMarker(
            [r.latitude, r.longitude], radius=10 if est_choisi else 7, weight=2, color="#fff",
            fill=True, fill_opacity=1 if est_choisi else .85,
            fill_color=ROUGE if est_choisi else (OLIVE if r.photos else BLEU),
            tooltip=folium.Tooltip(info, class_name="infobulle"),
        ).add_to(m if est_choisi else groupes)
    if not places.empty:
        m.fit_bounds([[places["latitude"].min(), places["longitude"].min()],
                      [places["latitude"].max(), places["longitude"].max()]], padding=(30, 30))
    return m


# ------------------------------------------------------------ sélection

ss = st.session_state
ss.setdefault("choisi", None)       # ID marchand affiché dans la fiche


def choix_tableau():
    lignes = ss.tableau.selection.get("rows", [])
    ss.choisi = ss.tableau_ids[lignes[0]] if lignes else None


# ------------------------------------------------------------ interface

st.markdown(f"""
<div class="entete">{logo_html()}
  <div><div class="titre">Carte des marchands onboardés</div>
  <div class="sous-titre">Marchands au statut « Accepté » dans le Google Sheet Onboarding marchand</div></div>
</div>""", unsafe_allow_html=True)

try:
    tous = marchands()
except Exception as e:  # secrets absents, Sheet non partagé, réseau...
    st.error("Connexion au Google Sheet impossible. Vérifiez les secrets et le partage du Sheet "
             f"avec le compte de service.\n\nDétail : {e}")
    st.stop()

with st.sidebar:
    if LOGO.exists():
        st.image(str(LOGO))
    st.markdown("### Filtres")
    recherche = st.text_input("Rechercher un marchand", placeholder="Nom…")
    villes = st.multiselect("Ville", sorted(v for v in tous["ville"].unique() if v))
    categories = st.multiselect("Catégorie", sorted(c for c in tous["categorie"].unique() if c))
    agents = st.multiselect("Agent", sorted(a for a in tous["agent"].unique() if a))
    canaux = st.multiselect("Canal", sorted(c for c in tous["canal"].unique() if c))
    dates = tous["date_acceptation"].dropna()
    periode = None
    if not dates.empty:
        debut, fin = dates.min().date(), dates.max().date()
        periode = st.date_input("Période d'acceptation", value=(debut, fin),
                                min_value=debut, max_value=fin, format="DD/MM/YYYY")
    avec_photos = st.toggle("Avec photos uniquement")
    if st.button("Actualiser les données", width="stretch"):
        marchands.clear()
        st.rerun()

df = tous
if recherche:
    df = df[df["nom"].str.contains(recherche, case=False, regex=False)]
for col, valeurs in (("ville", villes), ("categorie", categories), ("agent", agents), ("canal", canaux)):
    if valeurs:
        df = df[df[col].isin(valeurs)]
if periode and len(periode) == 2:
    d = df["date_acceptation"]
    df = df[d.isna() | ((d >= pd.Timestamp(periode[0])) & (d <= pd.Timestamp(periode[1])))]
if avec_photos:
    df = df[df["photos"] > 0]

places = df.dropna(subset=["latitude", "longitude"]).copy()

c1, c2, c3, c4 = st.columns(4)
c1.markdown(kpi(len(df), "marchands onboardés", BLEU), unsafe_allow_html=True)
c2.markdown(kpi(len(places), "placés sur la carte", BLEU_FONCE), unsafe_allow_html=True)
c3.markdown(kpi(int((df["photos"] > 0).sum()), "avec photos", OLIVE), unsafe_allow_html=True)
c4.markdown(kpi(df["ville"].replace("", pd.NA).nunique(), "villes", ROUGE), unsafe_allow_html=True)
st.write("")

col_carte, col_fiche = st.columns([2.2, 1], gap="medium")

with col_carte:
    places["date_txt"] = places["date_acceptation"].dt.strftime("%d/%m/%Y").fillna("")
    choisi = places[places["id"] == ss.choisi]
    centre = [choisi.iloc[0]["latitude"], choisi.iloc[0]["longitude"]] if not choisi.empty else None
    clic = st_folium(carte(places, ss.choisi), height=560, use_container_width=True, key="carte",
                     center=centre, zoom=16 if centre else None, returned_objects=["last_object_clicked"])
    # st_folium renvoie le dernier clic à chaque rendu : on ne traite que les nouveaux
    point = (clic or {}).get("last_object_clicked")
    if point and point != ss.get("dernier_clic"):
        ss.dernier_clic = point
        proches = places[((places["latitude"] - point["lat"]).abs() < 1e-6)
                         & ((places["longitude"] - point["lng"]).abs() < 1e-6)]
        if not proches.empty and proches.iloc[0]["id"] != ss.choisi:
            ss.choisi = proches.iloc[0]["id"]
            st.rerun()
    st.markdown(f'<div class="legende"><span style="background:{BLEU}"></span>Marchand'
                f'<span style="background:{OLIVE}"></span>Avec photos'
                f'<span style="background:{ROUGE}"></span>Sélectionné</div>', unsafe_allow_html=True)
    sans_position = len(df) - len(places)
    if sans_position:
        st.caption(f"{sans_position} marchand(s) sans position GPS : visibles dans le tableau, pas sur la carte.")

with col_fiche:
    fiche = tous[tous["id"] == ss.choisi]
    if fiche.empty:
        st.markdown('<div class="vide"><b>Aucun marchand sélectionné</b><br/>'
                    'Cliquez sur un point de la carte ou sur une ligne du tableau.</div>',
                    unsafe_allow_html=True)
    else:
        m = fiche.iloc[0]
        lignes = [("Ville", m["ville"]), ("Téléphone", m["telephone"]), ("Agent", m["agent"]),
                  ("Canal", m["canal"]),
                  ("Accepté le", m["date_acceptation"].strftime("%d/%m/%Y") if pd.notna(m["date_acceptation"]) else "")]
        if pd.notna(m["latitude"]):
            lien = f"https://www.google.com/maps?q={m['latitude']},{m['longitude']}"
            lignes.append(("Position", f'<a href="{lien}" target="_blank">Ouvrir dans Google Maps</a>'))
        corps = "".join(f"<tr><td>{k}</td><td>{v if k == 'Position' else escape(str(v)) or '–'}</td></tr>"
                        for k, v in lignes)
        badge = f'<div class="badge">{escape(m["categorie"])}</div>' if m["categorie"] else ""
        st.markdown(f'<div class="fiche"><h3>{escape(m["nom"])}</h3>{badge}<table>{corps}</table></div>',
                    unsafe_allow_html=True)

        st.write("")
        st.markdown("#### Photos")
        liens = [(t, l) for t, l in (("Devanture", m["photo_devanture"]), ("Produits", m["photo_produits"])) if l]
        if not liens:
            st.caption("Pas de photo pour ce marchand.")
        for titre, lien in liens:
            try:
                st.image(photo(photos.id_drive(lien)), caption=titre, width="stretch")
            except Exception:
                st.markdown(f"[{titre} : voir dans Google Drive]({lien})")

st.markdown("### Liste des marchands")
tableau = df.sort_values("date_acceptation", ascending=False, na_position="last").reset_index(drop=True)
ss.tableau_ids = list(tableau["id"])
st.dataframe(
    tableau[["nom", "categorie", "ville", "telephone", "agent", "canal", "date_acceptation", "photos"]],
    hide_index=True, width="stretch", height=380, key="tableau",
    on_select=choix_tableau, selection_mode="single-row",
    column_config={
        "nom": "Marchand", "categorie": "Catégorie", "ville": "Ville", "telephone": "Téléphone",
        "agent": "Agent", "canal": "Canal",
        "date_acceptation": st.column_config.DateColumn("Accepté le", format="DD/MM/YYYY"),
        "photos": st.column_config.NumberColumn("Photos", format="%d"),
    },
)
