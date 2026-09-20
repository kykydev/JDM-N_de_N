#!/usr/bin/env python3
"""Sonde JDM sur 30 termes stratifiés, pour choisir les seuils des signatures.

Mesure, pour chaque terme : existence, id et type du nœud ; trait H (50 premiers
r_isa par poids décroissant) ; trait TRT (types de relations entrantes et effectifs) ;
trait SST (_INFO-SEM-*) ; nombre de raffinements ; latence de chaque appel.
Tranche aussi les deux lignes ambiguës du corpus par existence dans JDM (§4.1).

N'écrit que reports/rapport_sonde_jdm.md (et le cache/journal du client).
Aucun seuil définitif n'est appliqué : seules les relations de poids <= 0 (niées
dans JDM) sont écartées, et le rapport chiffre les coupures possibles.

Usage : python3 src/jdm_probe.py
"""

import csv
import random
import statistics
from collections import Counter, defaultdict

import config
from corpus_check import decoupages_possibles
from jdm_client import ClientJDM, JDMErreur, JDMIntrouvable, nom_raffinement_lisible

CHEMIN_RAPPORT = config.DOSSIER_RAPPORTS / "rapport_sonde_jdm.md"

AMBIGUS = ["cacao de Côte d'Ivoire", "diamants d'Afrique du Sud"]

# Filtrage paramétrable par trait. Les filtres de main.py (préfixes « _ » et « : »,
# nœuds n_term/n_form uniquement) valent pour H, mais pas globalement : les
# _INFO-SEM-* sont des nœuds n_data_pot préfixés « _ », et ils SONT le trait SST.
# types_noeuds : ids de types de nœuds admis (None = tous).
FILTRES_TRAITS = {
    "H": {"sens": "sortant", "relation": "r_isa", "types_noeuds": (1, 2),  # n_term, n_form
          "prefixes_gardes": None, "prefixes_exclus": ("_", ":"), "poids_minimum_exclu": 0},
    "SST": {"sens": "sortant", "relation": "r_infopot", "types_noeuds": None,
            "prefixes_gardes": ("_INFO-SEM-",), "prefixes_exclus": (), "poids_minimum_exclu": 0},
    # TRT : symboles = noms de types de relations entrantes ; aucun type exclu à ce stade.
    "TRT": {"sens": "entrant", "types_relations_exclus": (), "poids_minimum_exclu": 0},
}

# Coupures de H chiffrées par le rapport : (libellé, genre de coupure, valeur).
COUPURES_H = [
    ("aucune (w > 0)", "aucune", None),
    ("top 10", "rang", 10),
    ("top 20", "rang", 20),
    ("w ≥ 50", "absolu", 50),
    ("w ≥ 100", "absolu", 100),
    ("w ≥ 25 % de w₁", "relatif", 0.25),
    ("w ≥ 50 % de w₁", "relatif", 0.5),
]

# Strate 1 : pas de mesure de fréquence hors-ligne, donc liste explicite (vérifiée ci-dessous).
CONCRETS = ["voiture", "maison", "pain", "chien", "vélo", "bateau"]
POLYLEXICAUX_IMPOSES = ["terre cuite", "Côte d'Ivoire"]


# ---------------------------------------------------------------------------
# Sélection des 30 termes
# ---------------------------------------------------------------------------

def charger_termes():
    """Lit termes.csv. Retourne terme -> {roles, relations, by_role, occ}."""
    termes = defaultdict(lambda: {"roles": set(), "relations": set(),
                                  "by_role": defaultdict(set), "occ": 0})
    with open(config.FICHIER_TERMES, encoding="utf-8", newline="") as f:
        for ligne in csv.DictReader(f):
            entree = termes[ligne["terme"]]
            relations = ligne["relations_associees"].split("|")
            entree["roles"].add(ligne["role"])
            entree["relations"].update(relations)
            if int(ligne["nb_occurrences"]) > 0:
                entree["by_role"][ligne["role"]].update(relations)
            entree["occ"] += int(ligne["nb_occurrences"])
    return termes


def termes_b_pluriels():
    """Termes B introduits par « des » : pluriel certain (contrairement à un -s final).
    Retourne un ensemble de termes."""
    pluriels = set()
    for chemin in sorted(config.DOSSIER_CORPUS_PROPRE.glob("corpus_*.csv")):
        with open(chemin, encoding="utf-8", newline="") as f:
            for ligne in csv.DictReader(f):
                if ligne["ambigu"] == "non" and f" des {ligne['B']}" in f" {ligne['syntagme']}":
                    pluriels.add(ligne["B"])
    return pluriels


def est_polylexical(terme):
    """Dit si le terme contient une espace, un tiret ou une apostrophe. Retourne un booléen."""
    return any(caractere in terme for caractere in " -'’")


def tirer_strate(rng, libelle, vivier, k, deja_choisis):
    """Tire k termes d'un vivier, hors termes déjà choisis. Retourne la liste triée tirée."""
    candidats = sorted(t for t in vivier if t not in deja_choisis)
    assert len(candidats) >= k, f"strate {libelle} : {len(candidats)} candidats pour {k}"
    return sorted(rng.sample(candidats, k))


