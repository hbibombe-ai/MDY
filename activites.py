"""Activités (tâches) de chaque chantier : à réaliser, en cours, réalisées."""
from __future__ import annotations

import datetime as dt

import streamlit as st

import auth
import calculs
import db
import ui


def _responsables(chantier_id: int) -> dict[int, str]:
    df = db.lire("select u.id, u.nom from utilisateurs u join affectations a on a.utilisateur_id = u.id "
                 "where a.chantier_id = :c and u.actif = :t order by u.nom", c=chantier_id, t=True)
    return {int(r.id): r.nom for r in df.itertuples()}


def _formulaire(cle: str, chantier_id: int, a: dict | None = None) -> dict | None:
    a = a or {}
    resp = _responsables(chantier_id)
    options = [None] + list(resp)
    with st.form(cle):
        titre = st.text_input("Activité *", value=a.get("titre") or "", placeholder="Ex. : coulage dalle niveau 1")
        c1, c2, c3 = st.columns(3)
        unites = db.UNITES
        unite = c1.selectbox("Unité", unites, index=unites.index(a["unite"]) if a.get("unite") in unites else 0)
        qte = c2.number_input("Quantité prévue", min_value=0.0, value=float(a.get("quantite_prevue") or 0.0), step=1.0,
                              help="Laisser 0 si l'activité ne se mesure pas : l'avancement suivra alors son statut.")
        statut = c3.selectbox("Statut", db.STATUTS_ACTIVITE,
                              index=db.STATUTS_ACTIVITE.index(a["statut"]) if a.get("statut") in db.STATUTS_ACTIVITE else 0)
        d1, d2, d3 = st.columns(3)
        debut = d1.date_input("Début prévu", value=a.get("date_debut") or dt.date.today(), format="DD/MM/YYYY")
        fin = d2.date_input("Fin prévue", value=a.get("date_fin_prevue") or dt.date.today() + dt.timedelta(days=14),
                            format="DD/MM/YYYY")
        r_id = d3.selectbox("Responsable", options,
                            index=options.index(a.get("responsable_id")) if a.get("responsable_id") in options else 0,
                            format_func=lambda i: "—" if i is None else resp[i])
        coords = ui.champ_coordonnees(f"{cle}_gps", (a.get("lat"), a.get("lon")) if a.get("lat") == a.get("lat") and a.get("lat") is not None else None,
                                      aide="Facultatif : à renseigner si l'activité se situe à un endroit précis "
                                           "(tronçon de route, forage…). Sinon, elle est placée sur le chantier.")
        desc = st.text_area("Description", value=a.get("description") or "", height=70)
        ok = st.form_submit_button("Enregistrer", type="primary")
    if not ok:
        return None
    if not titre.strip():
        st.error("Le nom de l'activité est obligatoire.")
        return None
    return {"titre": titre.strip(), "unite": unite, "quantite_prevue": qte or None, "statut": statut,
            "date_debut": debut, "date_fin_prevue": fin, "responsable_id": r_id,
            "lat": coords[0] if coords else None, "lon": coords[1] if coords else None, "description": desc.strip()}


def page() -> None:
    ui.en_tete("Activités", "Tâches prévues et réalisées sur chaque chantier")
    ch = calculs.chantiers()
    if ch.empty:
        st.info("Aucun chantier accessible.")
        return
    ids = ch["id"].tolist()
    defaut = st.session_state.get("chantier_choisi")
    cid = st.selectbox("Chantier", ids, index=ids.index(defaut) if defaut in ids else 0,
                       format_func=lambda i: ch.loc[ch["id"] == i, "nom"].iloc[0])
    st.session_state["chantier_choisi"] = cid
    act = calculs.activites([cid])
    noms = calculs.noms_utilisateurs()
    gerer = auth.peut("gerer_activites") and (auth.peut("creer_chantier") or cid in (auth.chantiers_accessibles() or []))

    if act.empty:
        st.info("Aucune activité pour ce chantier.")
    else:
        n = act["statut"].value_counts()
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Avancement du chantier", f"{act['avancement'].mean():.0%}")
        k2.metric("À réaliser", int(n.get("À réaliser", 0)))
        k3.metric("En cours", int(n.get("En cours", 0)))
        k4.metric("Réalisées", int(n.get("Réalisée", 0)))
        act["responsable"] = act["responsable_id"].map(noms)
        act["realise_txt"] = act.apply(lambda r: f"{r['realise']:g} / {r['quantite_prevue']:g} {r['unite'] or ''}"
                                       if r["quantite_prevue"] == r["quantite_prevue"] and r["quantite_prevue"] else "—", axis=1)
        st.dataframe(ui.en_pct(act, "avancement"), hide_index=True,
                     column_order=["titre", "statut", "avancement", "realise_txt", "date_debut", "date_fin_prevue", "responsable"],
                     column_config={"titre": st.column_config.TextColumn("Activité", width="large"), "statut": "Statut",
                                    "avancement": ui.colonne_pct("Avancement"),
                                    "realise_txt": st.column_config.TextColumn("Réalisé / prévu",
                                                                               help="Quantités des rapports validés."),
                                    "date_debut": st.column_config.DateColumn("Début", format="DD/MM/YYYY"),
                                    "date_fin_prevue": st.column_config.DateColumn("Fin prévue", format="DD/MM/YYYY"),
                                    "responsable": "Responsable"})

    if not gerer:
        return
    u = auth.utilisateur()
    with st.expander("Nouvelle activité", icon=":material/add_task:", expanded=act.empty):
        v = _formulaire(f"form_nouvelle_activite_{cid}", cid)
        if v:
            db.inserer(db.activites, chantier_id=cid, cree_par=u["id"], **v)
            st.success(f"Activité « {v['titre']} » ajoutée.")
            st.rerun()
    if not act.empty:
        with st.expander("Modifier ou supprimer une activité", icon=":material/edit:"):
            aid = st.selectbox("Activité", act["id"].tolist(),
                               format_func=lambda i: act.loc[act["id"] == i, "titre"].iloc[0], key=f"choix_act_{cid}")
            a = act[act["id"] == aid].iloc[0].to_dict()
            v = _formulaire(f"form_modif_activite_{aid}", cid, a)
            if v:
                db.maj(db.activites, aid, **v)
                st.success("Activité mise à jour.")
                st.rerun()
            if st.checkbox("Supprimer cette activité (ses rapports sont conservés)", key=f"conf_suppr_act_{aid}"):
                if st.button("Supprimer", key=f"suppr_act_{aid}"):
                    db.executer(db.activites.delete().where(db.activites.c.id == aid))
                    st.rerun()
