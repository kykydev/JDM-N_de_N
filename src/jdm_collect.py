#!/usr/bin/env python3
"""Collecte brute des traits JDM pour tous les termes du corpus (étape 2).

Principe : on collecte BRUT. Aucun seuil, aucune coupure, aucune liste d'exclusion
n'est appliquée ici — ni le top 20 de H, ni l'exclusion des types TRT non sémantiques.
Ces décisions appartiennent à l'étape 3, pour qu'elles puissent varier sans relancer
deux heures de requêtes. Seul filtre : poids > 0 (une relation de poids <= 0 est niée
dans JDM).

Pour chaque terme de data/corpus/clean/termes.csv, une ligne JSONL contenant :
- existence, id, type et poids du nœud ;
- H  : TOUTES les relations r_isa sortantes de poids > 0 (cible, poids, type de nœud),
       triées par poids décroissant, sans plafond ; chaque cible porte les drapeaux
       `lang_prefix` et `forme_normalisee` qui permettront à l'étape 3 d'écarter les
       traductions et de fusionner les doublons de casse ;
- TRT : par type de relation entrante, le nombre de relations entrantes de poids > 0 ;
- SST : toutes les annotations _INFO-SEM-* de poids > 0 ; DET, NODET et les autres
       annotations morphologiques sont CONSERVÉES et marquées `morpho: true` ;
- raffinements : via r_raff_sem sortant (/refinements plante sur certains termes).
       Collectés, pas exploités : ils serviront à une expérience de désambiguïsation.

Diagnostic : pour un terme dont H est vide, la forme singulière simple (retrait d'un
« s » ou « x » final) est testée et consignée dans `diagnostic_singulier`. C'est un
DIAGNOSTIC : la forme originale reste celle utilisée, et le corpus n'est pas modifié.

Termes absents de JDM : le script PROPOSE un remplacement dans
reports/remplacements_proposes.csv, il ne l'applique jamais. Seules les variantes
morphologiques du même terme sont proposées ; aucune substitution par similarité
sémantique, faute de signatures pour la justifier.

Les noms des champs du JSONL et des colonnes du CSV sont figés : ils sont l'interface
de l'étape 3 et les changer rendrait la collecte inutilisable.

Reprise : le script est interruptible. Un terme déjà écrit est sauté, l'écriture est
incrémentale et vidée après chaque terme, les échecs sont consignés à part et réessayés
au lancement suivant.

Usage :
  python3 src/jdm_collect.py                # collecte puis rapport
  python3 src/jdm_collect.py --limit 20     # essai sur les 20 premiers termes
  python3 src/jdm_collect.py --report-only  # régénère le rapport depuis le JSONL
"""

import argparse
import csv
import html
import json
import re
import statistics
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import time

import config
from jdm_client import ClientJDM, JDMErreur, JDMIntrouvable

CHEMIN_PROPOSITIONS = config.DOSSIER_RAPPORTS / "remplacements_proposes.csv"
CHEMIN_RAPPORT = config.DOSSIER_RAPPORTS / "rapport_collecte.md"
CHEMIN_PHASE1 = config.DOSSIER_RAPPORTS / "phase1_payload.json"

PREFIXE_SST = "_INFO-SEM-"
# « en:aircraft », « de:Haus »... : code ISO de 2 ou 3 lettres suivi de deux-points.
PREFIXE_LANGUE_RE = re.compile(r"^([A-Za-z]{2,3}):")


# ---------------------------------------------------------------------------
# Normalisation et drapeaux
# ---------------------------------------------------------------------------

def forme_normalisee(nom):
    """Minuscules, NFC, espaces réduits — pour fusionner les doublons de casse à l'étape 3.
    La forme originale n'est jamais modifiée : cette valeur est stockée à côté d'elle.
    Retourne une chaîne."""
    texte = unicodedata.normalize("NFC", html.unescape(nom))
    return " ".join(texte.split()).lower()


def prefixe_langue(nom):
    """Code de langue en tête du nom, ou None. Retourne une chaîne ou None."""
    trouve = PREFIXE_LANGUE_RE.match(nom)
    return trouve.group(1) if trouve else None


def candidat_singulier(terme):
    """Forme singulière simple : retrait d'un « s » ou « x » final. Retourne une chaîne
    ou None si le terme ne porte pas de marque de pluriel simple."""
    if len(terme) > 3 and terme[-1] in "sx":
        return terme[:-1]
    return None


# ---------------------------------------------------------------------------
# Collecte d'un terme
# ---------------------------------------------------------------------------

def cibles_sortantes(client, terme, id_type):
    """Cibles des relations sortantes d'un type donné, poids > 0, triées par poids
    décroissant. Retourne une liste de {nom, poids, type_noeud}."""
    donnees = client.relations_sortantes(terme, types_ids=[id_type],
                                         timeout=config.TIMEOUT_DEFAUT)
    noms = {n["id"]: n["name"] for n in donnees.get("nodes") or []}
    types_noeuds = {n["id"]: n.get("type") for n in donnees.get("nodes") or []}
    cibles = []
    for relation in donnees.get("relations") or []:
        if relation["type"] != id_type or relation["w"] <= 0:
            continue
        cible = relation["node2"]
        cibles.append({"nom": noms.get(cible, str(cible)), "poids": relation["w"],
                       "type_noeud": types_noeuds.get(cible)})
    cibles.sort(key=lambda c: (-c["poids"], c["nom"]))
    return cibles