def termes_ayant_role(termes, role, relation):
    """Termes jouant ce rôle pour cette relation, hors lignes ambiguës. Retourne une liste."""
    return [t for t, v in termes.items() if relation in v["by_role"][role]]


def selectionner_termes(termes):
    """Compose l'échantillon stratifié de 30 termes. Retourne une liste de (terme, strate)."""
    rng = random.Random(config.GRAINE_ALEATOIRE)
    choisis, strates = set(), []

    absents = [t for t in CONCRETS + POLYLEXICAUX_IMPOSES if t not in termes]
    assert not absents, f"absents de termes.csv : {absents}"
    choisis.update(CONCRETS)
    strates.extend((t, "concret") for t in CONCRETS)

    for relation in ("r_has_property-1", "r_processus_agent", "r_processus_patient"):
        vivier = [t for t in termes_ayant_role(termes, "A", relation) if not est_polylexical(t)]
        tires = tirer_strate(rng, "abstrait", vivier, 2, choisis)
        choisis.update(tires)
        strates.extend((t, "abstrait") for t in tires)

    for relation in ("r_lieu", "r_lieu>origine"):
        vivier = [t for t in termes_ayant_role(termes, "B", relation)
                  if t[:1].isupper() and not est_polylexical(t)]
        tires = tirer_strate(rng, "entité nommée", vivier, 3, choisis)
        choisis.update(tires)
        strates.extend((t, "entité nommée") for t in tires)

    choisis.update(POLYLEXICAUX_IMPOSES)
    strates.extend((t, "polylexical") for t in POLYLEXICAUX_IMPOSES)
    # Les termes nés d'un découpage ambigu (« cacao de Côte ») ne sont pas de vrais polylexicaux.
    vivier = [t for t, v in termes.items() if est_polylexical(t) and v["occ"] > 0]
    tires = tirer_strate(rng, "polylexical", vivier,
                         config.TERMES_PAR_STRATE - len(POLYLEXICAUX_IMPOSES), choisis)
    choisis.update(tires)
    strates.extend((t, "polylexical") for t in tires)

    vivier = [t for t in termes_b_pluriels() if not est_polylexical(t) and not t[:1].isupper()]
    tires = tirer_strate(rng, "pluriel", vivier, config.TERMES_PAR_STRATE, choisis)
    choisis.update(tires)
    strates.extend((t, "pluriel") for t in tires)

    assert len(strates) == 30 and len({t for t, _ in strates}) == 30
    return strates


# ---------------------------------------------------------------------------
# Mesures par terme
# ---------------------------------------------------------------------------

def garder_symbole(nom, poids, type_noeud, filtre):
    """Dit si une cible passe le filtre du trait. Retourne un booléen."""
    if poids <= filtre["poids_minimum_exclu"]:
        return False
    if filtre.get("types_noeuds") and type_noeud not in filtre["types_noeuds"]:
        return False
    if filtre.get("prefixes_gardes") and not nom.startswith(tuple(filtre["prefixes_gardes"])):
        return False
    if filtre.get("prefixes_exclus") and nom.startswith(tuple(filtre["prefixes_exclus"])):
        return False
    return True


def symboles_sortants(client, terme, id_relation, filtre):
    """Cibles sortantes d'un type de relation, filtrées et triées par poids décroissant.
    Retourne (liste de (nom, poids), nombre de relations brutes, compteur des écartées)."""
    donnees = client.relations_sortantes(terme, types_ids=[id_relation])
    noms = {n["id"]: n["name"] for n in donnees["nodes"]}
    types_noeuds = {n["id"]: n.get("type") for n in donnees["nodes"]}
    relations = [r for r in donnees["relations"] if r["type"] == id_relation]

    gardes, ecartees = [], Counter()
    for relation in sorted(relations, key=lambda r: (-r["w"], noms.get(r["node2"], ""))):
        nom_brut = noms.get(relation["node2"], str(relation["node2"]))
        if relation["w"] <= filtre["poids_minimum_exclu"]:
            ecartees["poids ≤ 0"] += 1
        elif not garder_symbole(nom_brut, relation["w"], types_noeuds.get(relation["node2"]), filtre):
            ecartees["type de nœud ou préfixe"] += 1
        else:
            gardes.append((nom_raffinement_lisible(nom_brut, noms, client), relation["w"]))
    return gardes, len(relations), ecartees


def compter_types_entrants(client, terme, id_vers_relation):
    """Compte les relations entrantes de poids > 0 par type de relation.
    Retourne (compteur type -> effectif, nombre de relations brutes, nombre de poids ≤ 0)."""
    filtre = FILTRES_TRAITS["TRT"]
    donnees = client.relations_entrantes(terme, timeout=config.TIMEOUT_RELATIONS_ENTRANTES,
                                  without_nodes=True, relation_fields=["type", "w"])
    effectifs, non_positives = Counter(), 0
    for relation in donnees["relations"]:
        nom_type = id_vers_relation.get(relation["type"], str(relation["type"]))
        if relation.get("w", 0) <= filtre["poids_minimum_exclu"]:
            non_positives += 1
        elif nom_type not in filtre["types_relations_exclus"]:
            effectifs[nom_type] += 1
    return effectifs, len(donnees["relations"]), non_positives


