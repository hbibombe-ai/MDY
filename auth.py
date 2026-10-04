"""Comptes, mots de passe et droits d'accès.

Les mots de passe ne sont jamais stockés en clair : PBKDF2-SHA256 avec sel aléatoire
(bibliothèque standard Python). Cinq échecs de connexion bloquent le compte 15 minutes.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import os
import secrets
import string

import sqlalchemy as sa
import streamlit as st

import db

ROLES = {
    "admin": "Administrateur (direction)",
    "conducteur": "Conducteur de travaux",
    "chef": "Chef de chantier",
    "lecteur": "Lecteur (consultation seule)",
}
DESCRIPTION_ROLES = {
    "admin": "Voit tout, crée les chantiers et les comptes, valide les rapports.",
    "conducteur": "Gère les activités et valide les rapports de ses chantiers.",
    "chef": "Saisit les rapports journaliers de ses chantiers.",
    "lecteur": "Consulte le tableau de bord et la carte, sans rien modifier.",
}
ITERATIONS = 260_000
DUREE_SESSION = dt.timedelta(hours=12)
ECHECS_MAX = 5
DUREE_BLOCAGE = dt.timedelta(minutes=15)
MDP_INITIAL_PAR_DEFAUT = "changez-moi"


# ----------------------------------------------------------------- mots de passe
def hacher(mdp: str) -> str:
    sel = os.urandom(16)
    h = hashlib.pbkdf2_hmac("sha256", mdp.encode("utf-8"), sel, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${sel.hex()}${h.hex()}"


def verifier(mdp: str, stocke: str) -> bool:
    try:
        algo, it, sel, h = stocke.split("$")
        calc = hashlib.pbkdf2_hmac("sha256", mdp.encode("utf-8"), bytes.fromhex(sel), int(it))
        return algo == "pbkdf2_sha256" and hmac.compare_digest(calc.hex(), h)
    except (ValueError, TypeError):
        return False


def mdp_temporaire(longueur: int = 10) -> str:
    """Mot de passe lisible (sans 0/O ni 1/l/I), avec au moins une lettre et un chiffre."""
    lettres = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ"
    chiffres = "23456789"
    while True:
        m = "".join(secrets.choice(lettres + chiffres) for _ in range(longueur))
        if any(c in chiffres for c in m) and any(c in lettres for c in m):
            return m


def probleme_mdp(mdp: str) -> str | None:
    if len(mdp) < 8:
        return "Le mot de passe doit contenir au moins 8 caractères."
    if not any(c.isdigit() for c in mdp) or not any(c.isalpha() for c in mdp):
        return "Le mot de passe doit contenir au moins une lettre et un chiffre."
    if mdp.lower() in {MDP_INITIAL_PAR_DEFAUT, "password", "motdepasse", "12345678"}:
        return "Ce mot de passe est trop facile à deviner."
    return None


# ------------------------------------------------------------------- comptes
def secret(cle: str, defaut: str | None = None) -> str | None:
    try:
        return st.secrets[cle]
    except Exception:  # noqa: BLE001
        return os.environ.get(cle, defaut)


def assurer_admin_initial() -> None:
    """À la toute première ouverture, crée le compte administrateur."""
    u = db.utilisateurs
    with db.moteur().begin() as c:
        if c.execute(sa.select(sa.func.count()).select_from(u)).scalar():
            return
        ident = secret("ADMIN_IDENTIFIANT", "admin")
        mdp = secret("ADMIN_MDP_INITIAL") or MDP_INITIAL_PAR_DEFAUT
        c.execute(u.insert().values(identifiant=ident, nom="Administrateur", role="admin",
                                    mdp_hash=hacher(mdp), doit_changer_mdp=True, actif=True,
                                    echecs=0, demo=False))


def admin_par_defaut_actif() -> bool:
    """Vrai tant que le compte initial n'a pas changé son mot de passe par défaut."""
    if secret("ADMIN_MDP_INITIAL"):
        return False
    df = db.lire("select mdp_hash from utilisateurs where role = 'admin' and doit_changer_mdp = :v", v=True)
    return any(verifier(MDP_INITIAL_PAR_DEFAUT, h) for h in df["mdp_hash"])


def creer_utilisateur(identifiant: str, nom: str, role: str, telephone: str = "",
                      chantiers_ids: list[int] | None = None, demo: bool = False,
                      mdp: str | None = None, doit_changer: bool = True) -> str:
    """Crée le compte et renvoie le mot de passe temporaire à communiquer à l'usager."""
    mdp = mdp or mdp_temporaire()
    uid = db.inserer(db.utilisateurs, identifiant=identifiant.strip().lower(), nom=nom.strip(), role=role,
                     telephone=telephone.strip(), mdp_hash=hacher(mdp), doit_changer_mdp=doit_changer,
                     actif=True, echecs=0, demo=demo)
    definir_affectations(uid, chantiers_ids or [])
    return mdp


def definir_affectations(uid: int, chantiers_ids: list[int]) -> None:
    a = db.affectations
    with db.moteur().begin() as c:
        c.execute(a.delete().where(a.c.utilisateur_id == uid))
        if chantiers_ids:
            c.execute(a.insert(), [{"utilisateur_id": uid, "chantier_id": int(i)} for i in chantiers_ids])


