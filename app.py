"""Application de suivi des activités réalisées — chantiers et autres activités.

Lancement en local :  streamlit run app.py
"""
from __future__ import annotations

import streamlit as st

import auth
import db
import ui

st.set_page_config(page_title=f"{ui.nom_entreprise()} · Suivi des chantiers", page_icon=ui.ICONE, layout="wide",
                   initial_sidebar_state="auto")
ui.appliquer_style()

db.moteur()
auth.assurer_admin_initial()


# ------------------------------------------------------------------ connexion
def page_connexion() -> None:
    ui.appliquer_style(connexion=True)
    _, centre, _ = st.columns([1, 1.2, 1])
    with centre:
        st.write("")
        st.image(ui.LOGO_CLAIR, width=300)
        st.markdown("Connectez-vous pour saisir ou suivre l'avancement des chantiers.")
        if auth.admin_par_defaut_actif():
            st.warning(f"Première installation : connectez-vous avec l'identifiant **admin** et le mot de passe "
                       f"**{auth.MDP_INITIAL_PAR_DEFAUT}**, puis choisissez immédiatement un nouveau mot de passe.")
        with st.form("connexion"):
            ident = st.text_input("Identifiant", autocomplete="username")
            mdp = st.text_input("Mot de passe", type="password", autocomplete="current-password")
            ok = st.form_submit_button("Se connecter", type="primary", width="stretch")
        if ok:
            u, err = auth.connecter(ident, mdp)
            if err:
                st.error(err)
            else:
                auth.ouvrir_session(u)
                st.rerun()
        st.caption("Mot de passe oublié ? Demandez à l'administrateur de le réinitialiser.")


def page_changement_obligatoire() -> None:
    ui.appliquer_style(connexion=True)
    u = auth.utilisateur()
    _, centre, _ = st.columns([1, 1.2, 1])
    with centre:
        st.image(ui.LOGO_CLAIR, width=260)
        st.markdown(f"## Bienvenue, {u['nom']}")
        st.info("Pour votre première connexion, choisissez un mot de passe personnel "
                "(8 caractères au moins, avec au moins une lettre et un chiffre).")
        with st.form("nouveau_mdp"):
            n1 = st.text_input("Nouveau mot de passe", type="password", autocomplete="new-password")
            n2 = st.text_input("Confirmer le mot de passe", type="password", autocomplete="new-password")
            ok = st.form_submit_button("Enregistrer", type="primary", width="stretch")
        if ok:
            err = auth.probleme_mdp(n1) or (None if n1 == n2 else "Les deux mots de passe ne correspondent pas.")
            if err:
                st.error(err)
            else:
                auth.changer_mdp(u["id"], n1)
                st.session_state["utilisateur"] = {**u, "doit_changer_mdp": False}
                st.rerun()
        if st.button("Se déconnecter"):
            auth.deconnecter()
            st.rerun()


# session conservée après actualisation de la page (jeton signé dans l'adresse)
if not auth.utilisateur() and (j := st.query_params.get("s")):
    if u := auth.depuis_jeton(j):
        st.session_state["utilisateur"] = u
        st.session_state["jeton"] = j
    else:
        st.query_params.clear()

utilisateur = auth.utilisateur()
if utilisateur and st.session_state.get("jeton"):
    st.query_params["s"] = st.session_state["jeton"]
if not utilisateur:
    page_connexion()
    st.stop()
if utilisateur.get("doit_changer_mdp"):
    page_changement_obligatoire()
    st.stop()

# ------------------------------------------------------------------ navigation
from vues import (activites, carte, chantiers, compte, historique, rapport,  # noqa: E402
                  tableau_de_bord, utilisateurs, validation)

pages = {
    "Suivi": [
        st.Page(tableau_de_bord.page, title="Tableau de bord", icon=":material/dashboard:", url_path="tableau-de-bord",
                default=True),
        st.Page(carte.page, title="Carte", icon=":material/map:", url_path="carte"),
        st.Page(chantiers.page, title="Chantiers", icon=":material/apartment:", url_path="chantiers"),
        st.Page(activites.page, title="Activités", icon=":material/checklist:", url_path="activites"),
        st.Page(historique.page, title="Historique des rapports", icon=":material/history:", url_path="historique"),
    ],
}
saisie = []
if auth.peut("saisir_rapport"):
    saisie.append(st.Page(rapport.page, title="Rapport journalier", icon=":material/edit_note:", url_path="rapport"))
if auth.peut("valider_rapport"):
    n = validation.nombre_en_attente()
    saisie.append(st.Page(validation.page, title=f"Validation ({n})" if n else "Validation", icon=":material/fact_check:",
                          url_path="validation"))
if saisie:
    pages["Saisie"] = saisie
admin = [st.Page(utilisateurs.page, title="Utilisateurs", icon=":material/group:", url_path="utilisateurs")] \
    if auth.peut("gerer_utilisateurs") else []
pages["Compte"] = admin + [st.Page(compte.page, title="Mon compte", icon=":material/key:", url_path="compte")]

st.logo(ui.LOGO_SOMBRE, size="large", icon_image=ui.ICONE)
with st.sidebar:
    st.markdown(f"**{utilisateur['nom']}**  \n{auth.ROLES.get(utilisateur['role'], utilisateur['role'])}")
    if st.button("Se déconnecter", width="stretch"):
        auth.deconnecter()
        st.rerun()

st.navigation(pages).run()