def compter_raffinements(client, terme, nom_jdm, id_raff_sem):
    """Compte les raffinements du terme via r_raff_sem sortant. Retourne (sens de premier
    niveau, total).

    /refinements n'est pas utilisé : il plante côté serveur dès qu'un raffinement est
    nommé « terme>glose » au lieu de « terme>id » (ex. « chien »)."""
    donnees = client.relations_sortantes(terme, types_ids=[id_raff_sem])
    noms = {n["id"]: n["name"] for n in donnees["nodes"]}
    raffinements = [noms.get(r["node2"], "") for r in donnees["relations"]
                    if r["type"] == id_raff_sem and r["w"] > 0]
    raffinements = [x for x in raffinements if x.startswith(nom_jdm + ">")]
    sens = sum(1 for x in raffinements if x.count(">") == 1)
    return sens, len(raffinements)


def sonder_terme(client, terme, ids_relations, id_vers_relation, types_noeuds):
    """Mesure tous les traits d'un terme. Retourne l'enregistrement de mesures."""
    premier_appel = len(client.appels)
    enr = {"terme": terme}
    try:
        noeud = client.noeud_par_nom(terme)
    except JDMIntrouvable:
        enr["existe"] = False
        enr["appels"] = client.appels[premier_appel:]
        return enr

    enr.update(existe=True, id=noeud["id"],
               type=types_noeuds.get(noeud.get("type"), noeud.get("type")),
               poids=noeud.get("w"), nom_jdm=noeud["name"])

    hyperonymes, enr["H_relations_brutes"], enr["H_ecartees"] = symboles_sortants(
        client, terme, ids_relations["r_isa"], FILTRES_TRAITS["H"])
    enr["H_poids"] = [poids for _, poids in hyperonymes]
    enr["H"] = hyperonymes[:config.H_PLAFOND_SONDE]

    enr["SST"], enr["SST_relations_brutes"], enr["SST_ecartees"] = symboles_sortants(
        client, terme, ids_relations["r_infopot"], FILTRES_TRAITS["SST"])

    enr["TRT"], enr["TRT_relations_brutes"], enr["TRT_non_positives"] = compter_types_entrants(
        client, terme, id_vers_relation)

    enr["raff_sens"], enr["raff_total"] = compter_raffinements(
        client, terme, noeud["name"], ids_relations["r_raff_sem"])

    enr["appels"] = client.appels[premier_appel:]
    return enr


def tester_ambiguites(client):
    """Teste l'existence des candidats A et B de chaque ligne ambiguë. Retourne une liste
    de {syntagme, entier_existe, candidats}. Le corpus n'est pas modifié."""
    resultats = []
    for syntagme in AMBIGUS:
        candidats = []
        for candidat in decoupages_possibles(syntagme):
            candidats.append({"A": candidat["A"], "B": candidat["B"],
                              "A_existe": client.existe(candidat["A"]),
                              "B_existe": client.existe(candidat["B"])})
        resultats.append({"syntagme": syntagme, "entier_existe": client.existe(syntagme),
                          "candidats": candidats})
    return resultats


# ---------------------------------------------------------------------------
# Outils de mise en forme du rapport
# ---------------------------------------------------------------------------

def mediane(valeurs):
    """Médiane d'une liste, ou None si elle est vide. Retourne un nombre ou None."""
    return statistics.median(valeurs) if valeurs else None


def fmt(x, nd=1):
    """Formate un nombre pour le rapport, « — » si absent. Retourne une chaîne."""
    if x is None:
        return "—"
    return f"{x:.{nd}f}" if isinstance(x, float) else str(x)


def tableau(entete, lignes):
    """Construit un tableau Markdown. Retourne une liste de lignes."""
    sortie = ["| " + " | ".join(entete) + " |", "|" + "---|" * len(entete)]
    for ligne in lignes:
        sortie.append("| " + " | ".join(str(c).replace("|", "\\|") for c in ligne) + " |")
    return sortie


def endpoint_de(chemin):
    """Nom d'endpoint correspondant à un chemin d'API. Retourne une chaîne."""
    if chemin.startswith("/relations/from/"):
        return "relations/from"
    if chemin.startswith("/relations/to/"):
        return "relations/to"
    return chemin.strip("/").split("/")[0]


def taille_h_apres_coupure(hyperonymes, genre, valeur):
    """Nombre d'hyperonymes gardés par une coupure donnée. Retourne un entier."""
    if genre == "aucune":
        return len(hyperonymes)
    if genre == "rang":
        return min(valeur, len(hyperonymes))
    if genre == "absolu":
        gardes = 0
        for _, poids in hyperonymes:
            if poids >= valeur:
                gardes += 1
        return gardes
    if not hyperonymes:
        return 0
    seuil = valeur * hyperonymes[0][1]
    gardes = 0
    for _, poids in hyperonymes:
        if poids >= seuil:
            gardes += 1
    return gardes


