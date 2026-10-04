"""Chantiers : liste, fiche, création et modification."""
from __future__ import annotations

import datetime as dt

import streamlit as st

import auth
import calculs
import db
import ui


def _equipe() -> dict[int, str]:
    df = db.lire("select id, nom, role from utilisateurs where actif = :a and role in ('conducteur', 'chef') "
                 "order by nom", a=True)
    return {int(r.id): f"{r.nom} ({auth.ROLES[r.role]})" for r in df.itertuples()}


def _affectes(chantier_id: int) -> list[int]:
    df = db.lire("select utilisateur_id from affectations where chantier_id = :c", c=chantier_id)
    return df["utilisateur_id"].astype(int).tolist()


def _enregistrer_affectations(chantier_id: int, ids: list[int]) -> None:
    a = db.affectations
    with db.moteur().begin() as c:
        c.execute(a.delete().where(a.c.chantier_id == chantier_id))
        if ids:
            c.execute(a.insert(), [{"utilisateur_id": int(i), "chantier_id": chantier_id} for i in ids])


def _formulaire(cle: str, ch: dict | None = None) -> dict | None:
    """Champs communs à la création et à la modification. Renvoie les valeurs si le bouton est cliqué."""
    ch = ch or {}
    equipe = _equipe()
    with st.form(cle):
        a, b = st.columns(2)
        nom = a.text_input("Nom du chantier ou de l'activité *", value=ch.get("nom") or "")
        client = b.text_input("Client / maître d'ouvrage", value=ch.get("client") or "")
        types = db.TYPES_ACTIVITE
        type_act = a.selectbox("Type", types, index=types.index(ch["type_activite"]) if ch.get("type_activite") in types else 0)
        statut = b.selectbox("Statut", db.STATUTS_CHANTIER,
                             index=db.STATUTS_CHANTIER.index(ch["statut"]) if ch.get("statut") in db.STATUTS_CHANTIER else 0)
        adresse = st.text_input("Adresse / quartier / commune", value=ch.get("adresse") or "")
        coords = ui.champ_coordonnees(f"{cle}_gps", (ch.get("lat"), ch.get("lon")) if ch.get("lat") is not None else None)
        c, d, e = st.columns(3)
        debut = c.date_input("Date de début", value=ch.get("date_debut") or dt.date.today(), format="DD/MM/YYYY")
        fin = d.date_input("Date de fin prévue", value=ch.get("date_fin_prevue") or dt.date.today() + dt.timedelta(days=90),
                           format="DD/MM/YYYY")
        budget = e.number_input(f"Budget ({ui.devise()})", min_value=0.0, step=1000.0,
                                value=float(ch.get("budget") or 0.0), format="%.0f")
        desc = st.text_area("Description", value=ch.get("description") or "", height=80)
        equipe_ids = None
        if auth.peut("creer_chantier"):
            equipe_ids = st.multiselect("Équipe affectée (conducteurs et chefs de chantier)", list(equipe),
                                        default=[i for i in (ch.get("equipe") or []) if i in equipe],
                                        format_func=lambda i: equipe[i],
                                        help="Seules les personnes affectées voient ce chantier et peuvent y saisir des rapports.")
        ok = st.form_submit_button("Enregistrer", type="primary")
    if not ok:
        return None
    if not nom.strip():
        st.error("Le nom est obligatoire.")
        return None
    if fin < debut:
        st.error("La date de fin prévue est antérieure à la date de début.")
        return None
    return {"nom": nom.strip(), "client": client.strip(), "type_activite": type_act, "statut": statut,
            "adresse": adresse.strip(), "lat": coords[0] if coords else None, "lon": coords[1] if coords else None,
            "date_debut": debut, "date_fin_prevue": fin, "budget": budget or None, "description": desc.strip(),
            "equipe": equipe_ids}


