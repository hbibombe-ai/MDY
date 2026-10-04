"""Historique des rapports, filtres et export Excel."""
from __future__ import annotations

import datetime as dt
import io

import pandas as pd
import streamlit as st

import calculs
import db
import ui


def page() -> None:
    ui.en_tete("Historique des rapports", "Tous les rapports saisis, avec leur statut de validation")
    r = calculs.rapports(avec_photo=False)
    if r.empty:
        st.info("Aucun rapport pour le moment.")
        return
    ch = calculs.chantiers()
    act = calculs.activites()
    r["chantier"] = r["chantier_id"].map(dict(zip(ch["id"], ch["nom"])))
    r["activite"] = r["activite_id"].map(dict(zip(act["id"], act["titre"]))).fillna("Général")
    r["unite"] = r["activite_id"].map(dict(zip(act["id"], act["unite"]))).fillna("")
    noms = calculs.noms_utilisateurs()
    r["auteur"] = r["cree_par"].map(noms)
    r["validateur"] = r["valide_par"].map(noms)

    f1, f2, f3 = st.columns([1.5, 1.2, 1])
    choix = f1.multiselect("Chantiers", sorted(r["chantier"].dropna().unique()), placeholder="Tous les chantiers")
    debut_min = min(r["date_rapport"])
    periode = f2.date_input("Période", value=(max(debut_min, dt.date.today() - dt.timedelta(days=30)), dt.date.today()),
                            format="DD/MM/YYYY")
    statuts = f3.multiselect("Validation", ["En attente", "Validé", "Rejeté"], placeholder="Tous")
    v = r.copy()
    if choix:
        v = v[v["chantier"].isin(choix)]
    if isinstance(periode, (tuple, list)) and len(periode) == 2:
        v = v[(v["date_rapport"] >= periode[0]) & (v["date_rapport"] <= periode[1])]
    if statuts:
        v = v[v["statut_validation"].isin(statuts)]

    dev = ui.devise()
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Rapports", len(v))
    k2.metric("Validés", int((v["statut_validation"] == "Validé").sum()))
    k3.metric("Dépenses validées", calculs.fmt_montant(v.loc[v["statut_validation"] == "Validé", "depenses"].sum(), dev))
    k4.metric("Incidents", int(v["incident"].sum()))

    colonnes = ["date_rapport", "chantier", "activite", "quantite", "unite", "effectif", "depenses", "incident",
                "incident_desc", "materiaux", "commentaire", "statut_validation", "motif_rejet", "auteur", "validateur",
                "lat", "lon", "a_photo"]
    noms_col = {"date_rapport": "Date", "chantier": "Chantier", "activite": "Activité", "quantite": "Quantité",
                "unite": "Unité", "effectif": "Effectif", "depenses": f"Dépenses ({dev})", "incident": "Incident",
                "incident_desc": "Description de l'incident", "materiaux": "Matériaux", "commentaire": "Observations",
                "statut_validation": "Validation", "motif_rejet": "Motif de rejet", "auteur": "Saisi par",
                "validateur": "Validé par", "lat": "Latitude", "lon": "Longitude", "a_photo": "Photo"}
    sel = st.dataframe(v, hide_index=True, column_order=colonnes, on_select="rerun", selection_mode="single-row",
                       column_config={k: (st.column_config.DateColumn(t, format="DD/MM/YYYY") if k == "date_rapport"
                                          else st.column_config.CheckboxColumn(t) if k in ("incident", "a_photo")
                                          else t) for k, t in noms_col.items()},
                       key="table_historique")
    lignes = sel.selection.rows if sel and hasattr(sel, "selection") else []
    if lignes:
        x = v.iloc[lignes[0]]
        st.markdown(f"**{x['date_rapport']:%d/%m/%Y} · {x['chantier']} · {x['activite']}** — saisi par {x['auteur']}")
        if x["a_photo"]:
            photo = db.lire("select photo from rapports where id = :i", i=int(x["id"]))["photo"].iloc[0]
            st.image(bytes(photo), width=480)
        else:
            st.caption("Pas de photo pour ce rapport.")
    else:
        st.caption("Cliquez sur une ligne pour afficher sa photo.")

    buf = io.BytesIO()
    export = v[colonnes].rename(columns=noms_col)
    export["Date"] = pd.to_datetime(export["Date"])
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        export.to_excel(w, index=False, sheet_name="Rapports")
        ws = w.sheets["Rapports"]
        for col in ws.columns:
            ws.column_dimensions[col[0].column_letter].width = 18
    st.download_button("Télécharger en Excel", buf.getvalue(), type="primary",
                       file_name=f"rapports_{dt.date.today():%Y%m%d}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