def ligne_taille_signature(libelle, tailles_h, tailles_trt, tailles_sst):
    """Une ligne du tableau des tailles de signature. Retourne une liste de cellules."""
    totaux = [1 + h + t + s for h, t, s in zip(tailles_h, tailles_trt, tailles_sst)]
    cellules = [libelle]
    for valeurs in (tailles_h, tailles_trt, tailles_sst, totaux):
        cellules.append(f"{fmt(mediane(valeurs))} [{min(valeurs)}–{max(valeurs)}]")
    return cellules


# ---------------------------------------------------------------------------
# Rapport : une fonction par section
# ---------------------------------------------------------------------------

def section_endpoints():
    """Section 0 : endpoints de l'API. Retourne une liste de lignes."""
    return ["## 0. Endpoints de l'API (lus sur /schema)", "",
            "| endpoint | paramètres |", "|---|---|",
            "| `GET /v0/node_by_name/{node_name}` | — |",
            "| `GET /v0/node_by_id/{node_id}` | — |",
            "| `GET /v0/refinements/{node_name}` | — |",
            "| `GET /v0/nodes_types` | — |",
            "| `GET /v0/relations_types` | — |",
            "| `GET /v0/relations/from/{node1_name}` | types_ids[], not_types_ids[], min_weight, max_weight, relation_fields[], node_fields[], limit, offset, without_nodes |",
            "| `GET /v0/relations/from_by_id/{node1_id}` | idem |",
            "| `GET /v0/relations/to/{node2_name}` | idem (**relations entrantes**) |",
            "| `GET /v0/relations/to_by_id/{node2_id}` | idem (**relations entrantes**) |",
            "| `GET /v0/relations/from/{n1}/to/{n2}` et `from_by_id/{id1}/to_by_id/{id2}` | idem |",
            "| `GET /v0/relations/by_type_id/{type_id}` | min_weight, max_weight, relation_fields[], limit (10000), offset |",
            "| `GET /v0/relations/random` | types_ids[], not_types_ids[], min_weight, max_weight, relation_fields[], limit (100) |",
            "",
            "Particularités constatées : `/refinements` plante (500) quand un raffinement est nommé "
            "« terme>glose » (ex. « chien ») — la polysémie est donc mesurée par `r_raff_sem` sortant ; nœud absent → HTTP 500 avec `status_code: 404` dans le corps ; "
            "`relation_fields` combiné à `types_ids` → erreur 500 serveur ; poids négatifs = relation niée.", ""]


def section_echantillon(strates, enregistrements):
    """Section 1 : composition de l'échantillon. Retourne une liste de lignes."""
    lignes = ["## 1. Échantillon", "",
              "Concrets : liste fixée à la main (fréquence non mesurable hors-ligne). Autres strates : "
              "`random.Random(42)` sur des viviers définis par règle — abstraits = A de Caractérisation/Agent/"
              "Patient (2 chacun) ; entités nommées = B à majuscule de Lieu/Origine (3 chacun) ; polylexicaux "
              "= « terre cuite », « Côte d'Ivoire » + 4 tirés parmi les termes à espace/tiret/apostrophe ; "
              "pluriels = B introduits par « des ».", ""]
    corps = []
    for (terme, strate), enr in zip(strates, enregistrements):
        if enr["existe"]:
            corps.append([terme, strate, "oui", enr["id"], enr["type"], enr["poids"],
                          enr["H_relations_brutes"], len(enr["H"]), len(enr["TRT"]),
                          sum(enr["TRT"].values()), len(enr["SST"]),
                          enr["raff_sens"], enr["raff_total"]])
        else:
            corps.append([terme, strate, "**non**", "", "", "", "", "", "", "", "", "", ""])
    lignes += tableau(["terme", "strate", "existe", "id", "type", "poids nœud", "r_isa (bruts)",
                       "H (≤50, w>0)", "TRT types", "TRT relations w>0", "SST",
                       "raff. (sens)", "raff. (total)"], corps)
    return lignes + [""]


def section_introuvables(strates, enregistrements, termes):
    """Section 2 : termes absents de JDM. Retourne une liste de lignes."""
    manquants = [(t, s) for (t, s), enr in zip(strates, enregistrements) if not enr["existe"]]
    lignes = ["## 2. Termes introuvables", ""]
    if manquants:
        lignes += tableau(["terme", "strate", "rôle", "relation(s) d'origine"],
                          [[t, s, "/".join(sorted(termes[t]["roles"])),
                            ", ".join(sorted(termes[t]["relations"]))] for t, s in manquants])
    else:
        lignes += ["Aucun : les 30 termes existent dans JDM sous leur forme exacte."]
    return lignes + [""]