def page() -> None:
    ui.en_tete("Chantiers", "Liste, fiche et localisation des chantiers et autres activités")
    u = auth.utilisateur()

    if auth.peut("creer_chantier"):
        with st.expander("Nouveau chantier", icon=":material/add_location_alt:", expanded=st.session_state.get("nouveau_chantier_ouvert", False)):
            v = _formulaire("form_nouveau_chantier")
            if v:
                equipe = v.pop("equipe") or []
                cid = db.inserer(db.chantiers, **v, cree_par=u["id"], demo=False)
                _enregistrer_affectations(cid, equipe)
                st.session_state["chantier_choisi"] = cid
                st.success(f"Chantier « {v['nom']} » créé.")

    s = calculs.synthese()
    if s.empty:
        st.info("Aucun chantier accessible pour le moment.")
        return
    dev = ui.devise()
    st.dataframe(ui.en_pct(s, "avancement"), hide_index=True,
                 column_order=["nom", "client", "type_activite", "etat", "avancement", "date_fin_prevue", "budget"],
                 column_config={"nom": "Chantier", "client": "Client", "type_activite": "Type", "etat": "État",
                                "avancement": ui.colonne_pct("Avancement"),
                                "date_fin_prevue": st.column_config.DateColumn("Fin prévue", format="DD/MM/YYYY"),
                                "budget": st.column_config.NumberColumn(f"Budget ({dev})", format="%.0f")})

    st.subheader("Fiche du chantier")
    ids = s["id"].tolist()
    defaut = st.session_state.get("chantier_choisi")
    cid = st.selectbox("Chantier", ids, index=ids.index(defaut) if defaut in ids else 0,
                       format_func=lambda i: s.loc[s["id"] == i, "nom"].iloc[0], label_visibility="collapsed")
    st.session_state["chantier_choisi"] = cid
    ligne = s[s["id"] == cid].iloc[0]
    ch = calculs.chantiers([cid]).iloc[0].to_dict()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("État", ligne["etat"])
    m2.metric("Avancement", f"{ligne['avancement']:.0%}",
              help=f"Attendu à ce jour : {ligne['attendu']:.0%}" if ligne["attendu"] == ligne["attendu"] else None)
    m3.metric("Activités réalisées", f"{ligne['realisees']} / {ligne['activites']}")
    m4.metric("Dépenses validées", calculs.fmt_montant(ligne["depenses"], dev),
              help=f"Budget : {calculs.fmt_montant(ligne['budget'], dev)}")

    g, d = st.columns([1, 1])
    with g:
        lignes = [f"**Client :** {ch.get('client') or '—'}", f"**Type :** {ch.get('type_activite') or '—'}",
                  f"**Adresse :** {ch.get('adresse') or '—'}"]
        if ch.get("date_debut") and ch.get("date_fin_prevue"):
            lignes.append(f"**Période :** {ch['date_debut']:%d/%m/%Y} → {ch['date_fin_prevue']:%d/%m/%Y}")
        st.markdown("  \n".join(lignes))
        if ch.get("description"):
            st.caption(ch["description"])
        noms = calculs.noms_utilisateurs()
        equipe = _affectes(cid)
        st.markdown("**Équipe :** " + (", ".join(noms.get(i, "?") for i in equipe) if equipe else "aucune personne affectée"))
    with d:
        if ch.get("lat") is not None and ch.get("lat") == ch.get("lat"):
            ui.apercu_point(ch["lat"], ch["lon"], ch["nom"])
        else:
            st.info("Pas de coordonnées GPS : ce chantier n'apparaît pas sur la carte.")

    modifiable = auth.peut("modifier_chantier") and (auth.peut("creer_chantier") or cid in (auth.chantiers_accessibles() or []))
    if modifiable:
        with st.expander("Modifier ce chantier", icon=":material/edit:"):
            v = _formulaire(f"form_modif_{cid}", {**ch, "equipe": _affectes(cid)})
            if v:
                equipe_ids = v.pop("equipe")
                db.maj(db.chantiers, cid, **v)
                if equipe_ids is not None:
                    _enregistrer_affectations(cid, equipe_ids)
                st.success("Modifications enregistrées.")
                st.rerun()
    if auth.peut("creer_chantier"):
        with st.expander("Supprimer ce chantier", icon=":material/delete:"):
            st.warning("La suppression efface aussi ses activités et tous ses rapports. Pour un chantier fini, "
                       "préférez le statut « Terminé ».")
            if st.checkbox("Je confirme la suppression définitive", key=f"conf_suppr_{cid}"):
                if st.button("Supprimer définitivement", type="primary", key=f"suppr_{cid}"):
                    db.executer(db.chantiers.delete().where(db.chantiers.c.id == cid))
                    st.session_state.pop("chantier_choisi", None)
                    st.rerun()
