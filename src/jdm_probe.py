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
from pathlib import Path

from corpus_check import split_candidates
from jdm_client import JDMClient, JDMError, JDMNotFound, resolve_refinement_name

ROOT = Path(__file__).resolve().parent.parent
TERMS_PATH = ROOT / "data" / "corpus" / "clean" / "termes.csv"
CLEAN_DIR = ROOT / "data" / "corpus" / "clean"
REPORT_PATH = ROOT / "reports" / "rapport_sonde_jdm.md"

SEED = 42
PER_STRATUM = 6
H_TOP = 50
H_RANKS = [1, 5, 10, 20, 30, 50]
# Timeout des relations entrantes : « eau » en a 165 004 et répond en ~22 s.
TIMEOUT_INCOMING = 60.0
AMBIGUOUS = ["cacao de Côte d'Ivoire", "diamants d'Afrique du Sud"]

# Filtrage paramétrable par trait. Les filtres de main.py (préfixes « _ » et « : »,
# nœuds n_term/n_form uniquement) valent pour H, mais pas globalement : les
# _INFO-SEM-* sont des nœuds n_data_pot préfixés « _ », et ils SONT le trait SST.
# node_types : ids de types de nœuds admis (None = tous).
TRAIT_FILTERS = {
    "H": {"direction": "out", "relation": "r_isa", "node_types": (1, 2),  # n_term, n_form
          "include_prefixes": None, "exclude_prefixes": ("_", ":"), "min_weight_exclusive": 0},
    "SST": {"direction": "out", "relation": "r_infopot", "node_types": None,
            "include_prefixes": ("_INFO-SEM-",), "exclude_prefixes": (), "min_weight_exclusive": 0},
    # TRT : symboles = noms de types de relations entrantes ; aucun type exclu à ce stade.
    "TRT": {"direction": "in", "exclude_relation_types": (), "min_weight_exclusive": 0},
}

# Types entrants non sémantiques (méta, lexicaux, techniques) : candidats à l'exclusion du trait TRT.
# Proposition soumise à décision, non appliquée aux mesures brutes.
TRT_NON_SEMANTIC = (
    "r_aki", "r_wiki", "r_associated", "r_context", "r_variante", "r_translation", "r_lemma",
    "r_meaning/glose", "r_raff_sem-1", "r_sing_form", "r_der_morpho", "r_masc", "r_homophone",
    "r_locution", "r_error",
)
H_RECO_K = 20

# Strate 1 : pas de mesure de fréquence hors-ligne, donc liste explicite (vérifiée ci-dessous).
CONCRETE = ["voiture", "maison", "pain", "chien", "vélo", "bateau"]
POLYLEX_FORCED = ["terre cuite", "Côte d'Ivoire"]


# ---------------------------------------------------------------------------
# Sélection des 30 termes
# ---------------------------------------------------------------------------

