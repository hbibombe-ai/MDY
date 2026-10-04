"""Base de données de l'application de suivi des activités.

En local : un fichier SQLite (donnees/suivi_chantiers.db), créé automatiquement.
En production : une base PostgreSQL, indiquée dans les secrets Streamlit
([database] url = "postgresql://...") ou dans la variable d'environnement DATABASE_URL.
Sur Streamlit Community Cloud, le disque est effacé à chaque redémarrage : il FAUT
une base PostgreSQL (Neon, Supabase…) pour conserver les données.
"""
from __future__ import annotations

import datetime as dt
import os
from typing import Any

import pandas as pd
import sqlalchemy as sa
import streamlit as st

DOSSIER = os.path.dirname(os.path.abspath(__file__))

meta = sa.MetaData()


def maintenant() -> dt.datetime:
    return dt.datetime.now().replace(microsecond=0)


utilisateurs = sa.Table(
    "utilisateurs", meta,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("identifiant", sa.String(50), unique=True, nullable=False),
    sa.Column("nom", sa.String(120), nullable=False),
    sa.Column("telephone", sa.String(30)),
    sa.Column("role", sa.String(20), nullable=False),
    sa.Column("mdp_hash", sa.String(256), nullable=False),
    sa.Column("doit_changer_mdp", sa.Boolean, nullable=False, default=True),
    sa.Column("actif", sa.Boolean, nullable=False, default=True),
    sa.Column("echecs", sa.Integer, nullable=False, default=0),
    sa.Column("bloque_jusqua", sa.DateTime),
    sa.Column("derniere_connexion", sa.DateTime),
    sa.Column("version_session", sa.Integer, nullable=False, default=0),
    sa.Column("demo", sa.Boolean, nullable=False, default=False),
    sa.Column("cree_le", sa.DateTime, default=maintenant),
)

parametres = sa.Table(
    "parametres", meta,
    sa.Column("cle", sa.String(50), primary_key=True),
    sa.Column("valeur", sa.Text),
)

chantiers = sa.Table(
    "chantiers", meta,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("nom", sa.String(150), nullable=False),
    sa.Column("client", sa.String(150)),
    sa.Column("type_activite", sa.String(60)),
    sa.Column("adresse", sa.String(250)),
    sa.Column("lat", sa.Float),
    sa.Column("lon", sa.Float),
    sa.Column("date_debut", sa.Date),
    sa.Column("date_fin_prevue", sa.Date),
    sa.Column("budget", sa.Float),
    sa.Column("statut", sa.String(30), nullable=False, default="Planifié"),
    sa.Column("description", sa.Text),
    sa.Column("demo", sa.Boolean, nullable=False, default=False),
    sa.Column("cree_par", sa.Integer, sa.ForeignKey("utilisateurs.id")),
    sa.Column("cree_le", sa.DateTime, default=maintenant),
)

affectations = sa.Table(
    "affectations", meta,
    sa.Column("utilisateur_id", sa.Integer, sa.ForeignKey("utilisateurs.id", ondelete="CASCADE"), primary_key=True),
    sa.Column("chantier_id", sa.Integer, sa.ForeignKey("chantiers.id", ondelete="CASCADE"), primary_key=True),
)

activites = sa.Table(
    "activites", meta,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("chantier_id", sa.Integer, sa.ForeignKey("chantiers.id", ondelete="CASCADE"), nullable=False),
    sa.Column("titre", sa.String(200), nullable=False),
    sa.Column("description", sa.Text),
    sa.Column("unite", sa.String(30)),
    sa.Column("quantite_prevue", sa.Float),
    sa.Column("date_debut", sa.Date),
    sa.Column("date_fin_prevue", sa.Date),
    sa.Column("lat", sa.Float),
    sa.Column("lon", sa.Float),
    sa.Column("statut", sa.String(30), nullable=False, default="À réaliser"),
    sa.Column("responsable_id", sa.Integer, sa.ForeignKey("utilisateurs.id")),
    sa.Column("cree_par", sa.Integer, sa.ForeignKey("utilisateurs.id")),
    sa.Column("cree_le", sa.DateTime, default=maintenant),
)

