"""Gestion des comptes : création des identifiants, rôles, affectations, réinitialisation."""
from __future__ import annotations

import re

import streamlit as st

import auth
import calculs
import db
import demo
import ui


def _carte_identifiants(identifiant: str, mdp: str, nom: str) -> None:
    st.success(f"Identifiants de **{nom}** — à lui transmettre personnellement :")
    st.code(f"Adresse : (lien de l'application)\nIdentifiant : {identifiant}\nMot de passe provisoire : {mdp}",
            language=None)
    st.caption("Ce mot de passe ne sera plus affiché. L'usager devra en choisir un nouveau à sa première connexion.")


def page() -> None:
    ui.en_tete("Utilisateurs", "Créer les identifiants, attribuer les rôles et les chantiers")
    if info := st.session_state.pop("identifiants_crees", None):
        _carte_identifiants(*info)

    ch = calculs.chantiers(None)
    noms_ch = dict(zip(ch["id"], ch["nom"]))
    with st.expander("Nouvel utilisateur", icon=":material/person_add:", expanded=False):
        with st.form("form_nouvel_utilisateur", clear_on_submit=True):
            a, b = st.columns(2)
            nom = a.text_input("Nom complet *")
            ident = b.text_input("Identifiant de connexion *", placeholder="ex. j.mukendi",
                                 help="Lettres minuscules, chiffres, point, tiret ou soulignement.")
            tel = a.text_input("Téléphone")
            role = b.selectbox("Rôle", list(auth.ROLES), format_func=lambda r: auth.ROLES[r], index=2)
            st.caption(" · ".join(f"**{auth.ROLES[r]}** : {d}" for r, d in auth.DESCRIPTION_ROLES.items()))
            chantiers_ids = st.multiselect("Chantiers affectés", list(noms_ch), format_func=lambda i: noms_ch[i],
                                           help="Utile pour les conducteurs et les chefs de chantier : ils ne voient "
                                                "que ces chantiers.")
            ok = st.form_submit_button("Créer le compte", type="primary")
        if ok:
            ident_n = ident.strip().lower()
            if not nom.strip() or not ident_n:
                st.error("Le nom et l'identifiant sont obligatoires.")
            elif not re.fullmatch(r"[a-z0-9._-]{3,50}", ident_n):
                st.error("Identifiant invalide : 3 à 50 caractères, lettres minuscules, chiffres, . _ ou -.")
            elif not db.lire("select id from utilisateurs where identifiant = :i", i=ident_n).empty:
                st.error("Cet identifiant existe déjà.")
            else:
                mdp = auth.creer_utilisateur(ident_n, nom, role, tel, chantiers_ids)
                st.session_state["identifiants_crees"] = (ident_n, mdp, nom.strip())
                st.rerun()

    us = db.lire("select id, identifiant, nom, telephone, role, actif, derniere_connexion, demo from utilisateurs "
                 "order by actif desc, nom")
    aff = db.lire("select utilisateur_id, chantier_id from affectations")
    us["chantiers"] = us["id"].map(lambda i: ", ".join(noms_ch.get(c, "?") for c in
                                                      aff.loc[aff["utilisateur_id"] == i, "chantier_id"]))
    us["role_txt"] = us["role"].map(auth.ROLES)
    st.dataframe(us, hide_index=True,
                 column_order=["nom", "identifiant", "role_txt", "chantiers", "telephone", "actif", "derniere_connexion"],
                 column_config={"nom": "Nom", "identifiant": "Identifiant", "role_txt": "Rôle",
                                "chantiers": st.column_config.TextColumn("Chantiers affectés", width="large"),
                                "telephone": "Téléphone", "actif": st.column_config.CheckboxColumn("Actif"),
                                "derniere_connexion": st.column_config.DatetimeColumn("Dernière connexion",
                                                                                      format="DD/MM/YYYY HH:mm")})

    st.subheader("Modifier un compte")
    moi = auth.utilisateur()["id"]
    uid = st.selectbox("Utilisateur", us["id"].tolist(),
                       format_func=lambda i: f"{us.loc[us['id'] == i, 'nom'].iloc[0]} ({us.loc[us['id'] == i, 'identifiant'].iloc[0]})")
    x = us[us["id"] == uid].iloc[0]
    actuels = aff.loc[aff["utilisateur_id"] == uid, "chantier_id"].astype(int).tolist()
    with st.form(f"form_modif_utilisateur_{uid}"):
        a, b = st.columns(2)
        nom = a.text_input("Nom complet", value=x["nom"])
        tel = b.text_input("Téléphone", value=x["telephone"] or "")
        roles = list(auth.ROLES)
        role = a.selectbox("Rôle", roles, index=roles.index(x["role"]), format_func=lambda r: auth.ROLES[r],
                           disabled=uid == moi)
        actif = b.toggle("Compte actif", value=bool(x["actif"]), disabled=uid == moi,
                         help="Un compte désactivé ne peut plus se connecter ; son historique est conservé.")
        chantiers_ids = st.multiselect("Chantiers affectés", list(noms_ch), default=[c for c in actuels if c in noms_ch],
                                       format_func=lambda i: noms_ch[i])
        ok = st.form_submit_button("Enregistrer les modifications", type="primary")
    if ok:
        db.maj(db.utilisateurs, uid, nom=nom.strip() or x["nom"], telephone=tel.strip(),
               role=x["role"] if uid == moi else role, actif=True if uid == moi else actif)
        auth.definir_affectations(uid, chantiers_ids)
        st.success("Compte mis à jour.")
        st.rerun()
    if st.button("Réinitialiser le mot de passe", icon=":material/lock_reset:", disabled=uid == moi,
                 help="Pour votre propre compte, utilisez la page « Mon compte »."):
        mdp = auth.reinitialiser_mdp(uid)
        st.session_state["identifiants_crees"] = (x["identifiant"], mdp, x["nom"])
        st.rerun()

    st.divider()
    st.subheader("Données de démonstration")
    st.caption("Pour présenter l'application : cinq chantiers fictifs à Kinshasa, avec activités, rapports et "
               "comptes de test. Elles se suppriment en un clic avant la mise en service réelle.")
    d1, d2 = st.columns(2)
    if d1.button("Charger les données de démonstration", disabled=demo.est_chargee()):
        comptes = demo.charger(moi)
        st.session_state["demo_comptes"] = comptes
        st.rerun()
    if d2.button("Supprimer les données de démonstration", disabled=not demo.est_chargee()):
        demo.supprimer()
        st.session_state.pop("demo_comptes", None)
        st.rerun()
    if comptes := st.session_state.get("demo_comptes"):
        st.info("Comptes de test (mot de passe identique pour tous : **" + demo.MDP_DEMO + "**) : "
                + ", ".join(f"`{i}` ({auth.ROLES[r]})" for i, r in comptes))