def load_terms():
    terms = defaultdict(lambda: {"roles": set(), "relations": set(), "by_role": defaultdict(set), "occ": 0})
    with open(TERMS_PATH, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            t = terms[row["terme"]]
            t["roles"].add(row["role"])
            t["relations"].update(row["relations_associees"].split("|"))
            if int(row["nb_occurrences"]) > 0:
                t["by_role"][row["role"]].update(row["relations_associees"].split("|"))
            t["occ"] += int(row["nb_occurrences"])
    return terms


def plural_b_terms():
    """Termes B introduits par « des » : pluriel certain (contrairement à un -s final)."""
    out = set()
    for path in sorted(CLEAN_DIR.glob("corpus_*.csv")):
        with open(path, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                if row["ambigu"] == "non" and f" des {row['B']}" in f" {row['syntagme']}":
                    out.add(row["B"])
    return out


def is_polylex(term):
    return any(ch in term for ch in " -'’")


def select_terms(terms):
    rng = random.Random(SEED)
    chosen, strata = set(), []

    def draw(label, pool, k):
        pool = sorted(t for t in pool if t not in chosen)
        assert len(pool) >= k, f"strate {label} : {len(pool)} candidats pour {k}"
        picked = sorted(rng.sample(pool, k))
        chosen.update(picked)
        strata.extend((t, label) for t in picked)

    missing = [t for t in CONCRETE + POLYLEX_FORCED if t not in terms]
    assert not missing, f"absents de termes.csv : {missing}"
    chosen.update(CONCRETE)
    strata.extend((t, "concret") for t in CONCRETE)

    def with_role(role, rel):
        return [t for t, v in terms.items() if rel in v["by_role"][role]]

    for rel in ("r_has_property-1", "r_processus_agent", "r_processus_patient"):
        draw("abstrait", [t for t in with_role("A", rel) if not is_polylex(t)], 2)
    for rel in ("r_lieu", "r_lieu>origine"):
        draw("entité nommée", [t for t in with_role("B", rel) if t[:1].isupper() and not is_polylex(t)], 3)

    chosen.update(POLYLEX_FORCED)
    strata.extend((t, "polylexical") for t in POLYLEX_FORCED)
    # Les termes nés d'un découpage ambigu (« cacao de Côte ») ne sont pas de vrais polylexicaux.
    draw("polylexical", [t for t, v in terms.items() if is_polylex(t) and v["occ"] > 0],
         PER_STRATUM - len(POLYLEX_FORCED))
    draw("pluriel", [t for t in plural_b_terms() if not is_polylex(t) and not t[:1].isupper()], PER_STRATUM)

    assert len(strata) == 30 and len({t for t, _ in strata}) == 30
    return strata


# ---------------------------------------------------------------------------
# Mesures par terme
# ---------------------------------------------------------------------------

def keep_symbol(name, weight, node_type, flt):
    if weight <= flt["min_weight_exclusive"]:
        return False
    if flt.get("node_types") and node_type not in flt["node_types"]:
        return False
    if flt.get("include_prefixes") and not name.startswith(tuple(flt["include_prefixes"])):
        return False
    if flt.get("exclude_prefixes") and name.startswith(tuple(flt["exclude_prefixes"])):
        return False
    return True


def outgoing_symbols(client, term, rel_id, flt):
    data = client.relations_from(term, types_ids=[rel_id])
    names = {n["id"]: n["name"] for n in data["nodes"]}
    ntypes = {n["id"]: n.get("type") for n in data["nodes"]}
    rels = [r for r in data["relations"] if r["type"] == rel_id]
    kept, dropped = [], Counter()
    for r in sorted(rels, key=lambda r: (-r["w"], names.get(r["node2"], ""))):
        raw = names.get(r["node2"], str(r["node2"]))
        if r["w"] <= flt["min_weight_exclusive"]:
            dropped["poids ≤ 0"] += 1
        elif not keep_symbol(raw, r["w"], ntypes.get(r["node2"]), flt):
            dropped["type de nœud ou préfixe"] += 1
        else:
            kept.append((resolve_refinement_name(raw, names, client), r["w"]))
    return kept, len(rels), dropped


def probe_term(client, term, rel_ids, id_to_rel, node_types):
    rec = {"term": term, "calls_start": len(client.calls)}
    try:
        node = client.node_by_name(term)
    except JDMNotFound:
        rec["exists"] = False
        rec["calls"] = client.calls[rec.pop("calls_start"):]
        return rec
    rec.update(exists=True, id=node["id"], type=node_types.get(node.get("type"), node.get("type")),
               w=node.get("w"), name_jdm=node["name"])

    rec["H"], rec["H_total"], rec["H_dropped"] = outgoing_symbols(
        client, term, rel_ids["r_isa"], TRAIT_FILTERS["H"])
    rec["H_all_w"] = [w for _, w in rec["H"]]
    rec["H"] = rec["H"][:H_TOP]

    sst, rec["SST_total"], rec["SST_dropped"] = outgoing_symbols(
        client, term, rel_ids["r_infopot"], TRAIT_FILTERS["SST"])
    rec["SST"] = sst

    flt = TRAIT_FILTERS["TRT"]
    data = client.relations_to(term, timeout=TIMEOUT_INCOMING, without_nodes=True,
                               relation_fields=["type", "w"])
    trt, neg = Counter(), 0
    for r in data["relations"]:
        tname = id_to_rel.get(r["type"], str(r["type"]))
        if r.get("w", 0) <= flt["min_weight_exclusive"]:
            neg += 1
        elif tname not in flt["exclude_relation_types"]:
            trt[tname] += 1
    rec["TRT"], rec["TRT_total"], rec["TRT_nonpositive"] = trt, len(data["relations"]), neg

    # Raffinements via r_raff_sem sortant plutôt que /refinements, qui plante côté serveur
    # dès qu'un raffinement est nommé « terme>glose » au lieu de « terme>id » (ex. « chien »).
    data = client.relations_from(term, types_ids=[rel_ids["r_raff_sem"]])
    names = {n["id"]: n["name"] for n in data["nodes"]}
    refs = [names.get(r["node2"], "") for r in data["relations"]
            if r["type"] == rel_ids["r_raff_sem"] and r["w"] > 0]
    refs = [x for x in refs if x.startswith(node["name"] + ">")]
    rec["raff_senses"] = sum(1 for x in refs if x.count(">") == 1)
    rec["raff_total"] = len(refs)

    rec["calls"] = client.calls[rec.pop("calls_start"):]
    return rec


def ambiguity_test(client):
    out = []
    for syntagme in AMBIGUOUS:
        cands = []
        for c in split_candidates(syntagme):
            cands.append({"A": c["A"], "B": c["B"], "A_exists": client.exists(c["A"]),
                          "B_exists": client.exists(c["B"])})
        out.append({"syntagme": syntagme, "whole_exists": client.exists(syntagme), "cands": cands})
    return out


# ---------------------------------------------------------------------------
# Rapport
# ---------------------------------------------------------------------------

def med(values):
    return statistics.median(values) if values else None


def fmt(x, nd=1):
    if x is None:
        return "—"
    return f"{x:.{nd}f}" if isinstance(x, float) else str(x)


def table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(str(c).replace("|", "\\|") for c in r) + " |" for r in rows]
    return out


def endpoint_of(path):
    if path.startswith("/relations/from/"):
        return "relations/from"
    if path.startswith("/relations/to/"):
        return "relations/to"
    return path.strip("/").split("/")[0]


def build_report(strata, recs, terms, amb, client, n_terms_total):
    found = [r for r in recs if r["exists"]]
    L = ["# Sonde JDM : 30 termes", "",
         "Généré par `src/jdm_probe.py`. API : `https://jdm-api.demo.lirmm.fr/v0`. Seules les relations "
         "de poids ≤ 0 (niées dans JDM) sont écartées ; aucun seuil n'est appliqué. Les latences "
         "sont celles des appels réseau réels, conservées dans le cache.", ""]

    # --- Endpoints -----------------------------------------------------------
    L += ["## 0. Endpoints de l'API (lus sur /schema)", "",
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

    # --- Échantillon ---------------------------------------------------------
    L += ["## 1. Échantillon", "",
          "Concrets : liste fixée à la main (fréquence non mesurable hors-ligne). Autres strates : "
          "`random.Random(42)` sur des viviers définis par règle — abstraits = A de Caractérisation/Agent/"
          "Patient (2 chacun) ; entités nommées = B à majuscule de Lieu/Origine (3 chacun) ; polylexicaux "
          "= « terre cuite », « Côte d'Ivoire » + 4 tirés parmi les termes à espace/tiret/apostrophe ; "
          "pluriels = B introduits par « des ».", ""]
    body = []
    for (t, stratum), r in zip(strata, recs):
        if r["exists"]:
            trt_types = len(r["TRT"])
            body.append([t, stratum, "oui", r["id"], r["type"], r["w"], r["H_total"], len(r["H"]),
                         trt_types, sum(r["TRT"].values()), len(r["SST"]), r["raff_senses"], r["raff_total"]])
        else:
            body.append([t, stratum, "**non**", "", "", "", "", "", "", "", "", "", ""])
    L += table(["terme", "strate", "existe", "id", "type", "poids nœud", "r_isa (bruts)", "H (≤50, w>0)",
                "TRT types", "TRT relations w>0", "SST", "raff. (sens)", "raff. (total)"], body)
    L += [""]

    # --- Introuvables ----------------------------------------------------------
    missing = [(t, s) for (t, s), r in zip(strata, recs) if not r["exists"]]
    L += ["## 2. Termes introuvables", ""]
    if missing:
        L += table(["terme", "strate", "rôle", "relation(s) d'origine"],
                   [[t, s, "/".join(sorted(terms[t]["roles"])), ", ".join(sorted(terms[t]["relations"]))]
                    for t, s in missing])
    else:
        L += ["Aucun : les 30 termes existent dans JDM sous leur forme exacte."]
    L += [""]

    # --- H ------------------------------------------------------------------
    L += ["## 3. Trait H : décroissance des poids r_isa", ""]
    L += [f"r_isa positifs retenus par terme (nœuds n_term/n_form, hors préfixes « _ » et « : ») : min {min(r['H_total'] - sum(r['H_dropped'].values()) for r in found)}, "
          f"médiane {fmt(med([r['H_total'] - sum(r['H_dropped'].values()) for r in found]))}, "
          f"max {max(r['H_total'] - sum(r['H_dropped'].values()) for r in found)}. "
          f"Relations r_isa de poids ≤ 0 écartées au total : {sum(r['H_dropped']['poids ≤ 0'] for r in found)}.", ""]
    body = []
    for k in H_RANKS:
        ws = [r["H"][k - 1][1] for r in found if len(r["H"]) >= k]
        rel = [r["H"][k - 1][1] / r["H"][0][1] for r in found if len(r["H"]) >= k and r["H"][0][1] > 0]
        body.append([k, len(ws), fmt(med(ws)), fmt(min(ws)) if ws else "—", fmt(max(ws)) if ws else "—",
                     fmt(med(rel), 2)])
    L += table(["rang", "termes ayant ce rang", "poids médian", "min", "max", "médiane w/w₁"], body)
    rich = [r for r in found if len(r["H_all_w"]) >= 50]
    L += ["", f"Le tableau ci-dessus mélange des sous-populations (seuls les termes riches ont un rang 5) : "
          f"le poids médian n'y décroît donc pas. Décroissance sur les {len(rich)} termes ayant ≥ 50 r_isa "
          f"positifs ({', '.join(r['term'] for r in rich)}) :", ""]
    body = []
    for k in [1, 2, 3, 5, 10, 20, 30, 40, 50, 75, 100]:
        ws = [r["H_all_w"][k - 1] for r in rich if len(r["H_all_w"]) >= k]
        rel = [r["H_all_w"][k - 1] / r["H_all_w"][0] for r in rich if len(r["H_all_w"]) >= k]
        body.append([k, len(ws), fmt(med(ws)), fmt(med(rel), 2)])
    L += table(["rang", "termes", "poids médian", "médiane w/w₁"], body)
    allw = [w for r in found for w in r["H_all_w"]]
    buckets = [(0, 30, "< 30 (≈ 1 vote)"), (30, 100, "30–100"), (100, 300, "100–300"),
               (300, 600, "300–600"), (600, 10 ** 6, "≥ 600")]
    L += ["", f"Répartition des {len(allw)} poids r_isa positifs : "
          + " ; ".join(f"{lab} : {sum(lo <= w < hi for w in allw)}" for lo, hi, lab in buckets) + ".", ""]
    L += ["", "Taille de H selon la coupure (médiane [min–max] sur les termes trouvés, plafonnée à 50) :", ""]
    body = []
    for label, fn in [
        ("aucune (w > 0)", lambda h: len(h)),
        ("top 10", lambda h: min(10, len(h))),
        ("top 20", lambda h: min(20, len(h))),
        ("w ≥ 50", lambda h: sum(w >= 50 for _, w in h)),
        ("w ≥ 100", lambda h: sum(w >= 100 for _, w in h)),
        ("w ≥ 25 % de w₁", lambda h: sum(w >= 0.25 * h[0][1] for _, w in h) if h else 0),
        ("w ≥ 50 % de w₁", lambda h: sum(w >= 0.5 * h[0][1] for _, w in h) if h else 0),
    ]:
        sizes = [fn(r["H"]) for r in found]
        L.append(f"- {label} : {fmt(med(sizes))} [{min(sizes)}–{max(sizes)}]")
    L += ["", "Détail des 10 premiers hyperonymes par terme :", ""]
    body = [[r["term"], len(r["H"]), ", ".join(f"{n} ({w:g})" for n, w in r["H"][:10]) or "—"] for r in found]
    L += table(["terme", "|H|", "10 premiers (poids)"], body)
    sparse = [r for r in found if len(r["H_all_w"]) < H_RECO_K]
    L += ["", "### Recommandation H", "",
          f"**Coupure par rang, top {H_RECO_K} par poids décroissant (hors poids ≤ 0), sans seuil absolu.** Alternative : top 30.",
          "",
          f"- **Pas de seuil absolu.** Les termes pauvres n'ont que des poids de 25 à 50 (un ou deux votes) : "
          f"`w ≥ 50` ramène H à une médiane de {fmt(med([sum(w >= 50 for w in r['H_all_w'][:50]) for r in found]))} symboles et "
          f"vide presque entièrement les abstraits, les pluriels et les polylexicaux. Or ce sont justement "
          f"les termes à qui l'hyperonymie fait déjà défaut (papier, §4.4.1).",
          f"- **Pas de seuil relatif.** Sur les termes riches, w/w₁ se stabilise vers 0,5 entre les rangs 5 et 30 : "
          f"un seuil à 50 % de w₁ tomberait au milieu de ce palier, et le nombre de symboles gardés "
          f"basculerait d'un terme à l'autre sur des écarts de poids insignifiants.",
          f"- **Pourquoi 20.** Le palier (poids ≈ 500–550, souvent identiques à 0,01 près) va jusqu'au rang 30 environ, "
          f"puis chute (0,33 au rang 40, 0,20 au rang 50). Top 20 coupe dans le palier avant la chute ; top 30 "
          f"en garde la totalité. {len(sparse)}/{len(found)} termes ont moins de {H_RECO_K} hyperonymes : pour eux, la coupure ne "
          f"change rien. Elle ne borne donc que les termes riches.",
          f"- **Limite.** Le palier contient du bruit que le poids ne permet pas d'isoler : New York → navire (811), "
          f"en:american state, doublons de casse (« Procédé » et « procédé de séparation »). Le filtre sur le type de nœud "
          f"(repris de main.py) écarte déjà les nœuds n_wikipedia aux noms tronqués (« bâtiment d », « véhicule à ») "
          f"et les n_chunk. Aucune coupure par poids n'élimine le reste.", ""]

    # --- TRT ----------------------------------------------------------------
    L += ["## 4. Trait TRT : types de relations entrantes", ""]
    n_types = [len(r["TRT"]) for r in found]
    n_rel = [sum(r["TRT"].values()) for r in found]
    L += [f"Types entrants distincts (w > 0) par terme : min {min(n_types)}, médiane {fmt(med(n_types))}, "
          f"max {max(n_types)} (sur {len(client.relation_types())} types existants).",
          f"Relations entrantes w > 0 par terme : min {min(n_rel)}, médiane {fmt(med(n_rel))}, max {max(n_rel)}. "
          f"Relations entrantes de poids ≤ 0 : {sum(r['TRT_nonpositive'] for r in found)} au total.", ""]
    freq = Counter(t for r in found for t in r["TRT"])
    L += ["Types entrants les plus répandus (nombre de termes sur " + str(len(found)) + " qui les reçoivent) :", ""]
    L += [", ".join(f"`{t}` ({n})" for t, n in sorted(freq.items(), key=lambda x: (-x[1], x[0]))[:40])]
    L += ["", "Nombre de types entrants retenus selon un effectif minimal par type :", ""]
    for mn in (1, 2, 5, 10):
        sizes = [sum(c >= mn for c in r["TRT"].values()) for r in found]
        L.append(f"- effectif ≥ {mn} : médiane {fmt(med(sizes))} [{min(sizes)}–{max(sizes)}]")
    sem = [{t: n for t, n in r["TRT"].items() if t not in TRT_NON_SEMANTIC} for r in found]
    s1 = [len(x) for x in sem]
    s2 = [sum(n >= 2 for n in x.values()) for x in sem]
    universal = sorted(t for t, n in freq.items() if n == len(found))
    L += ["", "### Recommandation TRT", "",
          "**Borné naturellement : pas de coupure de taille nécessaire. Recommandation : exclure une liste de types "
          "non sémantiques, sans seuil d'effectif.**", "",
          f"- **Borne.** Le nombre de types distincts ne peut pas dépasser le nombre de types JDM "
          f"({len(client.relation_types())}) et vaut au plus {max(n_types)} dans l'échantillon, alors que le nombre de relations "
          f"entrantes varie de {min(n_rel)} à {max(n_rel)}. La signature est binaire : ce volume n'a donc aucun effet sur sa taille.",
          f"- **Types universels.** Présents chez les {len(found)} termes : {', '.join(f'`{t}`' for t in universal)}. Ces "
          f"symboles sont constants : ils gonflent toutes les similarités de la même façon, sans rien discriminer.",
          f"- **Liste d'exclusion proposée** (types méta, lexicaux ou techniques) : "
          f"{', '.join(f'`{t}`' for t in TRT_NON_SEMANTIC)}. "
          f"Avec cette exclusion, TRT vaut médiane {fmt(med(s1))} [{min(s1)}–{max(s1)}] ; avec en plus un effectif ≥ 2, "
          f"{fmt(med(s2))} [{min(s2)}–{max(s2)}].",
          "- **Pas de seuil d'effectif.** L'effectif dépend surtout de la popularité du terme (huées : 81 relations "
          "entrantes, animaux : 133 715). Un seuil pénaliserait encore les termes rares.", ""]

    # --- SST ----------------------------------------------------------------
    L += ["## 5. Trait SST : _INFO-SEM-*", ""]
    n_sst = [len(r["SST"]) for r in found]
    L += [f"_INFO-SEM-* (w > 0) par terme : min {min(n_sst)}, médiane {fmt(med(n_sst))}, max {max(n_sst)} ; "
          f"{sum(1 for x in n_sst if x == 0)} terme(s) sans aucune annotation.", ""]
    body = [[r["term"], ", ".join(f"{n[len('_INFO-SEM-'):]} ({w:g})" for n, w in r["SST"]) or "—"] for r in found]
    L += table(["terme", "annotations (poids)"], body)
    L += [""]

    # --- Taille de signature ------------------------------------------------
    L += ["## 6. Taille de signature résultante", "",
          "Terme lui-même (1) + H + TRT + SST, ensemble plat de symboles binaires.", ""]
    def size_row(label, hs, ts):
        tot = [1 + h + t + s for h, t, s in zip(hs, ts, n_sst)]
        return [label] + [f"{fmt(med(v))} [{min(v)}–{max(v)}]" for v in (hs, ts, n_sst, tot)]

    rows = [
        size_row("sans coupure (w > 0, H non plafonné)",
                 [len(r["H_all_w"]) for r in found], [len(r["TRT"]) for r in found]),
        size_row(f"recommandée (H top {H_RECO_K}, TRT sans types non sémantiques)",
                 [min(H_RECO_K, len(r["H_all_w"])) for r in found],
                 [sum(1 for t in r["TRT"] if t not in TRT_NON_SEMANTIC) for r in found]),
    ]
    L += table(["configuration", "H", "TRT", "SST", "total"], rows)
    L += [""]

    # --- Polysémie ----------------------------------------------------------
    senses = [r["raff_senses"] for r in found]
    L += ["## 7. Polysémie (raffinements)", "",
          f"Termes avec au moins un raffinement : {sum(s > 0 for s in senses)}/{len(found)} "
          f"({100 * sum(s > 0 for s in senses) / len(found):.0f} %) ; avec au moins deux sens de premier niveau : "
          f"{sum(s >= 2 for s in senses)}/{len(found)} ({100 * sum(s >= 2 for s in senses) / len(found):.0f} %). "
          f"Sens de premier niveau : médiane {fmt(med(senses))}, max {max(senses)}.", ""]
    by_stratum = defaultdict(list)
    for (t, s), r in zip(strata, recs):
        if r["exists"]:
            by_stratum[s].append(r["raff_senses"])
    L += table(["strate", "polysémiques (≥1 raff.)", "sens médians"],
               [[s, f"{sum(x > 0 for x in v)}/{len(v)}", fmt(med(v))] for s, v in by_stratum.items()])
    L += [""]

    # --- Latence ------------------------------------------------------------
    L += ["## 8. Latence et coût d'une passe complète", ""]
    per_ep = defaultdict(list)
    for r in recs:
        for c in r["calls"]:
            if c["elapsed_s"] is not None:
                per_ep[endpoint_of(c["path"])].append(c["elapsed_s"])
    body, per_term_mean = [], 0.0
    for ep in ("node_by_name", "relations/from", "relations/to"):
        v = per_ep.get(ep, [])
        if not v:
            continue
        calls_per_term = 3 if ep == "relations/from" else 1
        per_term_mean += calls_per_term * statistics.mean(v)
        body.append([ep, len(v), fmt(statistics.mean(v), 2), fmt(med(v), 2), fmt(max(v), 2), calls_per_term])
    L += table(["endpoint", "appels", "moyenne (s)", "médiane (s)", "max (s)", "appels / terme"], body)
    all_lat = [x for v in per_ep.values() for x in v]
    delay_total = 5 * client.delay  # node + 3 × from + to
    est = n_terms_total * (per_term_mean + delay_total)
    L += ["", f"Latence moyenne par appel, tous endpoints : {statistics.mean(all_lat):.2f} s ({len(all_lat)} appels).",
          f"Par terme : {per_term_mean:.2f} s d'appels + {delay_total:.1f} s de délai de politesse (5 appels × {client.delay} s).",
          f"**Passe complète estimée sur {n_terms_total} termes : {est / 60:.0f} min ({est / 3600:.1f} h)**, "
          f"en séquentiel, sans erreur ni nouvel essai. Les relations entrantes dominent : leur coût croît "
          f"avec la fréquence du terme (voir max).", ""]
    size = defaultdict(int)
    for r in recs:
        for c in r["calls"]:
            size[endpoint_of(c["path"])] += c.get("bytes") or 0
    total_b = sum(size.values())
    L += [f"Volume téléchargé pour les {len(recs)} termes : {total_b / 1e6:.1f} Mo, dont "
          f"{100 * size['relations/to'] / total_b:.0f} % pour les relations entrantes. Extrapolé à {n_terms_total} termes : "
          f"**≈ {total_b / len(recs) * n_terms_total / 1e9:.1f} Go de cache** (un JSON par requête, non compressé). "
          f"Le timeout de 10 s ne suffit pas pour les relations entrantes : on a mesuré jusqu'à "
          f"{max(per_ep['relations/to']):.1f} s (et 22 s pour « eau » en exploration), d'où un timeout de "
          f"{TIMEOUT_INCOMING:.0f} s sur cet endpoint.", ""]

    # --- Ambiguïtés -----------------------------------------------------------
    L += ["## 9. Test des deux lignes ambiguës (méthode §4.1)", "",
          "Existence dans JDM de chaque candidat A et B. Le corpus n'est pas modifié.", ""]
    body = []
    for a in amb:
        for c in a["cands"]:
            body.append([a["syntagme"], c["A"], "oui" if c["A_exists"] else "**non**",
                         c["B"], "oui" if c["B_exists"] else "**non**",
                         "valide" if c["A_exists"] and c["B_exists"] else "rejeté"])
    L += table(["syntagme", "A", "A existe", "B", "B existe", "découpage"], body)
    L += ["", "**Résultat.** Pour les deux syntagmes, un seul découpage a ses deux termes dans JDM : "
          + " ; ".join(f"« {a['syntagme']} » → A = `{c['A']}`, B = `{c['B']}`" for a in amb for c in a["cands"]
                       if c["A_exists"] and c["B_exists"])
          + ". Le critère est suffisant ici parce que le A du découpage concurrent (« cacao de Côte », "
          "« diamants d'Afrique ») n'existe pas, alors que les deux B concurrents existent (Ivoire, Sud). "
          "Tester B seul n'aurait donc pas suffi. Corpus non modifié.", ""]
    return "\n".join(L)


def main():
    terms = load_terms()
    strata = select_terms(terms)
    client = JDMClient()
    rel_ids, id_to_rel = client.relation_type_maps()
    node_types = {t["id"]: t["name"] for t in client.node_types()}

    recs = []
    for i, (term, stratum) in enumerate(strata, 1):
        try:
            rec = probe_term(client, term, rel_ids, id_to_rel, node_types)
        except JDMError as e:
            raise SystemExit(f"arrêt sur « {term} » : {e}")
        recs.append(rec)
        print(f"[{i:2d}/30] {stratum:14s} {term:22s} "
              + (f"H={len(rec['H']):2d} TRT={len(rec['TRT']):3d} SST={len(rec['SST']):2d} raff={rec['raff_senses']}"
                 if rec["exists"] else "INTROUVABLE"), flush=True)
    amb = ambiguity_test(client)
    n_terms_total = len(terms)
    report = build_report(strata, recs, terms, amb, client, n_terms_total)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report + "\n", encoding="utf-8")
    real = [c for c in client.calls if not c["cached"]]
    print(f"{len(client.calls)} requêtes, dont {len(real)} appels réseau. Rapport : {REPORT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