rapports = sa.Table(
    "rapports", meta,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("chantier_id", sa.Integer, sa.ForeignKey("chantiers.id", ondelete="CASCADE"), nullable=False),
    sa.Column("activite_id", sa.Integer, sa.ForeignKey("activites.id", ondelete="SET NULL")),
    sa.Column("date_rapport", sa.Date, nullable=False),
    sa.Column("quantite", sa.Float),
    sa.Column("effectif", sa.Integer),
    sa.Column("depenses", sa.Float),
    sa.Column("materiaux", sa.Text),
    sa.Column("incident", sa.Boolean, nullable=False, default=False),
    sa.Column("incident_desc", sa.Text),
    sa.Column("commentaire", sa.Text),
    sa.Column("lat", sa.Float),
    sa.Column("lon", sa.Float),
    sa.Column("photo", sa.LargeBinary),
    sa.Column("statut_validation", sa.String(20), nullable=False, default="En attente"),
    sa.Column("valide_par", sa.Integer, sa.ForeignKey("utilisateurs.id")),
    sa.Column("valide_le", sa.DateTime),
    sa.Column("motif_rejet", sa.Text),
    sa.Column("cree_par", sa.Integer, sa.ForeignKey("utilisateurs.id")),
    sa.Column("cree_le", sa.DateTime, default=maintenant),
)

# Listes de valeurs ------------------------------------------------------------
STATUTS_CHANTIER = ["Planifié", "En cours", "Suspendu", "Terminé"]
STATUTS_ACTIVITE = ["À réaliser", "En cours", "Réalisée"]
TYPES_ACTIVITE = ["Construction", "Rénovation", "Voirie et réseaux", "Forage et adduction d'eau",
                  "Électricité", "Fourniture et logistique", "Autre"]
UNITES = ["m²", "m³", "m", "ml", "kg", "t", "unité", "lot", "jour", "%"]


def url_base() -> str:
    url = None
    try:
        url = st.secrets["database"]["url"]
    except Exception:  # noqa: BLE001 — pas de secrets en local
        url = os.environ.get("DATABASE_URL")
    if not url:
        os.makedirs(os.path.join(DOSSIER, "donnees"), exist_ok=True)
        return "sqlite:///" + os.path.join(DOSSIER, "donnees", "suivi_chantiers.db")
    if url.startswith("postgres://"):
        url = "postgresql+psycopg2://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg2://" + url[len("postgresql://"):]
    return url


@st.cache_resource(show_spinner=False)
def moteur() -> sa.Engine:
    url = url_base()
    kw = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kw["connect_args"] = {"check_same_thread": False}
    eng = sa.create_engine(url, **kw)
    if url.startswith("sqlite"):
        @sa.event.listens_for(eng, "connect")
        def _fk(dbapi_con, _):  # active les clés étrangères (suppressions en cascade)
            dbapi_con.execute("PRAGMA foreign_keys=ON")
    meta.create_all(eng)
    return eng


def est_sqlite() -> bool:
    return moteur().url.get_backend_name() == "sqlite"


def lire(requete: Any, **params) -> pd.DataFrame:
    with moteur().connect() as c:
        if isinstance(requete, str):
            requete = sa.text(requete)
        return pd.read_sql(requete, c, params=params or None)


def executer(instruction, valeurs: dict | list | None = None):
    with moteur().begin() as c:
        return c.execute(instruction, valeurs) if valeurs is not None else c.execute(instruction)


def inserer(table: sa.Table, **valeurs) -> int:
    with moteur().begin() as c:
        res = c.execute(table.insert().values(**valeurs))
        return int(res.inserted_primary_key[0])


def maj(table: sa.Table, ident: int, **valeurs) -> None:
    executer(table.update().where(table.c.id == ident).values(**valeurs))
