"""Tableau de bord de la direction : où en est chaque chantier, aujourd'hui."""
from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

import calculs
import ui


def page() -> None:
    auj = dt.date.today()
    ui.en_tete("Tableau de bord", f"Situation au {auj:%d/%m/%Y} · rapports validés uniquement")
    s = calculs.synthese(auj)
    if s.empty:
        st.info("Aucun chantier pour le moment. L'administrateur peut en créer dans la page **Chantiers**, "
                "ou charger des données de démonstration dans la page **Utilisateurs**.")
        return
    dev = ui.devise()
    actifs = s[s["etat"].isin(["Dans les délais", "En retard"])]
    rap = calculs.rapports(avec_photo=False)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Chantiers en cours", len(actifs), help="Chantiers démarrés, ni terminés ni suspendus.")
    c2.metric("En retard", int((s["etat"] == "En retard").sum()),
              help="Avancement réel inférieur de plus de 15 points à l'avancement attendu à cette date, "
                   "ou date de fin dépassée.")
    c3.metric("Avancement moyen", f"{actifs['avancement'].mean():.0%}" if not actifs.empty else "—")
    budget = s["budget"].fillna(0).sum()
    c4.metric("Dépenses / budget", f"{s['depenses'].sum() / budget:.0%}" if budget else "—",
              help=f"{calculs.fmt_montant(s['depenses'].sum(), dev)} dépensés sur "
                   f"{calculs.fmt_montant(budget, dev)} de budget total.")
    c5.metric("Rapports à valider", int(s["en_attente"].sum()))

    al = calculs.alertes(s, auj)
    if al:
        st.subheader("Points d'attention")
        for niveau, msg in sorted(al, key=lambda x: x[0] != "error"):
            (st.error if niveau == "error" else st.warning)(msg)

    st.subheader("Avancement par chantier")
    vue = ui.en_pct(s.sort_values(["etat", "avancement"]), "avancement", "attendu", "taux_budget")
    vue["budget_txt"] = vue.apply(lambda r: f"{calculs.fmt_montant(r['depenses'], dev)} / "
                                            f"{calculs.fmt_montant(r['budget'], dev)}", axis=1)
    vue["activites_txt"] = vue.apply(lambda r: f"{r['realisees']} / {r['activites']}", axis=1)
    st.dataframe(
        vue, hide_index=True,
        column_order=["nom", "etat", "avancement", "attendu", "activites_txt", "taux_budget", "budget_txt",
                      "date_fin_prevue", "dernier_rapport", "en_attente", "incidents_7j"],
        column_config={
            "nom": st.column_config.TextColumn("Chantier", width="medium"),
            "etat": st.column_config.TextColumn("État"),
            "avancement": ui.colonne_pct("Avancement réel"),
            "attendu": ui.colonne_pct("Attendu à ce jour", "Part du délai écoulée entre le début et la fin prévue."),
            "activites_txt": st.column_config.TextColumn("Activités réalisées"),
            "taux_budget": ui.colonne_pct("Budget consommé"),
            "budget_txt": st.column_config.TextColumn(f"Dépenses / budget ({dev})"),
            "date_fin_prevue": st.column_config.DateColumn("Fin prévue", format="DD/MM/YYYY"),
            "dernier_rapport": st.column_config.DateColumn("Dernier rapport", format="DD/MM/YYYY"),
            "en_attente": st.column_config.NumberColumn("À valider"),
            "incidents_7j": st.column_config.NumberColumn("Incidents (7 j)"),
        })

    g, d = st.columns([1.2, 1])
    with g:
        st.subheader("Carte des chantiers")
        ui.carte(s, hauteur=380, cle="carte_tdb")
        ui.legende(calculs.COULEURS_ETAT)
    with d:
        st.subheader("Rapports reçus (30 derniers jours)")
        r = rap[rap["date_rapport"] >= auj - dt.timedelta(days=29)]
        if r.empty:
            st.caption("Aucun rapport sur la période.")
        else:
            jours = pd.date_range(auj - dt.timedelta(days=29), auj).date
            par_jour = (r.groupby(["date_rapport", "statut_validation"]).size().unstack(fill_value=0)
                        .reindex(jours, fill_value=0))
            par_jour.index = pd.to_datetime(par_jour.index)
            teintes = {"En attente": "#F2B705", "Rejeté": "#C2382B", "Validé": "#1D4F91"}
            st.bar_chart(par_jour, height=330, y_label="Rapports", x_label="",
                         color=[teintes.get(c, "#8A9199") for c in par_jour.columns])