def reinitialiser_mdp(uid: int) -> str:
    mdp = mdp_temporaire()
    db.maj(db.utilisateurs, uid, mdp_hash=hacher(mdp), doit_changer_mdp=True, echecs=0, bloque_jusqua=None)
    db.executer(sa.text("update utilisateurs set version_session = coalesce(version_session, 0) + 1 where id = :i"),
                {"i": uid})
    return mdp


def changer_mdp(uid: int, nouveau: str) -> None:
    db.maj(db.utilisateurs, uid, mdp_hash=hacher(nouveau), doit_changer_mdp=False)


def connecter(identifiant: str, mdp: str) -> tuple[dict | None, str | None]:
    u = db.utilisateurs
    with db.moteur().begin() as c:
        row = c.execute(sa.select(u).where(u.c.identifiant == identifiant.strip().lower())).mappings().first()
        if row is None:
            verifier(mdp, hacher("x"))  # même durée de calcul : ne révèle pas si le compte existe
            return None, "Identifiant ou mot de passe incorrect."
        if not row["actif"]:
            return None, "Ce compte est désactivé. Contactez l'administrateur."
        if row["bloque_jusqua"] and row["bloque_jusqua"] > db.maintenant():
            reste = int((row["bloque_jusqua"] - db.maintenant()).total_seconds() // 60) + 1
            return None, f"Trop de tentatives : compte bloqué encore {reste} minute(s)."
        if not verifier(mdp, row["mdp_hash"]):
            echecs = (row["echecs"] or 0) + 1
            vals = {"echecs": echecs}
            if echecs >= ECHECS_MAX:
                vals = {"echecs": 0, "bloque_jusqua": db.maintenant() + DUREE_BLOCAGE}
            c.execute(u.update().where(u.c.id == row["id"]).values(**vals))
            return None, "Identifiant ou mot de passe incorrect."
        c.execute(u.update().where(u.c.id == row["id"]).values(echecs=0, bloque_jusqua=None,
                                                               derniere_connexion=db.maintenant()))
        return {k: row[k] for k in ("id", "identifiant", "nom", "role", "doit_changer_mdp")}, None


# --------------------------------------------------------------------- session
# Le jeton de session, signé, est gardé dans l'adresse (?s=…) : actualiser la page ne déconnecte pas.
# Il expire après 12 h et devient invalide dès que l'usager se déconnecte.
def _cle_secrete() -> bytes:
    cle = secret("CLE_SECRETE")
    if cle:
        return cle.encode()
    p = db.parametres
    with db.moteur().begin() as c:
        v = c.execute(sa.select(p.c.valeur).where(p.c.cle == "cle_secrete")).scalar()
        if not v:
            v = secrets.token_hex(32)
            c.execute(p.insert().values(cle="cle_secrete", valeur=v))
    return v.encode()


def _signer(texte: str) -> str:
    return hmac.new(_cle_secrete(), texte.encode(), hashlib.sha256).hexdigest()[:32]


def jeton(uid: int) -> str:
    version = int(db.lire("select version_session from utilisateurs where id = :i", i=uid)["version_session"].iloc[0] or 0)
    exp = int((dt.datetime.now() + DUREE_SESSION).timestamp())
    corps = f"{uid}.{version}.{exp}"
    return f"{corps}.{_signer(corps)}"


def depuis_jeton(texte: str) -> dict | None:
    try:
        uid, version, exp, sig = texte.split(".")
        if not hmac.compare_digest(sig, _signer(f"{uid}.{version}.{exp}")) or int(exp) < dt.datetime.now().timestamp():
            return None
    except (ValueError, AttributeError):
        return None
    u = db.lire("select id, identifiant, nom, role, doit_changer_mdp, actif, version_session from utilisateurs "
                "where id = :i", i=int(uid))
    if u.empty or not bool(u["actif"].iloc[0]) or int(u["version_session"].iloc[0] or 0) != int(version):
        return None
    r = u.iloc[0]
    return {"id": int(r["id"]), "identifiant": r["identifiant"], "nom": r["nom"], "role": r["role"],
            "doit_changer_mdp": bool(r["doit_changer_mdp"])}


def utilisateur() -> dict | None:
    return st.session_state.get("utilisateur")


def ouvrir_session(u: dict) -> None:
    st.session_state["utilisateur"] = u
    st.session_state["jeton"] = jeton(u["id"])


def deconnecter() -> None:
    u = utilisateur()
    if u:  # invalide tous les jetons de cet usager
        db.executer(sa.text("update utilisateurs set version_session = coalesce(version_session, 0) + 1 where id = :i"),
                    {"i": u["id"]})
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.query_params.clear()


def peut(action: str) -> bool:
    """Droits par rôle."""
    role = (utilisateur() or {}).get("role")
    droits = {
        "gerer_utilisateurs": {"admin"},
        "creer_chantier": {"admin"},
        "modifier_chantier": {"admin", "conducteur"},
        "gerer_activites": {"admin", "conducteur"},
        "saisir_rapport": {"admin", "conducteur", "chef"},
        "valider_rapport": {"admin", "conducteur"},
        "voir_tout": {"admin", "lecteur"},
    }
    return role in droits.get(action, set())


def chantiers_accessibles() -> list[int] | None:
    """None = tous les chantiers ; sinon la liste des chantiers affectés à l'usager."""
    u = utilisateur()
    if not u or peut("voir_tout"):
        return None
    df = db.lire("select chantier_id from affectations where utilisateur_id = :u", u=u["id"])
    return df["chantier_id"].astype(int).tolist()