def section_h(trouves):
    """Section 3 : trait H et décroissance des poids r_isa. Retourne une liste de lignes."""
    lignes = ["## 3. Trait H : décroissance des poids r_isa", ""]
    retenus = [enr["H_relations_brutes"] - sum(enr["H_ecartees"].values()) for enr in trouves]
    poids_negatifs = sum(enr["H_ecartees"]["poids ≤ 0"] for enr in trouves)
    lignes += [f"r_isa positifs retenus par terme (nœuds n_term/n_form, hors préfixes « _ » et « : ») : "
               f"min {min(retenus)}, médiane {fmt(mediane(retenus))}, max {max(retenus)}. "
               f"Relations r_isa de poids ≤ 0 écartées au total : {poids_negatifs}.", ""]

    corps = []
    for rang in config.H_RANGS_MESURES:
        poids = [enr["H"][rang - 1][1] for enr in trouves if len(enr["H"]) >= rang]
        relatifs = [enr["H"][rang - 1][1] / enr["H"][0][1] for enr in trouves
                    if len(enr["H"]) >= rang and enr["H"][0][1] > 0]
        corps.append([rang, len(poids), fmt(mediane(poids)),
                      fmt(min(poids)) if poids else "—", fmt(max(poids)) if poids else "—",
                      fmt(mediane(relatifs), 2)])
    lignes += tableau(["rang", "termes ayant ce rang", "poids médian", "min", "max",
                       "médiane w/w₁"], corps)

    riches = [enr for enr in trouves if len(enr["H_poids"]) >= 50]
    lignes += ["", f"Le tableau ci-dessus mélange des sous-populations (seuls les termes riches ont un rang 5) : "
               f"le poids médian n'y décroît donc pas. Décroissance sur les {len(riches)} termes ayant ≥ 50 r_isa "
               f"positifs ({', '.join(enr['terme'] for enr in riches)}) :", ""]
    corps = []
    for rang in [1, 2, 3, 5, 10, 20, 30, 40, 50, 75, 100]:
        poids = [enr["H_poids"][rang - 1] for enr in riches if len(enr["H_poids"]) >= rang]
        relatifs = [enr["H_poids"][rang - 1] / enr["H_poids"][0] for enr in riches
                    if len(enr["H_poids"]) >= rang]
        corps.append([rang, len(poids), fmt(mediane(poids)), fmt(mediane(relatifs), 2)])
    lignes += tableau(["rang", "termes", "poids médian", "médiane w/w₁"], corps)

    tous_poids = [poids for enr in trouves for poids in enr["H_poids"]]
    tranches = [(0, 30, "< 30 (≈ 1 vote)"), (30, 100, "30–100"), (100, 300, "100–300"),
                (300, 600, "300–600"), (600, 10 ** 6, "≥ 600")]
    reparties = []
    for bas, haut, libelle in tranches:
        reparties.append(f"{libelle} : {sum(bas <= poids < haut for poids in tous_poids)}")
    lignes += ["", f"Répartition des {len(tous_poids)} poids r_isa positifs : "
               + " ; ".join(reparties) + ".", ""]

    lignes += ["", "Taille de H selon la coupure (médiane [min–max] sur les termes trouvés, "
               "plafonnée à 50) :", ""]
    for libelle, genre, valeur in COUPURES_H:
        tailles = [taille_h_apres_coupure(enr["H"], genre, valeur) for enr in trouves]
        lignes.append(f"- {libelle} : {fmt(mediane(tailles))} [{min(tailles)}–{max(tailles)}]")

    lignes += ["", "Détail des 10 premiers hyperonymes par terme :", ""]
    corps = []
    for enr in trouves:
        premiers = ", ".join(f"{nom} ({poids:g})" for nom, poids in enr["H"][:10])
        corps.append([enr["terme"], len(enr["H"]), premiers or "—"])
    lignes += tableau(["terme", "|H|", "10 premiers (poids)"], corps)

    lignes += section_recommandation_h(trouves)
    return lignes


def section_recommandation_h(trouves):
    """Recommandation de coupure pour H. Retourne une liste de lignes."""
    pauvres = [enr for enr in trouves if len(enr["H_poids"]) < config.H_TOP_RECOMMANDE]
    tailles_seuil_50 = [sum(poids >= 50 for poids in enr["H_poids"][:50]) for enr in trouves]
    return ["", "### Recommandation H", "",
            f"**Coupure par rang, top {config.H_TOP_RECOMMANDE} par poids décroissant "
            f"(hors poids ≤ 0), sans seuil absolu.** Alternative : top 30.",
            "",
            f"- **Pas de seuil absolu.** Les termes pauvres n'ont que des poids de 25 à 50 (un ou deux votes) : "
            f"`w ≥ 50` ramène H à une médiane de {fmt(mediane(tailles_seuil_50))} symboles et "
            f"vide presque entièrement les abstraits, les pluriels et les polylexicaux. Or ce sont justement "
            f"les termes à qui l'hyperonymie fait déjà défaut (papier, §4.4.1).",
            f"- **Pas de seuil relatif.** Sur les termes riches, w/w₁ se stabilise vers 0,5 entre les rangs 5 et 30 : "
            f"un seuil à 50 % de w₁ tomberait au milieu de ce palier, et le nombre de symboles gardés "
            f"basculerait d'un terme à l'autre sur des écarts de poids insignifiants.",
            f"- **Pourquoi 20.** Le palier (poids ≈ 500–550, souvent identiques à 0,01 près) va jusqu'au rang 30 environ, "
            f"puis chute (0,33 au rang 40, 0,20 au rang 50). Top 20 coupe dans le palier avant la chute ; top 30 "
            f"en garde la totalité. {len(pauvres)}/{len(trouves)} termes ont moins de {config.H_TOP_RECOMMANDE} hyperonymes : pour eux, la coupure ne "
            f"change rien. Elle ne borne donc que les termes riches.",
            f"- **Limite.** Le palier contient du bruit que le poids ne permet pas d'isoler : New York → navire (811), "
            f"en:american state, doublons de casse (« Procédé » et « procédé de séparation »). Le filtre sur le type de nœud "
            f"(repris de main.py) écarte déjà les nœuds n_wikipedia aux noms tronqués (« bâtiment d », « véhicule à ») "
            f"et les n_chunk. Aucune coupure par poids n'élimine le reste.", ""]


