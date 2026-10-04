"""Éléments d'interface partagés : carte, coordonnées, photos, pastilles."""
from __future__ import annotations

import io
import os
import re

import pandas as pd
import pydeck as pdk
import streamlit as st

import auth
import calculs

CENTRE_DEFAUT = (-4.325, 15.322)  # Kinshasa


def devise() -> str:
    return auth.secret("DEVISE", "USD")


def nom_entreprise() -> str:
    return auth.secret("NOM_ENTREPRISE", "My Destiny")


STATIQUE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
LOGO_SOMBRE = os.path.join(STATIQUE, "logo_sombre.svg")   # texte clair, pour la barre latérale
LOGO_CLAIR = os.path.join(STATIQUE, "logo_clair.svg")     # texte foncé, pour la page de connexion
ICONE = os.path.join(STATIQUE, "icone.svg")

STYLE = """
<style>
/* Titres : serrés, sans artifice */
h1 { letter-spacing: -0.02em; }
h2, h3 { letter-spacing: -0.01em; }
/* Indicateurs : un filet bleu des plans à gauche, chiffres en gras */
[data-testid="stMetric"] { border-left: 3px solid #1D4F91; padding: 2px 0 2px 14px; }
[data-testid="stMetricValue"] { font-weight: 700; letter-spacing: -0.02em; }
[data-testid="stMetricLabel"] p { color: #5B6B77; }
/* Barre latérale : l'élément actif marqué au jaune jalon */
[data-testid="stSidebarNav"] a[aria-current="page"] { box-shadow: inset 3px 0 0 #F2B705; }
/* Focus clavier visible */
button:focus-visible, a:focus-visible { outline: 2px solid #F2B705; outline-offset: 2px; }
</style>
"""

STYLE_CONNEXION = """
<style>
/* Page de connexion : papier de plan (quadrillage fin + trame tous les 5 carreaux) */
[data-testid="stMain"] {
  background-color: #F4F5F2;
  background-image:
    linear-gradient(rgba(29,79,145,.10) 1px, transparent 1px),
    linear-gradient(90deg, rgba(29,79,145,.10) 1px, transparent 1px),
    linear-gradient(rgba(29,79,145,.045) 1px, transparent 1px),
    linear-gradient(90deg, rgba(29,79,145,.045) 1px, transparent 1px);
  background-size: 120px 120px, 120px 120px, 24px 24px, 24px 24px;
}
[data-testid="stForm"] { background: #FFFFFF; box-shadow: 0 1px 0 #CDD2CC; }
@media (max-width: 640px) { [data-testid="stMain"] { background-size: 96px 96px, 96px 96px, 24px 24px, 24px 24px; } }
</style>
"""


def appliquer_style(connexion: bool = False) -> None:
    st.markdown(STYLE + (STYLE_CONNEXION if connexion else ""), unsafe_allow_html=True)


def lire_coordonnees(texte: str) -> tuple[float, float] | None:
    """Accepte « -4.3521, 15.3412 », « -4.3521 15.3412 » ou un lien Google Maps (…@-4.35,15.34,17z)."""
    if not texte or not texte.strip():
        return None
    t = texte.strip()
    m = re.search(r"@(-?\d+\.\d+),(-?\d+\.\d+)", t) or re.search(r"(-?\d+\.\d+)\s*[,;\s]\s*(-?\d+\.\d+)", t)
    if not m:
        return None
    lat, lon = float(m.group(1)), float(m.group(2))
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return lat, lon


def champ_coordonnees(cle: str, defaut: tuple[float, float] | None = None, aide: str | None = None) -> tuple[float, float] | None:
    valeur = f"{defaut[0]:.6f}, {defaut[1]:.6f}" if defaut and defaut[0] == defaut[0] else ""
    txt = st.text_input("Coordonnées GPS (latitude, longitude)", value=valeur, key=cle,
                        placeholder="-4.3521, 15.3412",
                        help=aide or "Dans Google Maps, appuyez longuement sur l'emplacement : les coordonnées "
                                     "s'affichent, copiez-les ici. Un lien Google Maps fonctionne aussi.")
    pt = lire_coordonnees(txt)
    if txt.strip() and pt is None:
        st.caption(":red[Coordonnées non reconnues : écrire par exemple -4.3521, 15.3412]")
    return pt


def couleur(rgb: tuple[int, int, int], alpha: int = 210) -> list[int]:
    return [rgb[0], rgb[1], rgb[2], alpha]


def legende(couleurs: dict[str, tuple[int, int, int]]) -> None:
    html = " &nbsp; ".join(
        f"<span style='display:inline-block;width:11px;height:11px;border-radius:50%;"
        f"background:rgb{tuple(c)};margin-right:4px;vertical-align:middle'></span>{nom}"
        for nom, c in couleurs.items())
    st.markdown(f"<div style='font-size:0.85rem'>{html}</div>", unsafe_allow_html=True)


