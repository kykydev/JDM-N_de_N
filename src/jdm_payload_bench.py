#!/usr/bin/env python3
"""Phase 1 : mesure du gain de payload sur /v0/relations/to avant la collecte complète.

Les relations entrantes portent 98 % du volume et l'essentiel de la latence (sonde du
2026-09-18). Le trait TRT n'a besoin que du *type* de chaque relation entrante, et du
nombre de celles de poids > 0. On compare donc plusieurs jeux de paramètres sur cinq
termes de profils différents, et on ne retient une optimisation que si le résultat est
strictement identique à la référence.

Deux comparaisons sont faites, car elles ne sont pas équivalentes :
- `types_all`  : multi-ensemble type -> nombre de relations entrantes, toutes relations ;
- `types_pos`  : idem restreint aux relations de poids > 0, c'est-à-dire le trait TRT.
Une combinaison sans le champ `w` ne peut pas produire `types_pos` par elle-même : elle
n'est utilisable que si le serveur filtre pour nous (min_weight) et que le résultat
coïncide avec `types_pos` de la référence.

Le cache de cette phase est séparé de celui de la collecte (les réponses complètes de
référence pèsent lourd et ne resserviront jamais).

Les clés du JSON produit (`ok`, `bytes`, `types_all`, ...) sont celles que lit le rapport
de collecte : elles ne sont pas renommées.

Usage : python3 src/jdm_payload_bench.py [--cache-dir DIR] [--out FICHIER.json]
"""

import argparse
import json
import time
from collections import Counter
from pathlib import Path

import config
from jdm_client import ClientJDM, JDMErreur, JDMIntrouvable

# Profils contrastés, choisis sur les mesures de la sonde (relations entrantes w > 0) :
TERMES = [
    ("animaux", "très connecté (133 715 relations entrantes)"),
    ("huées", "rare (81)"),
    ("discrétion", "moyen (9 944)"),
    ("Bordeaux", "entité nommée (22 229)"),
    ("Côte d'Ivoire", "polylexical (4 683)"),
]

COMBINAISONS = [
    ("référence (aucun paramètre)", {}),
    ("without_nodes=true", {"without_nodes": True}),
    ("relation_fields=[type]", {"relation_fields": ["type"]}),
    ("without_nodes=true + relation_fields=[type]",
     {"without_nodes": True, "relation_fields": ["type"]}),
    ("without_nodes=true + relation_fields=[type] + min_weight=1",
     {"without_nodes": True, "relation_fields": ["type"], "min_weight": 1}),
    # Variante retenue par la sonde : garde `w`, donc sait filtrer w > 0 côté client.
    ("without_nodes=true + relation_fields=[type,w]",
     {"without_nodes": True, "relation_fields": ["type", "w"]}),
    ("without_nodes=true + relation_fields=[type,w] + min_weight=1",
     {"without_nodes": True, "relation_fields": ["type", "w"], "min_weight": 1}),
]

TIMEOUT = 300.0  # la référence sur « animaux » rapatrie des dizaines de Mo


def compter_types(relations):
    """Compte les relations entrantes par type. Retourne (toutes, celles de poids > 0),
    la seconde valant None si le champ `w` est absent de la réponse."""
    toutes, positives, avec_poids = Counter(), Counter(), True
    for relation in relations:
        toutes[relation["type"]] += 1
        if "w" not in relation:
            avec_poids = False
        elif relation["w"] > 0:
            positives[relation["type"]] += 1
    return toutes, (positives if avec_poids else None)


def mesurer_combinaison(client, terme, parametres):
    """Mesure une combinaison de paramètres sur un terme. Retourne le dict de mesures,
    ou {ok: False, erreur} si le serveur a refusé la requête."""
    avant = len(client.appels)
    debut = time.monotonic()
    try:
        donnees = client.relations_entrantes(terme, timeout=TIMEOUT, **parametres)
    except (JDMErreur, JDMIntrouvable) as e:
        return {"ok": False, "erreur": f"{type(e).__name__}: {e}"}
    duree_totale = time.monotonic() - debut

    appel = client.appels[avant]
    relations = donnees.get("relations", [])
    toutes, positives = compter_types(relations)
    return {"ok": True, "bytes": appel["bytes"], "elapsed_s": appel["elapsed_s"],
            "wall_s": round(duree_totale, 3), "cached": appel["cached"],
            "n_relations": len(relations), "n_nodes": len(donnees.get("nodes") or []),
            "types_all": dict(toutes),
            "types_pos": (dict(positives) if positives is not None else None)}


