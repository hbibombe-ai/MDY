"""Données de démonstration (fictives) : chantiers à Kinshasa, activités, rapports, comptes de test."""
from __future__ import annotations

import datetime as dt
import random

import sqlalchemy as sa

import auth
import db

MDP_DEMO = "Demo2026"

CHANTIERS = [
    # nom, client, type, adresse, lat, lon, début (j), fin (j), budget, statut
    ("Immeuble de bureaux R+4 — Gombe", "Société Kivu Invest", "Construction", "Boulevard du 30 Juin, Gombe",
     -4.3052, 15.3118, -120, 90, 850_000, "En cours"),
    ("Entrepôt logistique — Limete", "Trans-Congo Logistique", "Construction", "Quartier industriel, Limete",
     -4.3561, 15.3462, -60, 30, 95_000, "En cours"),
    ("Villa R+1 — Ngaliema", "Famille Lukusa", "Construction", "Ma Campagne, Ngaliema",
     -4.3398, 15.2551, -40, 100, 140_000, "En cours"),
    ("Forage et château d'eau — Masina", "ONG Eau pour Tous", "Forage et adduction d'eau", "Petro-Congo, Masina",
     -4.3872, 15.3948, 10, 70, 60_000, "Planifié"),
    ("Réhabilitation d'avenue — Lemba", "Commune de Lemba", "Voirie et réseaux", "Avenue de l'Université, Lemba",
     -4.4012, 15.3149, -150, -20, 210_000, "Terminé"),
]

ACTIVITES = {
    0: [("Fondations et radier", "m³", 320, "Réalisée", None), ("Poteaux et dalles R+1 à R+2", "m³", 260, "Réalisée", None),
        ("Dalles R+3 à R+4", "m³", 240, "En cours", None), ("Maçonnerie des façades", "m²", 1800, "En cours", None),
        ("Électricité et plomberie", "lot", 0, "À réaliser", None)],
    1: [("Terrassement de la plateforme", "m³", 1500, "Réalisée", None), ("Charpente métallique", "t", 48, "En cours", None),
        ("Couverture en tôles", "m²", 2400, "À réaliser", None), ("Dallage industriel", "m²", 2200, "À réaliser", None)],
    2: [("Fondations", "m³", 60, "Réalisée", None), ("Élévation des murs", "m²", 520, "En cours", None),
        ("Dalle de l'étage", "m³", 45, "À réaliser", None)],
    3: [("Forage à 80 m", "m", 80, "À réaliser", (-4.3880, 15.3941)), ("Château d'eau 20 m³", "unité", 1, "À réaliser", None),
        ("Bornes-fontaines", "unité", 4, "À réaliser", (-4.3858, 15.3962))],
    4: [("Tronçon 1 : décapage et couche de base", "ml", 600, "Réalisée", (-4.3990, 15.3135)),
        ("Tronçon 2 : décapage et couche de base", "ml", 650, "Réalisée", (-4.4030, 15.3162)),
        ("Revêtement en enrobé", "ml", 1250, "Réalisée", (-4.4012, 15.3149)),
        ("Caniveaux latéraux", "ml", 2500, "Réalisée", (-4.4022, 15.3140))],
}

COMPTES = [  # identifiant, nom, rôle, chantiers (indices)
    ("conducteur.demo", "Patrick Mbuyi", "conducteur", [0, 1, 2]),
    ("chef.demo1", "Grâce Kalala", "chef", [0, 1]),
    ("chef.demo2", "Jonas Ilunga", "chef", [2, 3]),
    ("lecteur.demo", "Service comptabilité", "lecteur", []),
]


def est_chargee() -> bool:
    return not db.lire("select id from chantiers where demo = :d", d=True).empty


