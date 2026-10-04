"""Lecture des données (filtrées selon les droits de l'usager) et indicateurs de suivi."""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import sqlalchemy as sa

import auth
import db

# Couleurs de la carte et des pastilles (RGB)
COULEURS_ETAT = {
    "Dans les délais": (29, 79, 145),    # bleu des plans
    "En retard": (194, 56, 43),
    "Terminé": (47, 125, 79),
    "Planifié": (138, 145, 153),
    "Suspendu": (217, 130, 43),
}
COULEURS_ACTIVITE = {
    "À réaliser": (138, 145, 153),
    "En cours": (29, 79, 145),
    "Réalisée": (47, 125, 79),
}


def _filtre(table: sa.Table, colonne: str, ids: list[int] | None):
    q = sa.select(table)
    if ids is not None:
        q = q.where(getattr(table.c, colonne).in_(ids or [-1]))
    return q


def chantiers(ids: list[int] | None = "auto") -> pd.DataFrame:
    ids = auth.chantiers_accessibles() if ids == "auto" else ids
    df = db.lire(_filtre(db.chantiers, "id", ids).order_by(db.chantiers.c.nom))
    _dates(df, "date_debut", "date_fin_prevue")
    return df


def _dates(df: pd.DataFrame, *cols: str) -> None:
    """Colonnes de dates en objets date Python, valeurs manquantes en None (et non NaT)."""
    for c in cols:
        d = pd.to_datetime(df[c]).dt.date
        df[c] = d.astype(object).where(d.notna(), None)


def activites(ids: list[int] | None = "auto") -> pd.DataFrame:
    ids = auth.chantiers_accessibles() if ids == "auto" else ids
    df = db.lire(_filtre(db.activites, "chantier_id", ids).order_by(db.activites.c.chantier_id, db.activites.c.id))
    _dates(df, "date_debut", "date_fin_prevue")
    r = rapports(ids, avec_photo=False)
    val = r[r["statut_validation"] == "Validé"]
    cumul = val.groupby("activite_id")["quantite"].sum() if not val.empty else pd.Series(dtype=float)
    df["realise"] = df["id"].map(cumul).fillna(0.0)

    def prog(x):
        if x["statut"] == "Réalisée":
            return 1.0
        if x["quantite_prevue"] and x["quantite_prevue"] > 0:
            return float(min(1.0, x["realise"] / x["quantite_prevue"]))
        return 0.5 if x["statut"] == "En cours" else 0.0

    df["avancement"] = df.apply(prog, axis=1) if not df.empty else pd.Series(dtype=float)
    return df


def rapports(ids: list[int] | None = "auto", avec_photo: bool = False) -> pd.DataFrame:
    ids = auth.chantiers_accessibles() if ids == "auto" else ids
    t = db.rapports
    cols = [c for c in t.c if avec_photo or c.name != "photo"]
    q = sa.select(*cols)
    if not avec_photo:
        q = q.add_columns((t.c.photo.is_not(None)).label("a_photo"))
    if ids is not None:
        q = q.where(t.c.chantier_id.in_(ids or [-1]))
    df = db.lire(q.order_by(t.c.date_rapport.desc(), t.c.id.desc()))
    _dates(df, "date_rapport")
    return df


def noms_utilisateurs() -> dict[int, str]:
    df = db.lire("select id, nom from utilisateurs")
    return dict(zip(df["id"], df["nom"]))