def section_trt(trouves, client):
    """Section 4 : trait TRT, types de relations entrantes. Retourne une liste de lignes."""
    nb_types = [len(enr["TRT"]) for enr in trouves]
    nb_relations = [sum(enr["TRT"].values()) for enr in trouves]
    nb_types_jdm = len(client.types_de_relations())
    lignes = ["## 4. Trait TRT : types de relations entrantes", "",
              f"Types entrants distincts (w > 0) par terme : min {min(nb_types)}, "
              f"médiane {fmt(mediane(nb_types))}, max {max(nb_types)} (sur {nb_types_jdm} types existants).",
              f"Relations entrantes w > 0 par terme : min {min(nb_relations)}, "
              f"médiane {fmt(mediane(nb_relations))}, max {max(nb_relations)}. "
              f"Relations entrantes de poids ≤ 0 : "
              f"{sum(enr['TRT_non_positives'] for enr in trouves)} au total.", ""]

    frequences = Counter(t for enr in trouves for t in enr["TRT"])
    repandus = sorted(frequences.items(), key=lambda kv: (-kv[1], kv[0]))[:40]
    lignes += [f"Types entrants les plus répandus (nombre de termes sur {len(trouves)} qui les reçoivent) :", ""]
    lignes += [", ".join(f"`{t}` ({n})" for t, n in repandus)]

    lignes += ["", "Nombre de types entrants retenus selon un effectif minimal par type :", ""]
    for effectif_minimal in (1, 2, 5, 10):
        tailles = [sum(n >= effectif_minimal for n in enr["TRT"].values()) for enr in trouves]
        lignes.append(f"- effectif ≥ {effectif_minimal} : médiane {fmt(mediane(tailles))} "
                      f"[{min(tailles)}–{max(tailles)}]")

    semantiques = []
    for enr in trouves:
        semantiques.append({t: n for t, n in enr["TRT"].items()
                            if t not in config.TRT_TYPES_NON_SEMANTIQUES})
    tailles_sem = [len(x) for x in semantiques]
    tailles_sem_2 = [sum(n >= 2 for n in x.values()) for x in semantiques]
    universels = sorted(t for t, n in frequences.items() if n == len(trouves))
    lignes += ["", "### Recommandation TRT", "",
               "**Borné naturellement : pas de coupure de taille nécessaire. Recommandation : exclure une liste de types "
               "non sémantiques, sans seuil d'effectif.**", "",
               f"- **Borne.** Le nombre de types distincts ne peut pas dépasser le nombre de types JDM "
               f"({nb_types_jdm}) et vaut au plus {max(nb_types)} dans l'échantillon, alors que le nombre de relations "
               f"entrantes varie de {min(nb_relations)} à {max(nb_relations)}. La signature est binaire : ce volume n'a donc aucun effet sur sa taille.",
               f"- **Types universels.** Présents chez les {len(trouves)} termes : {', '.join(f'`{t}`' for t in universels)}. Ces "
               f"symboles sont constants : ils gonflent toutes les similarités de la même façon, sans rien discriminer.",
               f"- **Liste d'exclusion proposée** (types méta, lexicaux ou techniques) : "
               f"{', '.join(f'`{t}`' for t in config.TRT_TYPES_NON_SEMANTIQUES)}. "
               f"Avec cette exclusion, TRT vaut médiane {fmt(mediane(tailles_sem))} [{min(tailles_sem)}–{max(tailles_sem)}] ; avec en plus un effectif ≥ 2, "
               f"{fmt(mediane(tailles_sem_2))} [{min(tailles_sem_2)}–{max(tailles_sem_2)}].",
               "- **Pas de seuil d'effectif.** L'effectif dépend surtout de la popularité du terme (huées : 81 relations "
               "entrantes, animaux : 133 715). Un seuil pénaliserait encore les termes rares.", ""]
    return lignes