def charger(admin_id: int) -> list[tuple[str, str]]:
    rnd = random.Random(2026)
    auj = dt.date.today()
    ch_ids = []
    for (nom, client, typ, adr, lat, lon, d0, d1, budget, statut) in CHANTIERS:
        ch_ids.append(db.inserer(db.chantiers, nom=nom, client=client, type_activite=typ, adresse=adr, lat=lat, lon=lon,
                                 date_debut=auj + dt.timedelta(days=d0), date_fin_prevue=auj + dt.timedelta(days=d1),
                                 budget=budget, statut=statut, description="Chantier fictif (démonstration).",
                                 demo=True, cree_par=admin_id))
    comptes, u_ids = [], {}
    for ident, nom, role, idx in COMPTES:
        existant = db.lire("select id from utilisateurs where identifiant = :i", i=ident)
        if not existant.empty:
            db.executer(db.utilisateurs.delete().where(db.utilisateurs.c.identifiant == ident))
        auth.creer_utilisateur(ident, nom, role, "", [ch_ids[i] for i in idx], demo=True, mdp=MDP_DEMO, doit_changer=False)
        u_ids[ident] = int(db.lire("select id from utilisateurs where identifiant = :i", i=ident)["id"].iloc[0])
        comptes.append((ident, role))
    conducteur = u_ids["conducteur.demo"]
    chefs = {0: u_ids["chef.demo1"], 1: u_ids["chef.demo1"], 2: u_ids["chef.demo2"], 3: u_ids["chef.demo2"], 4: conducteur}

    # rythme de dépenses par chantier (USD/jour) : l'entrepôt de Limete consomme vite son budget
    depense_jour = {0: 2600, 1: 3900, 2: 900, 4: 3000}
    lignes = []
    for i, cid in enumerate(ch_ids):
        d0, d1, statut = CHANTIERS[i][6], CHANTIERS[i][7], CHANTIERS[i][9]
        for k, (titre, unite, qte, st_act, pos) in enumerate(ACTIVITES[i]):
            n = len(ACTIVITES[i])
            a_debut = auj + dt.timedelta(days=d0 + (d1 - d0) * k // n)
            a_fin = auj + dt.timedelta(days=d0 + (d1 - d0) * (k + 1) // n)
            aid = db.inserer(db.activites, chantier_id=cid, titre=titre, unite=unite, quantite_prevue=qte or None,
                             statut=st_act, date_debut=a_debut, date_fin_prevue=a_fin, responsable_id=chefs[i],
                             lat=pos[0] if pos else None, lon=pos[1] if pos else None, cree_par=admin_id)
            if statut == "Planifié" or st_act == "À réaliser":
                continue
            # quantités réalisées : 100 % si réalisée ; sinon une part, faible pour l'entrepôt en retard
            part = 1.0 if st_act == "Réalisée" else {0: 0.55, 1: 0.25, 2: 0.45}.get(i, 0.5)
            jours = [a_debut + dt.timedelta(days=j) for j in range(max(1, (min(a_fin, auj) - a_debut).days + 1))]
            jours = [j for j in jours if j.weekday() < 6][-24:] or [a_debut]
            total = qte * part if qte else 0
            for j in jours:
                lignes.append(dict(chantier_id=cid, activite_id=aid, date_rapport=j,
                                   quantite=round(total / len(jours), 1) if qte else None,
                                   effectif=rnd.randint(8, 26), depenses=round(depense_jour.get(i, 1000) * rnd.uniform(0.6, 1.4)),
                                   materiaux=rnd.choice(["Ciment, sable", "Fers à béton", "Gravier", "Tôles", "Blocs de 15", None]),
                                   incident=False, commentaire="Travaux conformes au planning.",
                                   lat=pos[0] if pos else CHANTIERS[i][4], lon=pos[1] if pos else CHANTIERS[i][5],
                                   statut_validation="Validé", valide_par=conducteur,
                                   valide_le=dt.datetime.combine(j, dt.time(18)), cree_par=chefs[i]))
    # dépenses recalées sur une part réaliste du budget (Limete proche du dépassement)
    cibles = {0: 0.48, 1: 0.92, 2: 0.33, 4: 0.97}
    for i, part_budget in cibles.items():
        rows = [x for x in lignes if x["chantier_id"] == ch_ids[i]]
        tot = sum(x["depenses"] for x in rows)
        for x in rows:
            x["depenses"] = round(x["depenses"] * part_budget * CHANTIERS[i][8] / tot) if tot else x["depenses"]
    # derniers rapports en attente, un rejet et deux incidents
    recents = sorted([x for x in lignes if x["date_rapport"] >= auj - dt.timedelta(days=1)], key=lambda x: x["date_rapport"])
    for x in recents:
        x.update(statut_validation="En attente", valide_par=None, valide_le=None)
    if lignes:
        lignes[len(lignes) // 3].update(statut_validation="Rejeté", motif_rejet="Quantité supérieure à ce qui a été constaté.")
    for x in [x for x in lignes if x["chantier_id"] == ch_ids[1]][-3:-1]:
        x.update(incident=True, incident_desc="Retard de livraison de la charpente ; équipe partiellement inoccupée.")
    if lignes:
        with db.moteur().begin() as c:
            c.execute(db.rapports.insert(), lignes)
    return comptes


def supprimer() -> None:
    with db.moteur().begin() as c:
        ids = [r[0] for r in c.execute(sa.select(db.chantiers.c.id).where(db.chantiers.c.demo.is_(True)))]
        if ids:
            c.execute(db.rapports.delete().where(db.rapports.c.chantier_id.in_(ids)))
            c.execute(db.activites.delete().where(db.activites.c.chantier_id.in_(ids)))
            c.execute(db.affectations.delete().where(db.affectations.c.chantier_id.in_(ids)))
            c.execute(db.chantiers.delete().where(db.chantiers.c.id.in_(ids)))
        u_ids = [r[0] for r in c.execute(sa.select(db.utilisateurs.c.id).where(db.utilisateurs.c.demo.is_(True)))]
        if u_ids:
            t = db.rapports
            c.execute(t.update().where(t.c.valide_par.in_(u_ids)).values(valide_par=None))
            c.execute(t.update().where(t.c.cree_par.in_(u_ids)).values(cree_par=None))
            c.execute(db.activites.update().where(db.activites.c.responsable_id.in_(u_ids)).values(responsable_id=None))
            c.execute(db.affectations.delete().where(db.affectations.c.utilisateur_id.in_(u_ids)))
            c.execute(db.utilisateurs.delete().where(db.utilisateurs.c.id.in_(u_ids)))
