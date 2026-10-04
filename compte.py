"""Mon compte : informations et changement de mot de passe."""
from __future__ import annotations

import streamlit as st

import auth
import db
import ui


def page() -> None:
    ui.en_tete("Mon compte")
    u = auth.utilisateur()
    st.markdown(f"**{u['nom']}** · identifiant `{u['identifiant']}` · {auth.ROLES.get(u['role'], u['role'])}")
    st.caption(auth.DESCRIPTION_ROLES.get(u["role"], ""))
    st.subheader("Changer mon mot de passe")
    with st.form("form_changer_mdp", clear_on_submit=True):
        actuel = st.text_input("Mot de passe actuel", type="password", autocomplete="current-password")
        n1 = st.text_input("Nouveau mot de passe", type="password", autocomplete="new-password")
        n2 = st.text_input("Confirmer le nouveau mot de passe", type="password", autocomplete="new-password")
        ok = st.form_submit_button("Changer le mot de passe", type="primary")
    if ok:
        stocke = db.lire("select mdp_hash from utilisateurs where id = :i", i=u["id"])["mdp_hash"].iloc[0]
        if not auth.verifier(actuel, stocke):
            st.error("Le mot de passe actuel est incorrect.")
        elif err := (auth.probleme_mdp(n1) or (None if n1 == n2 else "Les deux mots de passe ne correspondent pas.")):
            st.error(err)
        else:
            auth.changer_mdp(u["id"], n1)
            st.success("Mot de passe changé.")
