"""Carte des chantiers et des activités (à réaliser, en cours, réalisées)."""
from __future__ import annotations

import streamlit as st

import calculs
import db
import ui


def page() -> None:
    ui.en_tete("Carte des chantiers et des activités",
               "Grands cercles : chantiers, colorés selon leur état · petits points : activités localisées")
    s = calculs.synthese()
    act = calculs.activites()
    if s.empty:
        st.info("Aucun chantier à afficher.")
        return
    act = act.merge(s[["id", "nom", "lat", "lon"]].rename(columns={"id": "chantier_id", "nom": "chantier",
                                                                     "lat": "lat_ch", "lon": "lon_ch"}),
                    on="chantier_id", how="left")

    f1, f2, f3 = st.columns([1.4, 1, 1])
    choix = f1.multiselect("Chantiers", s["nom"].tolist(), placeholder="Tous les chantiers")
    etats = f2.multiselect("État des chantiers", list(calculs.COULEURS_ETAT), placeholder="Tous")
    statuts = f3.multiselect("Statut des activités", db.STATUTS_ACTIVITE, default=db.STATUTS_ACTIVITE)
    o1, o2 = st.columns(2)
    voir_ch = o1.toggle("Afficher les chantiers", value=True)
    voir_act = o2.toggle("Afficher les activités", value=True,
                         help="Une activité sans coordonnées propres est placée sur son chantier.")

    sc = s.copy()
    if choix:
        sc = sc[sc["nom"].isin(choix)]
    if etats:
        sc = sc[sc["etat"].isin(etats)]
    sa = act[act["chantier_id"].isin(sc["id"]) & act["statut"].isin(statuts)].copy()
    sa["lat"] = sa["lat"].fillna(sa["lat_ch"])
    sa["lon"] = sa["lon"].fillna(sa["lon_ch"])

    ui.carte(sc if voir_ch else None, sa if voir_act else None, hauteur=600, cle="carte_principale")
    l1, l2 = st.columns(2)
    with l1:
        st.caption("Chantiers")
        ui.legende(calculs.COULEURS_ETAT)
    with l2:
        st.caption("Activités")
        ui.legende(calculs.COULEURS_ACTIVITE)

    sans = sc[sc["lat"].isna() | sc["lon"].isna()]
    if not sans.empty:
        st.warning("Chantiers sans coordonnées, absents de la carte : " + ", ".join(sans["nom"])
                   + ". Ajoutez leurs coordonnées dans la page **Chantiers**.")

    with st.expander(f"Liste des activités affichées ({len(sa)})"):
        st.dataframe(ui.en_pct(sa, "avancement"), hide_index=True, column_order=["chantier", "titre", "statut", "avancement",
                                                         "date_fin_prevue", "lat", "lon"],
                     column_config={"chantier": "Chantier", "titre": "Activité", "statut": "Statut",
                                    "avancement": ui.colonne_pct("Avancement"),
                                    "date_fin_prevue": st.column_config.DateColumn("Fin prévue", format="DD/MM/YYYY"),
                                    "lat": st.column_config.NumberColumn("Latitude", format="%.5f"),
                                    "lon": st.column_config.NumberColumn("Longitude", format="%.5f")})