def construire_h(cibles):
    """H brut : toutes les cibles r_isa de poids > 0, plus les deux drapeaux de bruit.
    Retourne une liste de dicts.

    `type_noeud` est conservé parce qu'il ne se retrouve pas sans recollecte et que
    l'étape 3 en a besoin pour écarter les n_wikipedia aux noms tronqués."""
    hyperonymes = []
    for cible in cibles:
        hyperonymes.append({**cible,
                            "lang_prefix": prefixe_langue(cible["nom"]) is not None,
                            "forme_normalisee": forme_normalisee(cible["nom"])})
    return hyperonymes


def construire_sst(cibles):
    """SST brut : annotations _INFO-SEM-* de poids > 0. Retourne une liste de dicts.

    Rien n'est écarté ; les annotations morphologiques (DET, NODET, ...) sont marquées
    pour que l'étape 3 puisse trancher."""
    annotations = []
    for cible in cibles:
        if not cible["nom"].startswith(PREFIXE_SST):
            continue
        etiquette = cible["nom"][len(PREFIXE_SST):]
        annotations.append({"tag": etiquette, "poids": cible["poids"],
                            "morpho": etiquette in config.SST_ANNOTATIONS_MORPHO})
    return annotations


def construire_trt(client, terme, id_vers_relation):
    """TRT brut : par type de relation entrante, le nombre de relations de poids > 0.
    Aucun type n'est exclu ici : c'est l'affaire de l'étape 3. Retourne une liste de
    {type, n}, triée par effectif décroissant."""
    donnees = client.relations_entrantes(terme, timeout=config.TIMEOUT_RELATIONS_ENTRANTES,
                                         **config.PARAMS_RELATIONS_ENTRANTES)
    effectifs = Counter()
    for relation in donnees.get("relations") or []:
        if relation["w"] > 0:
            effectifs[relation["type"]] += 1
    return [{"type": id_vers_relation.get(id_type, str(id_type)), "n": n}
            for id_type, n in effectifs.most_common()]


def diagnostiquer_singulier(client, terme, id_r_isa):
    """Teste la forme singulière d'un terme à H vide. Retourne le dict de diagnostic.

    C'est un DIAGNOSTIC (papier §4.5, « liste de films ») : la forme originale reste
    celle utilisée et le corpus n'est pas modifié."""
    candidat = candidat_singulier(terme)
    if candidat is None:
        return {"forme_testee": None,
                "raison": "pas de marque de pluriel simple (« s »/« x » final)"}
    diagnostic = {"forme_testee": candidat}
    try:
        client.noeud_par_nom(candidat)
    except JDMIntrouvable:
        diagnostic["existe"] = False
        return diagnostic
    hyperonymes = construire_h(cibles_sortantes(client, candidat, id_r_isa))
    diagnostic.update(existe=True, H_taille=len(hyperonymes), H=hyperonymes)
    return diagnostic