def carte(points_chantiers: pd.DataFrame | None = None, points_activites: pd.DataFrame | None = None,
          hauteur: int = 520, cle: str | None = None) -> None:
    """Carte pydeck : chantiers (grands cercles colorés selon l'état), activités (petits points)."""
    couches, tous = [], []
    if points_chantiers is not None and not points_chantiers.dropna(subset=["lat", "lon"]).empty:
        pc = points_chantiers.dropna(subset=["lat", "lon"]).copy()
        pc["couleur"] = pc["etat"].map(lambda e: couleur(calculs.COULEURS_ETAT.get(e, (120, 120, 120))))
        pc["avancement_txt"] = pc["avancement"].map(lambda x: f"{x:.0%}")
        pc["info"] = pc.apply(lambda r: f"<b>{r['nom']}</b><br/>{r['etat']} · avancement {r['avancement_txt']}"
                                        f"<br/>{r.get('client') or ''}", axis=1)
        couches.append(pdk.Layer("ScatterplotLayer", pc, get_position=["lon", "lat"], get_fill_color="couleur",
                                 get_radius=180, radius_min_pixels=9, radius_max_pixels=30, pickable=True,
                                 stroked=True, get_line_color=[255, 255, 255], line_width_min_pixels=2))
        couches.append(pdk.Layer("TextLayer", pc, get_position=["lon", "lat"], get_text="nom", get_size=13,
                                 get_color=[30, 30, 30], get_pixel_offset=[0, -22], get_alignment_baseline="'bottom'",
                                 background=True, get_background_color=[255, 255, 255, 200],
                                 character_set="'auto'", font_family="'Arial, Helvetica, sans-serif'",
                                 font_weight=600))
        tous.append(pc[["lat", "lon"]])
    if points_activites is not None and not points_activites.dropna(subset=["lat", "lon"]).empty:
        pa = points_activites.dropna(subset=["lat", "lon"]).copy()
        pa["couleur"] = pa["statut"].map(lambda s: couleur(calculs.COULEURS_ACTIVITE.get(s, (120, 120, 120)), 230))
        pa["info"] = pa.apply(lambda r: f"<b>{r['titre']}</b><br/>{r.get('chantier', '')}<br/>{r['statut']} · "
                                        f"{r['avancement']:.0%}", axis=1)
        couches.append(pdk.Layer("ScatterplotLayer", pa, get_position=["lon", "lat"], get_fill_color="couleur",
                                 get_radius=40, radius_min_pixels=5, radius_max_pixels=14, pickable=True,
                                 stroked=True, get_line_color=[255, 255, 255], line_width_min_pixels=1))
        tous.append(pa[["lat", "lon"]])
    if tous:
        t = pd.concat(tous)
        lat, lon = float(t["lat"].mean()), float(t["lon"].mean())
        ecart = max(t["lat"].max() - t["lat"].min(), t["lon"].max() - t["lon"].min())
        zoom = 15 if ecart < 0.005 else 13 if ecart < 0.03 else 12 if ecart < 0.08 else 11 if ecart < 0.2 else 9
    else:
        (lat, lon), zoom = CENTRE_DEFAUT, 11
    deck = pdk.Deck(layers=couches, initial_view_state=pdk.ViewState(latitude=lat, longitude=lon, zoom=zoom),
                    tooltip={"html": "{info}", "style": {"fontSize": "12px"}}, map_style="light")
    st.pydeck_chart(deck, height=hauteur, key=cle)


def apercu_point(lat: float, lon: float, libelle: str = "Emplacement") -> None:
    df = pd.DataFrame([{"lat": lat, "lon": lon, "info": libelle}])
    deck = pdk.Deck(layers=[pdk.Layer("ScatterplotLayer", df, get_position=["lon", "lat"],
                                      get_fill_color=[220, 38, 38, 220], get_radius=30, radius_min_pixels=7,
                                      pickable=True)],
                    initial_view_state=pdk.ViewState(latitude=lat, longitude=lon, zoom=15),
                    tooltip={"html": "{info}"}, map_style="light")
    st.pydeck_chart(deck, height=260)


def colonne_pct(titre: str, aide: str | None = None):
    """Barre de progression en pourcentage entier (les valeurs doivent être sur 0-100)."""
    return st.column_config.ProgressColumn(titre, format="%.0f%%", min_value=0, max_value=100, help=aide)


def en_pct(df: pd.DataFrame, *cols: str) -> pd.DataFrame:
    """Copie du tableau avec les colonnes 0-1 converties en 0-100 pour l'affichage."""
    out = df.copy()
    for c in cols:
        out[c] = out[c] * 100
    return out


def compresser_photo(fichier) -> bytes | None:
    """Réduit la photo (1280 px max, JPEG) pour ne pas alourdir la base."""
    if fichier is None:
        return None
    from PIL import Image, ImageOps
    img = ImageOps.exif_transpose(Image.open(fichier)).convert("RGB")
    img.thumbnail((1280, 1280))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=72, optimize=True)
    return buf.getvalue()


def en_tete(titre: str, sous_titre: str | None = None) -> None:
    st.title(titre)
    if sous_titre:
        st.caption(sous_titre)