def synthese(aujourdhui: dt.date | None = None) -> pd.DataFrame:
    """Une ligne par chantier : avancement réel et attendu, état, dépenses, alertes."""
    auj = aujourdhui or dt.date.today()
    ch = chantiers()
    if ch.empty:
        return ch
    act = activites()
    rap = rapports(avec_photo=False)
    val = rap[rap["statut_validation"] == "Validé"]
    lignes = []
    for _, c in ch.iterrows():
        a = act[act["chantier_id"] == c["id"]]
        r = rap[rap["chantier_id"] == c["id"]]
        v = val[val["chantier_id"] == c["id"]]
        if a.empty:
            av = 1.0 if c["statut"] == "Terminé" else 0.0
        else:
            av = float(a["avancement"].mean())
        attendu = np.nan
        if c["date_debut"] and c["date_fin_prevue"] and c["date_fin_prevue"] > c["date_debut"]:
            attendu = float(np.clip((auj - c["date_debut"]).days / (c["date_fin_prevue"] - c["date_debut"]).days, 0, 1))
        if c["statut"] == "Terminé":
            etat = "Terminé"
        elif c["statut"] == "Suspendu":
            etat = "Suspendu"
        elif c["statut"] == "Planifié" and (not c["date_debut"] or c["date_debut"] > auj):
            etat = "Planifié"
        elif c["date_fin_prevue"] and auj > c["date_fin_prevue"] and av < 1:
            etat = "En retard"
        elif not np.isnan(attendu) and av < attendu - 0.15:
            etat = "En retard"
        else:
            etat = "Dans les délais"
        dep = float(v["depenses"].fillna(0).sum())
        dernier = r["date_rapport"].max() if not r.empty else None
        lignes.append({
            "id": c["id"], "nom": c["nom"], "client": c["client"], "type_activite": c["type_activite"],
            "lat": c["lat"], "lon": c["lon"], "statut": c["statut"], "etat": etat,
            "avancement": av, "attendu": attendu,
            "activites": len(a), "realisees": int((a["statut"] == "Réalisée").sum()) if not a.empty else 0,
            "budget": c["budget"], "depenses": dep,
            "taux_budget": dep / c["budget"] if c["budget"] else np.nan,
            "date_fin_prevue": c["date_fin_prevue"], "dernier_rapport": dernier,
            "en_attente": int((r["statut_validation"] == "En attente").sum()),
            "incidents_7j": int(r[(r["incident"]) & (r["date_rapport"] >= auj - dt.timedelta(days=7))].shape[0]),
            "effectif_7j": float(v[v["date_rapport"] >= auj - dt.timedelta(days=7)]["effectif"].fillna(0).mean() or 0)
            if not v[v["date_rapport"] >= auj - dt.timedelta(days=7)].empty else 0.0,
        })
    return pd.DataFrame(lignes)


def alertes(s: pd.DataFrame, aujourdhui: dt.date | None = None) -> list[tuple[str, str]]:
    """(niveau, message) : 'error' bloquant, 'warning' à surveiller."""
    auj = aujourdhui or dt.date.today()
    out = []
    for _, c in s.iterrows():
        if c["etat"] == "En retard":
            msg = f"**{c['nom']}** est en retard : {c['avancement']:.0%} réalisé"
            if c["attendu"] == c["attendu"]:
                msg += f" pour {c['attendu']:.0%} attendu à ce jour"
            out.append(("error", msg + "."))
        if c["taux_budget"] == c["taux_budget"] and c["taux_budget"] >= 0.85:
            out.append(("error" if c["taux_budget"] >= 1 else "warning",
                        f"**{c['nom']}** a consommé {c['taux_budget']:.0%} de son budget pour {c['avancement']:.0%} d'avancement."))
        if c["etat"] in ("Dans les délais", "En retard"):
            if c["dernier_rapport"] is None or (auj - c["dernier_rapport"]).days > 2:
                depuis = "aucun rapport" if c["dernier_rapport"] is None else f"dernier rapport le {c['dernier_rapport']:%d/%m}"
                out.append(("warning", f"**{c['nom']}** : {depuis}."))
        if c["incidents_7j"]:
            out.append(("warning", f"**{c['nom']}** : {c['incidents_7j']} incident(s) signalé(s) ces 7 derniers jours."))
    return out


def fmt_montant(x, devise: str) -> str:
    if x is None or x != x:
        return "—"
    return f"{x:,.0f}".replace(",", " ") + f" {devise}"