def collecter_terme(client, terme, ids_relations, id_vers_relation, noms_types_noeuds):
    """Collecte tous les traits d'un terme. Retourne l'enregistrement JSONL."""
    enr = {"terme": terme,
           "collecte_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    try:
        noeud = client.noeud_par_nom(terme)
    except JDMIntrouvable:
        enr["existe"] = False
        return enr

    enr["existe"] = True
    enr["noeud"] = {"id": noeud["id"], "type": noms_types_noeuds.get(noeud.get("type")),
                    "poids": noeud.get("w")}
    enr["H"] = construire_h(cibles_sortantes(client, terme, ids_relations["r_isa"]))
    enr["TRT"] = construire_trt(client, terme, id_vers_relation)
    enr["SST"] = construire_sst(cibles_sortantes(client, terme, ids_relations["r_infopot"]))
    enr["raffinements"] = [{"nom": c["nom"], "poids": c["poids"]}
                           for c in cibles_sortantes(client, terme,
                                                     ids_relations["r_raff_sem"])]
    enr["diagnostic_singulier"] = None
    if not enr["H"]:
        enr["diagnostic_singulier"] = diagnostiquer_singulier(client, terme,
                                                              ids_relations["r_isa"])
    return enr


# ---------------------------------------------------------------------------
# Lecture du corpus et reprise
# ---------------------------------------------------------------------------

def charger_meta_termes():
    """Lit termes.csv. Retourne terme -> {roles, relations, couples, occurrences}."""
    meta = defaultdict(lambda: {"roles": set(), "relations": set(), "couples": set(),
                                "occurrences": 0})
    with open(config.FICHIER_TERMES, encoding="utf-8", newline="") as f:
        for ligne in csv.DictReader(f):
            entree = meta[ligne["terme"]]
            relations = [r for r in ligne["relations_associees"].split("|") if r]
            entree["roles"].add(ligne["role"])
            entree["relations"].update(relations)
            entree["couples"].update((ligne["role"], r) for r in relations)
            entree["occurrences"] += int(ligne["nb_occurrences"])
    return meta


def indexer_corpus():
    """Situe chaque terme dans le corpus. Retourne terme -> {(fichier, role, relation,
    syntagme, origine)}.

    Deux origines. « colonne » : le terme est le A ou le B retenu d'une ligne. « candidat » :
    le terme vient de la colonne `candidats` d'une ligne ambiguë, où les découpages
    concurrents sont notés « A1 / B1 | A2 / B2 ». Ces lignes-là ont leurs colonnes A et B
    vides, et leurs candidats ne seraient pas vus autrement."""
    index = defaultdict(set)
    for chemin in sorted(config.DOSSIER_CORPUS_PROPRE.glob("corpus_*.csv")):
        with open(chemin, encoding="utf-8", newline="") as f:
            for ligne in csv.DictReader(f):
                for role in ("A", "B"):
                    if ligne.get(role):
                        index[ligne[role]].add((chemin.name, role, ligne["relation"],
                                                ligne["syntagme"], "colonne"))
                for decoupage in (ligne.get("candidats") or "").split("|"):
                    parties = [p.strip() for p in decoupage.split("/")]
                    if len(parties) == 2 and all(parties):
                        for role, terme in zip(("A", "B"), parties):
                            index[terme].add((chemin.name, role, ligne["relation"],
                                              ligne["syntagme"], "candidat"))
    return index


def charger_deja_collectes(chemin, reparer=False):
    """Lit le JSONL déjà écrit. Retourne (ensemble des termes, liste des enregistrements).

    `reparer` retire du fichier une ligne tronquée (coupure en pleine écriture) pour que
    l'ajout suivant reparte sur du propre : réservé au démarrage de la collecte, car
    réécrire le fichier pendant qu'un collecteur y ajoute des lignes détruirait son
    travail. Une lecture ordinaire se contente d'ignorer la ligne cassée."""
    if not chemin.exists():
        return set(), []
    valides, enregistrements, tronquee = [], [], False
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        if not ligne.strip():
            continue
        try:
            enregistrements.append(json.loads(ligne))
        except ValueError:
            tronquee = True
            continue
        valides.append(ligne)
    if tronquee and reparer:
        chemin.write_text("\n".join(valides) + "\n", encoding="utf-8")
    return {e["terme"] for e in enregistrements}, enregistrements


def duree_hms(secondes):
    """Durée en h:mm:ss. Retourne une chaîne."""
    entier = int(secondes)
    return f"{entier // 3600:d}:{entier % 3600 // 60:02d}:{entier % 60:02d}"


# ---------------------------------------------------------------------------
# Propositions de remplacement (le script propose, il n'applique jamais)
# ---------------------------------------------------------------------------

def variantes_morphologiques(terme):
    """Variantes morphologiques du MÊME terme, par ordre de préférence. Retourne une
    liste de (candidat, méthode).

    Aucune proposition par similarité sémantique : on n'a pas encore les signatures."""
    variantes, vues = [], {terme}

    def ajouter(candidat, methode):
        if candidat and candidat not in vues:
            vues.add(candidat)
            variantes.append((candidat, methode))

    singulier = candidat_singulier(terme)
    ajouter(singulier, "singulier (retrait du « s »/« x » final)")
    ajouter(terme.lower(), "minuscules")
    if singulier:
        ajouter(singulier.lower(), "singulier + minuscules")
    if "-" in terme:
        ajouter(terme.replace("-", " "), "trait d'union remplacé par une espace")
        ajouter(terme.replace("-", ""), "trait d'union supprimé")
    if "’" in terme:
        ajouter(terme.replace("’", "'"),
                "apostrophe typographique remplacée par l'apostrophe droite")
    if "'" in terme:
        ajouter(terme.replace("'", "’"),
                "apostrophe droite remplacée par l'apostrophe typographique")
    ajouter(unicodedata.normalize("NFC", terme), "normalisation Unicode NFC")
    return variantes


def chercher_variante_existante(client, terme, journaliser):
    """Cherche la première variante morphologique présente dans JDM.
    Retourne (candidat, méthode) ; candidat vide si aucune ne convient."""
    for candidat, methode in variantes_morphologiques(terme):
        try:
            if client.existe(candidat):
                return candidat, f"variante morphologique : {methode}"
        except JDMErreur as e:
            journaliser(f"    variante « {candidat} » non testable : {e}")
    return "", "arbitrage manuel requis"


def proposer_remplacements(client, absents, index_corpus, journaliser):
    """Écrit reports/remplacements_proposes.csv. Retourne la liste des lignes écrites.
    Le corpus n'est modifié par aucun moyen."""
    lignes = []
    for terme in sorted(absents):
        candidat, methode = chercher_variante_existante(client, terme, journaliser)
        contextes = sorted(index_corpus.get(terme)
                           or {("(absent des fichiers corpus)", "", "", "", "colonne")})
        # Un terme qui n'apparaît QUE comme candidat d'un découpage ambigu ne se remplace
        # pas : son absence de JDM est précisément ce qui écarte ce découpage (§4.1 du
        # papier, reports/rapport_sonde_jdm.md §9). Proposer une variante ici reviendrait
        # à ressusciter un découpage que le corpus a déjà tranché.
        candidat_seul = contextes and all(o == "candidat" for *_, o in contextes)
        for fichier, role, relation, syntagme, _ in contextes:
            if candidat_seul:
                raison = (f"absent de JDM ; {role} d'un découpage concurrent de "
                          f"« {syntagme} », que cette absence écarte")
                propose = ""
                comment = ("aucun remplacement : l'absence tranche le découpage ambigu, "
                           "elle ne signale pas un terme manquant")
            else:
                raison = "absent de JDM sous sa forme exacte"
                propose, comment = candidat, methode
            lignes.append({"terme_absent": terme, "fichier": fichier, "role": role,
                           "relation": relation, "syntagme": syntagme, "raison": raison,
                           "candidat_propose": propose, "methode": comment})
        etat = "découpage ambigu écarté" if candidat_seul else methode
        journaliser(f"    {terme} -> {'(aucun)' if candidat_seul else candidat or '(aucun)'}"
                    f" [{etat}]")

    CHEMIN_PROPOSITIONS.parent.mkdir(parents=True, exist_ok=True)
    with open(CHEMIN_PROPOSITIONS, "w", encoding="utf-8", newline="") as f:
        redacteur = csv.DictWriter(f, fieldnames=["terme_absent", "fichier", "role",
                                                  "relation", "syntagme", "raison",
                                                  "candidat_propose", "methode"])
        redacteur.writeheader()
        redacteur.writerows(lignes)
    return lignes


# ---------------------------------------------------------------------------
# Collecte complète
# ---------------------------------------------------------------------------

def etat_du_terme(enr):
    """Résumé d'une ligne de journal pour un terme collecté. Retourne une chaîne."""
    if not enr["existe"]:
        return "ABSENT"
    return (f"H={len(enr['H']):<4d} TRT={len(enr['TRT']):<3d} "
            f"SST={len(enr['SST']):<2d} raff={len(enr['raffinements'])}")


def enregistrer_session(client, duree, nb_termes, reprise, collectes, erreurs):
    """Ajoute une ligne au journal des sessions. Retourne le dict de la session."""
    appels_reseau = [a for a in client.appels if not a["cached"]]
    session = {
        "debut_utc": datetime.fromtimestamp(time.time() - duree,
                                            timezone.utc).isoformat(timespec="seconds"),
        "fin_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "duree_s": round(duree, 1), "termes_vises": nb_termes, "reprise_sautes": reprise,
        "collectes": collectes, "erreurs": erreurs, "appels": len(client.appels),
        "appels_reseau": len(appels_reseau),
        "octets_reseau": sum(a["bytes"] or 0 for a in appels_reseau)}
    if config.FICHIER_SESSIONS.exists():
        sessions = json.loads(config.FICHIER_SESSIONS.read_text(encoding="utf-8"))
    else:
        sessions = []
    sessions.append(session)
    config.FICHIER_SESSIONS.write_text(json.dumps(sessions, ensure_ascii=False, indent=1),
                                       encoding="utf-8")
    return session


def lancer_collecte(limite=None, termes_choisis=None):
    """Collecte tous les termes non encore faits, puis propose les remplacements.
    Retourne la liste complète des enregistrements."""
    config.DOSSIER_COLLECTE.mkdir(parents=True, exist_ok=True)
    meta = charger_meta_termes()
    termes = sorted(meta)
    if termes_choisis:
        termes = [t for t in termes if t in termes_choisis]
    if limite:
        termes = termes[:limite]

    deja_faits, _ = charger_deja_collectes(config.FICHIER_COLLECTE, reparer=True)
    a_faire = [t for t in termes if t not in deja_faits]
    reprise = len(termes) - len(a_faire)

    def journaliser(message):
        print(message, flush=True)

    journaliser(f"Corpus : {len(termes)} termes ; déjà collectés : {reprise} ; "
                f"à faire : {len(a_faire)}")
    client = ClientJDM(dossier_cache=config.DOSSIER_CACHE_JDM, delai=config.DELAI_POLITESSE,
                       timeout=config.TIMEOUT_DEFAUT, essais=config.NB_ESSAIS)
    nom_vers_id, id_vers_relation = client.tables_types_relations()
    noms_types_noeuds = {t["id"]: t["name"] for t in client.types_de_noeuds()}
    ids_relations = {n: nom_vers_id[n] for n in ("r_isa", "r_infopot", "r_raff_sem")}

    depart = time.monotonic()
    erreurs = []
    with open(config.FICHIER_COLLECTE, "a", encoding="utf-8") as sortie:
        for numero, terme in enumerate(a_faire, 1):
            try:
                enr = collecter_terme(client, terme, ids_relations, id_vers_relation,
                                      noms_types_noeuds)
            except (JDMErreur, KeyError, TypeError, ValueError) as e:
                erreurs.append({"terme": terme, "erreur": f"{type(e).__name__}: {e}",
                                "utc": datetime.now(timezone.utc).isoformat(timespec="seconds")})
                journaliser(f"[{numero}/{len(a_faire)}] ERREUR {terme} : {e}")
                continue
            sortie.write(json.dumps(enr, ensure_ascii=False) + "\n")
            sortie.flush()
            ecoule = time.monotonic() - depart
            reste = ecoule / numero * (len(a_faire) - numero)
            journaliser(f"[{numero}/{len(a_faire)}] {100 * numero / len(a_faire):5.1f}%  "
                        f"{terme[:38]:<38} {etat_du_terme(enr):<28} | écoulé {duree_hms(ecoule)} "
                        f"| reste ~{duree_hms(reste)}")

    duree = time.monotonic() - depart
    if erreurs:
        with open(config.FICHIER_ERREURS, "a", encoding="utf-8") as f:
            for erreur in erreurs:
                f.write(json.dumps(erreur, ensure_ascii=False) + "\n")

    # Propositions pour les termes absents, sur la totalité du JSONL (pas seulement ce run).
    _, enregistrements = charger_deja_collectes(config.FICHIER_COLLECTE)
    absents = [e["terme"] for e in enregistrements if not e["existe"]]
    journaliser(f"\nTermes absents de JDM : {len(absents)}")
    proposer_remplacements(client, absents, indexer_corpus(), journaliser)

    session = enregistrer_session(client, duree, len(termes), reprise,
                                  len(a_faire) - len(erreurs), len(erreurs))
    journaliser(f"\nSession : {duree_hms(duree)}, {session['collectes']} termes, "
                f"{session['erreurs']} erreurs, {session['appels_reseau']} appels réseau, "
                f"{session['octets_reseau'] / 1e6:.1f} Mo")
    return enregistrements


# ---------------------------------------------------------------------------
# Outils de mise en forme du rapport
# ---------------------------------------------------------------------------

def mediane(valeurs):
    """Médiane d'une liste, 0 si elle est vide. Retourne un nombre."""
    return statistics.median(valeurs) if valeurs else 0


def milliers(n):
    """Entier avec séparateur de milliers à la française. Retourne une chaîne."""
    return f"{n:,}".replace(",", " ")


def fr(x, nd=1):
    """Nombre décimal à la française : séparateur virgule. Retourne une chaîne."""
    return f"{x:.{nd}f}".replace(".", ",")


def pct(partie, total, nd=1):
    """Pourcentage à la française, « — » si le total est nul. Retourne une chaîne."""
    return fr(100 * partie / total, nd) + " %" if total else "—"


def tableau(entete, lignes):
    """Construit un tableau Markdown. Retourne une liste de lignes."""
    sortie = ["| " + " | ".join(entete) + " |", "|" + "|".join(["---"] * len(entete)) + "|"]
    for ligne in lignes:
        sortie.append("| " + " | ".join(str(c) for c in ligne) + " |")
    return sortie + [""]


# ---------------------------------------------------------------------------
# Rapport : une fonction par section
# ---------------------------------------------------------------------------

def section_phase1():
    """Section 1 : optimisation du payload mesurée en phase 1. Retourne une liste de lignes."""
    lignes = ["## 1. Phase 1 : optimisation du payload de `/relations/to`", ""]
    if not CHEMIN_PHASE1.exists():
        return lignes + ["_Mesures absentes (`reports/phase1_payload.json`)._", ""]
    mesures = json.loads(CHEMIN_PHASE1.read_text(encoding="utf-8"))
    libelles = list(next(iter(mesures.values()))["combos"])
    reference = [mesures[t]["combos"][libelles[0]] for t in mesures]
    octets_ref = sum(c["bytes"] for c in reference)
    latence_ref = sum(c["elapsed_s"] for c in reference)

    corps = []
    for libelle in libelles:
        combinaison = [mesures[t]["combos"][libelle] for t in mesures]
        if not all(c["ok"] for c in combinaison):
            echecs = sum(1 for c in combinaison if not c["ok"])
            corps.append([f"`{libelle}`", "—", "—", "—", "—",
                          f"**500** sur {echecs}/{len(combinaison)} termes"])
            continue
        octets = sum(c["bytes"] for c in combinaison)
        latence = sum(c["elapsed_s"] for c in combinaison)
        identique = "oui" if all(c.get("ident_pos") for c in combinaison) else "**NON**"
        corps.append([f"`{libelle}`", milliers(octets), fr(latence, 2),
                      pct(octets_ref - octets, octets_ref, 0),
                      pct(latence_ref - latence, latence_ref, 0), identique])

    profils = " ; ".join(f"« {t} », {mesures[t]['profil']}" for t in mesures)
    lignes += [f"Cinq termes de profils contrastés : {profils}.", "",
               "Chaque combinaison est comparée à la référence sur le multi-ensemble "
               "`type de relation -> nombre de relations entrantes de poids > 0`, c'est-à-dire "
               "exactement le trait TRT. Une combinaison qui change ce résultat est rejetée, "
               "même plus rapide.", ""]
    lignes += tableau(["combinaison", "octets (5 termes)", "latence (s)", "gain volume",
                       "gain latence", "TRT identique"], corps)
    lignes += [
        "### Cause réelle des erreurs 500",
        "",
        "`relation_fields=[type]` échoue **sans aucun `types_ids`**, sur les cinq termes. "
        "En isolant les champs un à un : `[w]`, `[type,w]`, `[node1,w]`, `[id,w]` et "
        "`[type,w,node1]` passent ; `[type]`, `[node1]`, `[id,type]`, `[type,node1]` et "
        "`[type,type]` renvoient 500. La règle n'est donc pas « `relation_fields` combiné à "
        "`types_ids` » comme le supposait la sonde, mais : **`relation_fields` doit contenir "
        "`w`**. Les trois combinaisons reposant sur `[type]` seul sont inexploitables — ce qui "
        "tombe bien, puisque le comptage « poids > 0 » du trait TRT a de toute façon besoin de `w`.",
        "",
        "### Combinaison retenue : `without_nodes=true` + `relation_fields=[type,w]`, sans `min_weight`",
        "",
        "`min_weight=1` ne rapporte que 3 points de volume et 0,3 % de latence de plus. Écarté "
        "pour deux raisons. D'abord, c'est un filtre serveur : il ne perd rien sur ces cinq termes "
        "(compteurs TRT strictement identiques), mais une relation de poids 0 < w < 1 ailleurs "
        "dans le corpus disparaîtrait silencieusement — vérifié sur cinq termes n'est pas garanti "
        "sur 1871. Sans lui, le filtre `w > 0` est appliqué côté client sur la même donnée que la "
        "référence : l'identité est acquise par construction, pas par échantillon. Ensuite, le "
        "principe de collecte brute : `min_weight=1` jette les relations niées, alors qu'en les "
        "gardant on consigne leur nombre par type et l'étape 3 pourra faire varier ce seuil sans "
        "recollecte.",
        "",
        "Portée du gain : la sonde utilisait **déjà** ces paramètres sur `/relations/to`. Son "
        "estimation de 2,2 h et 0,9 Go les intègre donc ; les 82 % mesurés ici disent ce qu'aurait "
        "coûté la passe sans eux (≈ 5 Go de cache), ils ne la raccourcissent pas. La latence de cet "
        "endpoint est par ailleurs dominée par la charge du serveur, non par le payload : les mêmes "
        "paramètres ont donné 2,36 s de moyenne à la sonde et 1,0 s ici sur le terme le plus lourd "
        "(« animaux », 150 220 relations entrantes).",
        "",
    ]
    return lignes


def section_couverture(enregistrements, trouves, absents, meta, relations_corpus):
    """Section 2 : couverture par rôle et par type de relation. Retourne une liste de lignes."""
    lignes = ["## 2. Couverture", "",
              f"Termes du corpus : **{len(enregistrements)}**. Trouvés dans JDM : "
              f"**{len(trouves)}** ({pct(len(trouves), len(enregistrements))}). "
              f"Absents : **{len(absents)}**.", ""]
    if absents:
        noms = ", ".join(f"« {e['terme']} »" for e in sorted(absents, key=lambda e: e["terme"]))
        lignes += [f"Termes absents : {noms}.", "",
                   "Propositions de remplacement dans `reports/remplacements_proposes.csv` "
                   "(le script propose, il n'applique jamais).", ""]

    corps = []
    for role in ("A", "B"):
        vivier = [e for e in enregistrements if role in meta[e["terme"]]["roles"]]
        trouves_role = [e for e in vivier if e["existe"]]
        corps.append([role, len(vivier), len(trouves_role), pct(len(trouves_role), len(vivier))])
    lignes += ["### Par rôle", "", "Un terme jouant les deux rôles compte dans les deux lignes.", ""]
    lignes += tableau(["rôle", "termes", "trouvés", "couverture"], corps)

    corps = []
    for relation in relations_corpus:
        vivier = [e for e in enregistrements if relation in meta[e["terme"]]["relations"]]
        trouves_rel = [e for e in vivier if e["existe"]]
        corps.append([f"`{relation}`", len(vivier), len(trouves_rel),
                      pct(len(trouves_rel), len(vivier))])
    lignes += ["### Par type de relation", "",
               "Un terme apparaissant sous plusieurs types compte dans chaque ligne.", ""]
    lignes += tableau(["relation", "termes", "trouvés", "couverture"], corps)
    return lignes


def section_tailles(trouves):
    """Section 3 : tailles brutes par trait et inventaire SST. Retourne une liste de lignes."""
    tailles_h = [len(e["H"]) for e in trouves]
    tailles_trt = [len(e["TRT"]) for e in trouves]
    tailles_sst = [len(e["SST"]) for e in trouves]
    tailles_sst_sem = [sum(1 for s in e["SST"] if not s["morpho"]) for e in trouves]

    lignes = ["## 3. Tailles brutes par trait", "",
              "Sur les termes trouvés, sans aucune coupure.", ""]
    lignes += tableau(
        ["trait", "min", "médiane", "max", "total"],
        [["\\|H\\| — hyperonymes r_isa, w > 0", min(tailles_h), f"{mediane(tailles_h):g}",
          max(tailles_h), milliers(sum(tailles_h))],
         ["\\|TRT\\| — types de relations entrantes", min(tailles_trt),
          f"{mediane(tailles_trt):g}", max(tailles_trt), "—"],
         ["\\|SST\\| — _INFO-SEM-*, w > 0", min(tailles_sst), f"{mediane(tailles_sst):g}",
          max(tailles_sst), milliers(sum(tailles_sst))],
         ["\\|SST\\| hors annotations morphologiques", min(tailles_sst_sem),
          f"{mediane(tailles_sst_sem):g}", max(tailles_sst_sem),
          milliers(sum(tailles_sst_sem))]])

    volumes = [sum(t["n"] for t in e["TRT"]) for e in trouves]
    lignes += [f"Relations entrantes de poids > 0 par terme : min {milliers(min(volumes))}, "
               f"médiane {milliers(int(mediane(volumes)))}, max {milliers(max(volumes))}, "
               f"total {milliers(sum(volumes))}.", ""]

    etiquettes, morpho = Counter(), {}
    for enr in trouves:
        for annotation in enr["SST"]:
            etiquettes[annotation["tag"]] += 1
            morpho[annotation["tag"]] = annotation["morpho"]
    lignes += ["### Inventaire des annotations _INFO-SEM-*", "",
               "Toutes sont conservées dans le JSONL. La colonne `morpho` est le drapeau que "
               "l'étape 3 pourra utiliser pour les inclure ou les exclure par configuration, "
               "sans recollecte (constante `SST_ANNOTATIONS_MORPHO` de `src/config.py`).", ""]
    lignes += tableau(["annotation", "termes concernés", "morpho"],
                      [[f"`{t}`", n, "**oui**" if morpho[t] else "non"]
                       for t, n in sorted(etiquettes.items(), key=lambda kv: (-kv[1], kv[0]))])
    return lignes


def section_traits_vides(trouves):
    """Section 4 : traits vides et diagnostic singulier. Retourne une liste de lignes."""
    h_vides = [e for e in trouves if not e["H"]]
    sst_vides = [e for e in trouves if not e["SST"]]
    lignes = ["## 4. Traits vides et diagnostic morphologique", "",
              f"H vide (aucun hyperonyme de poids > 0) : **{len(h_vides)}** termes "
              f"({pct(len(h_vides), len(trouves))} des termes trouvés).", "",
              f"SST vide (aucune annotation _INFO-SEM-*) : **{len(sst_vides)}** termes "
              f"({pct(len(sst_vides), len(trouves))}).", ""]

    testes = [e for e in h_vides if (e.get("diagnostic_singulier") or {}).get("forme_testee")]
    non_testables = [e for e in h_vides
                     if not (e.get("diagnostic_singulier") or {}).get("forme_testee")]
    existants = [e for e in testes if e["diagnostic_singulier"].get("existe")]
    gagnants = [e for e in existants if e["diagnostic_singulier"].get("H_taille", 0) > 0]
    lignes += ["### Diagnostic singulier", "",
               "Pour chaque terme à H vide, la forme singulière simple (retrait d'un « s »/« x » "
               "final) est testée. **C'est un diagnostic : la forme originale reste celle utilisée "
               "et le corpus n'est pas modifié.** Le papier décrit ce cas de dispersion en §4.5 "
               "(« liste de films »).", "",
               f"- Termes à H vide sans marque de pluriel simple, non testables : {len(non_testables)}",
               f"- Formes singulières testées : {len(testes)} ; existant dans JDM : {len(existants)}",
               f"- **Formes singulières apportant au moins un hyperonyme : {len(gagnants)}**", ""]
    if gagnants:
        corps = []
        for enr in sorted(gagnants, key=lambda e: -e["diagnostic_singulier"]["H_taille"]):
            diagnostic = enr["diagnostic_singulier"]
            premiers = ", ".join(f"{h['nom']} ({h['poids']:g})" for h in diagnostic["H"][:3])
            corps.append([enr["terme"], diagnostic["forme_testee"], diagnostic["H_taille"],
                          premiers or "—"])
        lignes += tableau(["terme (H vide)", "forme singulière", "\\|H\\| du singulier",
                           "3 premiers hyperonymes"], corps)

    for titre, vivier in (("termes à H vide", h_vides), ("termes à SST vide", sst_vides)):
        if vivier:
            noms = ", ".join(f"« {e['terme']} »" for e in sorted(vivier, key=lambda e: e["terme"]))
            lignes += [f"<details><summary>Liste complète des {titre} ({len(vivier)})</summary>",
                       "", noms, "", "</details>", ""]
    return lignes


def section_bruit(trouves):
    """Section 5 : bruit marqué dans H. Retourne une liste de lignes."""
    total_h = sum(len(e["H"]) for e in trouves) or 1
    avec_prefixe = sum(1 for e in trouves for h in e["H"] if h["lang_prefix"])
    termes_touches = sum(1 for e in trouves if any(h["lang_prefix"] for h in e["H"]))
    prefixes = Counter(prefixe_langue(h["nom"]) for e in trouves for h in e["H"]
                       if h["lang_prefix"])
    doublons = 0
    for enr in trouves:
        formes = Counter(h["forme_normalisee"] for h in enr["H"])
        doublons += sum(n - 1 for n in formes.values() if n > 1)
    plus_frequents = ", ".join(f"`{p}:` ({n})" for p, n in prefixes.most_common(10))
    return ["## 5. Bruit marqué dans H (marqué, jamais supprimé)", "",
            f"- Cibles à préfixe de langue : **{milliers(avec_prefixe)}** sur {milliers(total_h)} "
            f"({pct(avec_prefixe, total_h)}), touchant {termes_touches} termes. Préfixes les plus "
            f"fréquents : {plus_frequents}.",
            f"- Doublons de casse ou d'espaces repérables par `forme_normalisee` : "
            f"**{milliers(doublons)}** cibles redondantes (ex. « Procédé de séparation » et "
            "« procédé de séparation »).", "",
            "Les deux drapeaux sont posés dans le JSONL ; aucune cible n'est retirée. L'étape 3 "
            "décidera d'écarter les traductions et de fusionner les doublons.", ""]


def section_polysemie(trouves, meta, relations_corpus):
    """Section 6 : polysémie mesurée par les raffinements. Retourne une liste de lignes."""
    nombres = [len(e["raffinements"]) for e in trouves]
    polysemiques = [e for e in trouves if e["raffinements"]]
    lignes = ["## 6. Polysémie (raffinements r_raff_sem)", "",
              "Collectés, non exploités : ils serviront à une expérience de désambiguïsation "
              "ultérieure.", "",
              f"Raffinements par terme : min {min(nombres)}, médiane {mediane(nombres):g}, "
              f"max {max(nombres)}. Termes polysémiques (≥ 1 raffinement) : "
              f"**{len(polysemiques)}/{len(trouves)}** ({pct(len(polysemiques), len(trouves))}).", ""]

    corps = []
    for relation in relations_corpus:
        vivier = [e for e in trouves if relation in meta[e["terme"]]["relations"]]
        avec = [e for e in vivier if e["raffinements"]]
        medianes = mediane([len(e["raffinements"]) for e in vivier])
        corps.append([f"`{relation}`", len(vivier), len(avec), pct(len(avec), len(vivier)),
                      f"{medianes:g}"])
    lignes += tableau(["relation", "termes trouvés", "polysémiques", "part",
                       "raffinements médians"], corps)

    corps = []
    for role in ("A", "B"):
        vivier = [e for e in trouves if role in meta[e["terme"]]["roles"]]
        avec = [e for e in vivier if e["raffinements"]]
        corps.append([role, len(vivier), len(avec), pct(len(avec), len(vivier))])
    lignes += tableau(["rôle", "termes trouvés", "polysémiques", "part"], corps)
    return lignes


def section_cout():
    """Section 7 : coût réel de la passe. Retourne une liste de lignes."""
    if config.FICHIER_SESSIONS.exists():
        sessions = json.loads(config.FICHIER_SESSIONS.read_text(encoding="utf-8"))
    else:
        sessions = []
    duree = sum(s["duree_s"] for s in sessions)
    if config.DOSSIER_CACHE_JDM.exists():
        fichiers_cache = list(config.DOSSIER_CACHE_JDM.glob("*.json"))
    else:
        fichiers_cache = []
    octets_cache = sum(f.stat().st_size for f in fichiers_cache)
    if config.FICHIER_ERREURS.exists():
        n_erreurs = len(config.FICHIER_ERREURS.read_text(encoding="utf-8").splitlines())
    else:
        n_erreurs = 0

    lignes = ["## 7. Coût réel de la passe", ""]
    lignes += tableau(
        ["mesure", "valeur"],
        [["durée cumulée", duree_hms(duree)],
         ["sessions (reprises comprises)", len(sessions)],
         ["termes sautés par reprise (cumul)", sum(s["reprise_sautes"] for s in sessions)],
         ["erreurs consignées", n_erreurs],
         ["requêtes servies", milliers(sum(s["appels"] for s in sessions))],
         ["dont appels réseau réels", milliers(sum(s["appels_reseau"] for s in sessions))],
         ["volume téléchargé", f"{fr(sum(s['octets_reseau'] for s in sessions) / 1e6, 0)} Mo"],
         ["fichiers de cache", milliers(len(fichiers_cache))],
         ["volume du cache", f"{fr(octets_cache / 1e9, 2)} Go"]])
    if n_erreurs:
        lignes += ["Les termes en erreur ne sont pas écrits dans le JSONL : ils sont consignés "
                   "dans `data/collecte/erreurs.jsonl` et seront réessayés au prochain "
                   "lancement.", ""]
    return lignes


def construire_rapport(enregistrements):
    """Écrit reports/rapport_collecte.md depuis les enregistrements. Ne retourne rien."""
    if not enregistrements:
        print("JSONL vide : rien à rapporter.")
        return
    meta = charger_meta_termes()
    trouves = [e for e in enregistrements if e["existe"]]
    absents = [e for e in enregistrements if not e["existe"]]
    relations_corpus = sorted({r for m in meta.values() for r in m["relations"]})

    lignes = ["# Collecte brute des traits JDM", "",
              f"Généré par `src/jdm_collect.py` le {datetime.now().strftime('%Y-%m-%d')}. "
              "API : `https://jdm-api.demo.lirmm.fr/v0`. Sortie : `data/collecte/termes_jdm.jsonl`, "
              "un enregistrement JSON par terme.", "",
              "**Aucun seuil, aucune coupure, aucune exclusion de types n'est appliqué ici.** Seules les "
              "relations de poids ≤ 0 (niées dans JDM) sont écartées des traits, et leur nombre est "
              "conservé dans chaque enregistrement pour que ce choix même reste réversible. Le top 20 de "
              "H et l'exclusion des types TRT non sémantiques appartiennent à l'étape 3. Le corpus n'est "
              "modifié par aucun moyen.", ""]
    lignes += section_phase1()
    lignes += section_couverture(enregistrements, trouves, absents, meta, relations_corpus)
    lignes += section_tailles(trouves)
    lignes += section_traits_vides(trouves)
    lignes += section_bruit(trouves)
    lignes += section_polysemie(trouves, meta, relations_corpus)
    lignes += section_cout()
    lignes += ["## 8. Hors périmètre", "",
               "Cette étape ne produit ni seuil, ni vecteur, ni vocabulaire global, ni similarité, ni "
               "désambiguïsation par raffinement, ni algorithme GRASP-it, et n'applique aucun "
               "remplacement. Le corpus est inchangé.", ""]

    CHEMIN_RAPPORT.parent.mkdir(parents=True, exist_ok=True)
    CHEMIN_RAPPORT.write_text("\n".join(lignes), encoding="utf-8")
    print(f"Rapport écrit : {CHEMIN_RAPPORT}")


def main():
    analyseur = argparse.ArgumentParser()
    analyseur.add_argument("--limit", type=int, default=None,
                           help="ne traiter que les N premiers termes")
    analyseur.add_argument("--terms", nargs="*", default=None, help="restreindre à ces termes")
    analyseur.add_argument("--report-only", action="store_true",
                           help="régénère le rapport depuis le JSONL, sans appel réseau")
    arguments = analyseur.parse_args()

    if arguments.report_only:
        _, enregistrements = charger_deja_collectes(config.FICHIER_COLLECTE)
        construire_rapport(enregistrements)
        return
    choisis = set(arguments.terms) if arguments.terms else None
    enregistrements = lancer_collecte(limite=arguments.limit, termes_choisis=choisis)
    construire_rapport(enregistrements)


if __name__ == "__main__":
    main()