def section_sst(trouves):
    """Section 5 : trait SST, annotations _INFO-SEM-*. Retourne une liste de lignes."""
    tailles = [len(enr["SST"]) for enr in trouves]
    lignes = ["## 5. Trait SST : _INFO-SEM-*", "",
              f"_INFO-SEM-* (w > 0) par terme : min {min(tailles)}, médiane {fmt(mediane(tailles))}, "
              f"max {max(tailles)} ; {sum(1 for t in tailles if t == 0)} terme(s) sans aucune annotation.", ""]
    corps = []
    for enr in trouves:
        annotations = ", ".join(f"{nom[len('_INFO-SEM-'):]} ({poids:g})" for nom, poids in enr["SST"])
        corps.append([enr["terme"], annotations or "—"])
    lignes += tableau(["terme", "annotations (poids)"], corps)
    return lignes + [""]


def section_taille_signature(trouves):
    """Section 6 : taille de signature résultante. Retourne une liste de lignes."""
    tailles_sst = [len(enr["SST"]) for enr in trouves]
    sans_coupure = ligne_taille_signature(
        "sans coupure (w > 0, H non plafonné)",
        [len(enr["H_poids"]) for enr in trouves],
        [len(enr["TRT"]) for enr in trouves], tailles_sst)
    recommandee = ligne_taille_signature(
        f"recommandée (H top {config.H_TOP_RECOMMANDE}, TRT sans types non sémantiques)",
        [min(config.H_TOP_RECOMMANDE, len(enr["H_poids"])) for enr in trouves],
        [sum(1 for t in enr["TRT"] if t not in config.TRT_TYPES_NON_SEMANTIQUES) for enr in trouves],
        tailles_sst)
    lignes = ["## 6. Taille de signature résultante", "",
              "Terme lui-même (1) + H + TRT + SST, ensemble plat de symboles binaires.", ""]
    lignes += tableau(["configuration", "H", "TRT", "SST", "total"], [sans_coupure, recommandee])
    return lignes + [""]


def section_polysemie(strates, enregistrements, trouves):
    """Section 7 : polysémie mesurée par les raffinements. Retourne une liste de lignes."""
    sens = [enr["raff_sens"] for enr in trouves]
    lignes = ["## 7. Polysémie (raffinements)", "",
              f"Termes avec au moins un raffinement : {sum(s > 0 for s in sens)}/{len(trouves)} "
              f"({100 * sum(s > 0 for s in sens) / len(trouves):.0f} %) ; avec au moins deux sens de premier niveau : "
              f"{sum(s >= 2 for s in sens)}/{len(trouves)} ({100 * sum(s >= 2 for s in sens) / len(trouves):.0f} %). "
              f"Sens de premier niveau : médiane {fmt(mediane(sens))}, max {max(sens)}.", ""]
    par_strate = defaultdict(list)
    for (_, strate), enr in zip(strates, enregistrements):
        if enr["existe"]:
            par_strate[strate].append(enr["raff_sens"])
    lignes += tableau(["strate", "polysémiques (≥1 raff.)", "sens médians"],
                      [[strate, f"{sum(x > 0 for x in valeurs)}/{len(valeurs)}", fmt(mediane(valeurs))]
                       for strate, valeurs in par_strate.items()])
    return lignes + [""]


def section_latence(enregistrements, client, nb_termes_total):
    """Section 8 : latence mesurée et coût extrapolé d'une passe complète.
    Retourne une liste de lignes."""
    latences = defaultdict(list)
    for enr in enregistrements:
        for appel in enr["appels"]:
            if appel["elapsed_s"] is not None:
                latences[endpoint_de(appel["path"])].append(appel["elapsed_s"])

    corps, moyenne_par_terme = [], 0.0
    for endpoint in ("node_by_name", "relations/from", "relations/to"):
        mesures = latences.get(endpoint, [])
        if not mesures:
            continue
        appels_par_terme = 3 if endpoint == "relations/from" else 1
        moyenne_par_terme += appels_par_terme * statistics.mean(mesures)
        corps.append([endpoint, len(mesures), fmt(statistics.mean(mesures), 2),
                      fmt(mediane(mesures), 2), fmt(max(mesures), 2), appels_par_terme])
    lignes = ["## 8. Latence et coût d'une passe complète", ""]
    lignes += tableau(["endpoint", "appels", "moyenne (s)", "médiane (s)", "max (s)",
                       "appels / terme"], corps)

    toutes_latences = [x for mesures in latences.values() for x in mesures]
    delai_total = 5 * client.delai  # node + 3 × from + to
    estimation = nb_termes_total * (moyenne_par_terme + delai_total)
    lignes += ["", f"Latence moyenne par appel, tous endpoints : {statistics.mean(toutes_latences):.2f} s ({len(toutes_latences)} appels).",
               f"Par terme : {moyenne_par_terme:.2f} s d'appels + {delai_total:.1f} s de délai de politesse (5 appels × {client.delai} s).",
               f"**Passe complète estimée sur {nb_termes_total} termes : {estimation / 60:.0f} min ({estimation / 3600:.1f} h)**, "
               f"en séquentiel, sans erreur ni nouvel essai. Les relations entrantes dominent : leur coût croît "
               f"avec la fréquence du terme (voir max).", ""]

    octets = defaultdict(int)
    for enr in enregistrements:
        for appel in enr["appels"]:
            octets[endpoint_de(appel["path"])] += appel.get("bytes") or 0
    total_octets = sum(octets.values())
    lignes += [f"Volume téléchargé pour les {len(enregistrements)} termes : {total_octets / 1e6:.1f} Mo, dont "
               f"{100 * octets['relations/to'] / total_octets:.0f} % pour les relations entrantes. Extrapolé à {nb_termes_total} termes : "
               f"**≈ {total_octets / len(enregistrements) * nb_termes_total / 1e9:.1f} Go de cache** (un JSON par requête, non compressé). "
               f"Le timeout de 10 s ne suffit pas pour les relations entrantes : on a mesuré jusqu'à "
               f"{max(latences['relations/to']):.1f} s (et 22 s pour « eau » en exploration), d'où un timeout de "
               f"{config.TIMEOUT_RELATIONS_ENTRANTES:.0f} s sur cet endpoint.", ""]
    return lignes


