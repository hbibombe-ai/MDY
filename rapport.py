"""Saisie du rapport journalier par le chef de chantier."""
from __future__ import annotations

import datetime as dt

import streamlit as st

import auth
import calculs
import db
import ui


def page() -> None:
    ui.en_tete("Rapport journalier", "Ce qui a été réalisé aujourd'hui sur le chantier")
    u = auth.utilisateur()
    ch = calculs.chantiers()
    ch = ch[ch["statut"].isin(["En cours", "Planifié"])]
    if ch.empty:
        st.info("Aucun chantier en cours ne vous est affecté. Contactez votre conducteur de travaux ou l'administrateur.")
        return
    if st.session_state.pop("rapport_enregistre", False):
        st.success("Rapport enregistré. Merci !" + (" Il sera visible au tableau de bord après validation."
                                                     if not auth.peut("valider_rapport") else ""))

    ids = ch["id"].tolist()
    defaut = st.session_state.get("chantier_choisi")
    cid = st.selectbox("Chantier", ids, index=ids.index(defaut) if defaut in ids else 0,
                       format_func=lambda i: ch.loc[ch["id"] == i, "nom"].iloc[0])
    st.session_state["chantier_choisi"] = cid
    c = ch[ch["id"] == cid].iloc[0]
    act = calculs.activites([cid])
    act = act.sort_values("statut", key=lambda s: s.map({"En cours": 0, "À réaliser": 1, "Réalisée": 2}))
    options = [None] + act["id"].tolist()

    def libelle(i):
        if i is None:
            return "Activité générale du chantier (sans activité précise)"
        a = act[act["id"] == i].iloc[0]
        return f"{a['titre']} — {a['statut']} ({a['avancement']:.0%})"

    aid = st.selectbox("Activité réalisée", options, index=1 if len(options) > 1 else 0, format_func=libelle)
    a = act[act["id"] == aid].iloc[0] if aid is not None else None
    unite = (a["unite"] if a is not None and a["unite"] else "")

    with st.form("form_rapport", clear_on_submit=True):
        d1, d2, d3, d4 = st.columns(4)
        jour = d1.date_input("Date", value=dt.date.today(), max_value=dt.date.today(), format="DD/MM/YYYY")
        qte = d2.number_input(f"Quantité réalisée{f' ({unite})' if unite else ''}", min_value=0.0, step=1.0,
                              help=(f"Prévu au total : {a['quantite_prevue']:g} {unite} · déjà validé : {a['realise']:g} {unite}"
                                    if a is not None and a["quantite_prevue"] == a["quantite_prevue"] and a["quantite_prevue"]
                                    else None))
        effectif = d3.number_input("Effectif présent", min_value=0, step=1)
        dep = d4.number_input(f"Dépenses du jour ({ui.devise()})", min_value=0.0, step=10.0, format="%.0f")
        materiaux = st.text_area("Matériaux reçus ou utilisés", height=70,
                                 placeholder="Ex. : 40 sacs de ciment reçus ; 6 m³ de sable utilisés")
        commentaire = st.text_area("Travaux réalisés, observations", height=90)
        i1, i2 = st.columns([1, 3])
        incident = i1.checkbox("Incident ou problème")
        incident_desc = i2.text_input("Si oui, lequel ?", placeholder="Accident, panne, retard de livraison, pluie…")
        termine = st.checkbox("Cette activité est entièrement terminée", disabled=aid is None)
        coords = ui.champ_coordonnees("gps_rapport", (c["lat"], c["lon"]) if c["lat"] == c["lat"] and c["lat"] is not None else None,
                                      aide="Par défaut, la position du chantier. Pour une activité ailleurs, collez "
                                           "les coordonnées relevées sur place (Google Maps : appui long).")
        p1, p2 = st.columns(2)
        photo = p1.file_uploader("Photo (facultatif)", type=["jpg", "jpeg", "png", "webp"])
        prendre = p2.camera_input("Ou prendre une photo") if st.session_state.get("camera_active") else None
        envoye = st.form_submit_button("Envoyer le rapport", type="primary", width="stretch")
    if not st.session_state.get("camera_active"):
        st.button("Prendre une photo avec l'appareil", icon=":material/photo_camera:", on_click=lambda: st.session_state.update(camera_active=True))

    if envoye:
        if incident and not incident_desc.strip():
            st.error("Décrivez l'incident signalé.")
            return
        if aid is None and not commentaire.strip():
            st.error("Sans activité précise, décrivez les travaux réalisés.")
            return
        auto = auth.peut("valider_rapport")
        db.inserer(db.rapports, chantier_id=cid, activite_id=aid, date_rapport=jour, quantite=qte or None,
                   effectif=int(effectif) or None, depenses=dep or None, materiaux=materiaux.strip() or None,
                   incident=bool(incident), incident_desc=incident_desc.strip() or None,
                   commentaire=commentaire.strip() or None, lat=coords[0] if coords else None,
                   lon=coords[1] if coords else None, photo=ui.compresser_photo(prendre or photo),
                   statut_validation="Validé" if auto else "En attente",
                   valide_par=u["id"] if auto else None, valide_le=db.maintenant() if auto else None,
                   cree_par=u["id"])
        if aid is not None:
            nouveau = "Réalisée" if termine else ("En cours" if a["statut"] == "À réaliser" else a["statut"])
            if nouveau != a["statut"]:
                db.maj(db.activites, aid, statut=nouveau)
        st.session_state["rapport_enregistre"] = True
        st.session_state["camera_active"] = False
        st.rerun()

    mes = calculs.rapports([cid])
    mes = mes[mes["cree_par"] == u["id"]].head(10)
    if not mes.empty:
        st.subheader("Mes derniers rapports sur ce chantier")
        titres = dict(zip(act["id"], act["titre"]))
        mes["activite"] = mes["activite_id"].map(titres).fillna("Général")
        st.dataframe(mes, hide_index=True,
                     column_order=["date_rapport", "activite", "quantite", "effectif", "statut_validation", "motif_rejet"],
                     column_config={"date_rapport": st.column_config.DateColumn("Date", format="DD/MM/YYYY"),
                                    "activite": "Activité", "quantite": "Quantité", "effectif": "Effectif",
                                    "statut_validation": "Validation", "motif_rejet": "Motif de rejet"})
