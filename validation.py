"""Validation des rapports par le conducteur de travaux ou la direction."""
from __future__ import annotations

import streamlit as st

import auth
import calculs
import db
import ui


def nombre_en_attente() -> int:
    r = calculs.rapports(avec_photo=False)
    return int((r["statut_validation"] == "En attente").sum())


def _decider(ids: list[int], statut: str, motif: str | None = None) -> None:
    u = auth.utilisateur()
    t = db.rapports
    db.executer(t.update().where(t.c.id.in_(ids)).values(statut_validation=statut, valide_par=u["id"],
                                                         valide_le=db.maintenant(), motif_rejet=motif))


def page() -> None:
    ui.en_tete("Validation des rapports",
               "Seuls les rapports validés comptent dans l'avancement et les dépenses du tableau de bord")
    if msg := st.session_state.pop("validation_msg", None):
        st.success(msg)
    r = calculs.rapports(avec_photo=False)
    r = r[r["statut_validation"] == "En attente"].copy()
    if r.empty:
        st.success("Aucun rapport en attente de validation.")
        return
    ch = calculs.chantiers()
    act = calculs.activites()
    noms = calculs.noms_utilisateurs()
    r["chantier"] = r["chantier_id"].map(dict(zip(ch["id"], ch["nom"])))
    r["activite"] = r["activite_id"].map(dict(zip(act["id"], act["titre"]))).fillna("Général")
    r["unite"] = r["activite_id"].map(dict(zip(act["id"], act["unite"]))).fillna("")
    r["auteur"] = r["cree_par"].map(noms)
    r["valider"] = False

    st.caption(f"{len(r)} rapport(s) en attente. Cochez ceux qui sont corrects, puis validez-les ensemble ; "
               "ouvrez un rapport ci-dessous pour voir sa photo ou le rejeter avec un motif.")
    choix = st.data_editor(
        r, hide_index=True, key="table_validation", disabled=[c for c in r.columns if c != "valider"],
        column_order=["valider", "date_rapport", "chantier", "activite", "quantite", "unite", "effectif", "depenses",
                      "incident", "auteur"],
        column_config={"valider": st.column_config.CheckboxColumn("Valider"),
                       "date_rapport": st.column_config.DateColumn("Date", format="DD/MM/YYYY"),
                       "chantier": "Chantier", "activite": "Activité", "quantite": "Quantité", "unite": "Unité",
                       "effectif": "Effectif",
                       "depenses": st.column_config.NumberColumn(f"Dépenses ({ui.devise()})", format="%.0f"),
                       "incident": st.column_config.CheckboxColumn("Incident"), "auteur": "Saisi par"})
    coches = choix.loc[choix["valider"], "id"].astype(int).tolist()
    if st.button(f"Valider les {len(coches)} rapport(s) cochés" if coches else "Valider les rapports cochés",
                 type="primary", disabled=not coches):
        _decider(coches, "Validé")
        st.session_state["validation_msg"] = f"{len(coches)} rapport(s) validé(s)."
        st.rerun()

    st.subheader("Détail")
    for _, x in r.iterrows():
        with st.expander(f"{x['date_rapport']:%d/%m/%Y} · {x['chantier']} · {x['activite']} · {x['auteur']}"):
            g, d = st.columns([1.3, 1])
            with g:
                st.markdown(f"**Quantité :** {x['quantite'] if x['quantite'] == x['quantite'] else '—'} {x['unite']}  \n"
                            f"**Effectif :** {x['effectif'] if x['effectif'] == x['effectif'] else '—'}  \n"
                            f"**Dépenses :** {calculs.fmt_montant(x['depenses'], ui.devise())}  \n"
                            f"**Matériaux :** {x['materiaux'] or '—'}  \n"
                            f"**Observations :** {x['commentaire'] or '—'}")
                if x["incident"]:
                    st.error(f"Incident : {x['incident_desc']}")
            with d:
                if x["a_photo"]:
                    photo = db.lire("select photo from rapports where id = :i", i=int(x["id"]))["photo"].iloc[0]
                    st.image(bytes(photo), width="stretch")
                else:
                    st.caption("Pas de photo.")
            b1, b2 = st.columns([1, 2])
            if b1.button("Valider", icon=":material/check:", key=f"val_{x['id']}"):
                _decider([int(x["id"])], "Validé")
                st.session_state["validation_msg"] = "Rapport validé."
                st.rerun()
            motif = b2.text_input("Motif du rejet", key=f"motif_{x['id']}", placeholder="Quantité incohérente…")
            if b2.button("Rejeter", icon=":material/close:", key=f"rej_{x['id']}", disabled=not motif.strip()):
                _decider([int(x["id"])], "Rejeté", motif.strip())
                st.session_state["validation_msg"] = "Rapport rejeté : son auteur verra le motif."
                st.rerun()