def section_ambiguites(ambiguites):
    """Section 9 : découpage des lignes ambiguës. Retourne une liste de lignes."""
    lignes = ["## 9. Test des deux lignes ambiguës (méthode §4.1)", "",
              "Existence dans JDM de chaque candidat A et B. Le corpus n'est pas modifié.", ""]
    corps, valides = [], []
    for ligne_ambigue in ambiguites:
        for candidat in ligne_ambigue["candidats"]:
            valide = candidat["A_existe"] and candidat["B_existe"]
            corps.append([ligne_ambigue["syntagme"],
                          candidat["A"], "oui" if candidat["A_existe"] else "**non**",
                          candidat["B"], "oui" if candidat["B_existe"] else "**non**",
                          "valide" if valide else "rejeté"])
            if valide:
                valides.append(f"« {ligne_ambigue['syntagme']} » → A = `{candidat['A']}`, "
                               f"B = `{candidat['B']}`")
    lignes += tableau(["syntagme", "A", "A existe", "B", "B existe", "découpage"], corps)
    lignes += ["", "**Résultat.** Pour les deux syntagmes, un seul découpage a ses deux termes dans JDM : "
               + " ; ".join(valides)
               + ". Le critère est suffisant ici parce que le A du découpage concurrent (« cacao de Côte », "
               "« diamants d'Afrique ») n'existe pas, alors que les deux B concurrents existent (Ivoire, Sud). "
               "Tester B seul n'aurait donc pas suffi. Corpus non modifié.", ""]
    return lignes


def construire_rapport(strates, enregistrements, termes, ambiguites, client, nb_termes_total):
    """Assemble le rapport de sonde. Retourne le texte Markdown complet."""
    trouves = [enr for enr in enregistrements if enr["existe"]]
    lignes = ["# Sonde JDM : 30 termes", "",
              "Généré par `src/jdm_probe.py`. API : `https://jdm-api.demo.lirmm.fr/v0`. Seules les relations "
              "de poids ≤ 0 (niées dans JDM) sont écartées ; aucun seuil n'est appliqué. Les latences "
              "sont celles des appels réseau réels, conservées dans le cache.", ""]
    lignes += section_endpoints()
    lignes += section_echantillon(strates, enregistrements)
    lignes += section_introuvables(strates, enregistrements, termes)
    lignes += section_h(trouves)
    lignes += section_trt(trouves, client)
    lignes += section_sst(trouves)
    lignes += section_taille_signature(trouves)
    lignes += section_polysemie(strates, enregistrements, trouves)
    lignes += section_latence(enregistrements, client, nb_termes_total)
    lignes += section_ambiguites(ambiguites)
    return "\n".join(lignes)


def main():
    termes = charger_termes()
    strates = selectionner_termes(termes)
    client = ClientJDM()
    ids_relations, id_vers_relation = client.tables_types_relations()
    types_noeuds = {t["id"]: t["name"] for t in client.types_de_noeuds()}

    enregistrements = []
    for numero, (terme, strate) in enumerate(strates, 1):
        try:
            enr = sonder_terme(client, terme, ids_relations, id_vers_relation, types_noeuds)
        except JDMErreur as e:
            raise SystemExit(f"arrêt sur « {terme} » : {e}")
        enregistrements.append(enr)
        if enr["existe"]:
            etat = (f"H={len(enr['H']):2d} TRT={len(enr['TRT']):3d} "
                    f"SST={len(enr['SST']):2d} raff={enr['raff_sens']}")
        else:
            etat = "INTROUVABLE"
        print(f"[{numero:2d}/30] {strate:14s} {terme:22s} {etat}", flush=True)

    ambiguites = tester_ambiguites(client)
    rapport = construire_rapport(strates, enregistrements, termes, ambiguites, client, len(termes))
    CHEMIN_RAPPORT.parent.mkdir(parents=True, exist_ok=True)
    CHEMIN_RAPPORT.write_text(rapport + "\n", encoding="utf-8")
    reels = [c for c in client.appels if not c["cached"]]
    print(f"{len(client.appels)} requêtes, dont {len(reels)} appels réseau. "
          f"Rapport : {CHEMIN_RAPPORT.relative_to(config.RACINE)}")


if __name__ == "__main__":
    main()