def comparer_a_la_reference(resultats, libelle_reference):
    """Marque chaque combinaison comme identique ou non à la référence. Ne retourne rien.

    Une combinaison sans `w` ne produit pas `types_pos` : on compare alors ce qu'elle
    renvoie (`types_all`) à la vérité attendue (`types_pos` de la référence)."""
    for terme in resultats:
        reference = resultats[terme]["combos"][libelle_reference]
        for mesures in resultats[terme]["combos"].values():
            if not mesures["ok"] or not reference["ok"]:
                continue
            mesures["ident_all"] = (mesures["types_all"] == reference["types_all"])
            if mesures["types_pos"] is not None:
                observees = mesures["types_pos"]
            else:
                observees = mesures["types_all"]
            mesures["ident_pos"] = (observees == reference["types_pos"])
            mesures["donne_w"] = mesures["types_pos"] is not None


def afficher_synthese(resultats, libelle_reference):
    """Affiche le tableau de synthèse et les gains. Ne retourne rien."""
    print("\n=== Synthèse (total sur les 5 termes) ===")
    print(f"{'combinaison':<58} {'octets':>12} {'latence s':>10} {'=TRT':>6} {'w?':>4}")
    for libelle, _ in COMBINAISONS:
        mesures = [resultats[t]["combos"][libelle] for t, _ in TERMES]
        if not all(m["ok"] for m in mesures):
            echecs = [t for (t, _), m in zip(TERMES, mesures) if not m["ok"]]
            print(f"{libelle:<58} ECHEC sur {echecs}")
            continue
        octets = sum(m["bytes"] for m in mesures)
        latence = sum(m["elapsed_s"] for m in mesures)
        identique = "oui" if all(m.get("ident_pos") for m in mesures) else "NON"
        donne_w = "oui" if mesures[0].get("donne_w") else "non"
        print(f"{libelle:<58} {octets:>12,} {latence:>10.2f} {identique:>6} {donne_w:>4}")

    reference = [resultats[t]["combos"][libelle_reference] for t, _ in TERMES]
    if not all(m["ok"] for m in reference):
        return
    octets_ref = sum(m["bytes"] for m in reference)
    latence_ref = sum(m["elapsed_s"] for m in reference)
    print(f"\nRéférence : {octets_ref:,} o, {latence_ref:.2f} s")
    for libelle, _ in COMBINAISONS[1:]:
        mesures = [resultats[t]["combos"][libelle] for t, _ in TERMES]
        if not all(m["ok"] for m in mesures):
            continue
        octets = sum(m["bytes"] for m in mesures)
        latence = sum(m["elapsed_s"] for m in mesures)
        print(f"  {libelle:<56} gain volume {100 * (1 - octets / octets_ref):5.1f} %   "
              f"gain latence {100 * (1 - latence / latence_ref):5.1f} %")


def main():
    analyseur = argparse.ArgumentParser()
    analyseur.add_argument("--cache-dir", default=str(config.DOSSIER_CACHE / "bench"))
    analyseur.add_argument("--out", default=str(config.DOSSIER_RAPPORTS / "phase1_payload.json"))
    arguments = analyseur.parse_args()

    client = ClientJDM(dossier_cache=arguments.cache_dir, delai=config.DELAI_POLITESSE,
                       timeout=TIMEOUT)
    resultats = {}
    for terme, profil in TERMES:
        resultats[terme] = {"profil": profil, "combos": {}}
        for libelle, parametres in COMBINAISONS:
            print(f"[{terme}] {libelle} ...", flush=True)
            mesures = mesurer_combinaison(client, terme, parametres)
            resultats[terme]["combos"][libelle] = mesures
            if mesures["ok"]:
                print(f"    {mesures['bytes']:>10,} o  {mesures['elapsed_s']:>7.2f} s  "
                      f"{mesures['n_relations']:>7} rel.  {mesures['n_nodes']:>6} nœuds"
                      f"{'  [cache]' if mesures['cached'] else ''}", flush=True)
            else:
                print(f"    ECHEC : {mesures['erreur']}", flush=True)

    comparer_a_la_reference(resultats, COMBINAISONS[0][0])
    destination = Path(arguments.out)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(resultats, ensure_ascii=False, indent=1), encoding="utf-8")
    afficher_synthese(resultats, COMBINAISONS[0][0])
    print(f"\nDétail : {arguments.out}")


if __name__ == "__main__":
    main()
