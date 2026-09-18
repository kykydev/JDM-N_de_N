#!/usr/bin/env python3
"""Variantes de déterminant pour casser la régularité artificielle de la définitude.

Lit data/corpus/raw/*.csv (jamais modifiés) et écrit data/corpus/variants/*.csv
au même format « <syntagme> ; <relation> », même ordre, même nombre de lignes.

Pour les huit types listés dans VARIABLE_TYPES seulement, environ 12,5 % des
lignes (stratifié train/test) reçoivent une variante de déterminant :
    « du X »    -> « d'un X »
    « de la X » -> « d'une X »
    « du X »    -> « de X »      (r_holo uniquement)
Le genre de X est lu sur le déterminant d'origine (du = masc., de la = fém.) ;
aucune détection de genre par dictionnaire. A, B et la relation sont inchangés.
Les autres fichiers sont recopiés à l'identique.

Sélection déterministe : un unique random.Random(42), consommé dans un ordre fixe.

Usage : python3 src/corpus_variants.py
"""

import random
import re
import shutil
from pathlib import Path

from corpus_check import PREP_RE, RAW_DIR, ROOT, TRAIN_SIZE, norm, parse_file, split_candidates

VARIANTS_DIR = ROOT / "data" / "corpus" / "variants"
REPORT_PATH = ROOT / "reports" / "variantes_definitude.md"

SEED = 42
# Lignes modifiées par split : 6/50 en train, 4/30 en test = 10/80 = 12,5 %.
TARGET = {"train": 6, "test": 4}

VARIABLE_TYPES = [
    "r_holo", "r_own-1", "r_processus_agent", "r_processus_patient",
    "r_product_of", "r_social_tie", "r_has_property-1", "r_has_causatif",
]
# Garde-fou : ces types ne doivent jamais être transformés.
FROZEN_TYPES = {
    "r_topic", "r_depict", "r_lieu", "r_lieu>origine",
    "r_objet>matiere", "r_quantificateur",
}
assert not FROZEN_TYPES & set(VARIABLE_TYPES)

# Syntagmes d'origine à ne jamais transformer (variante jugée non naturelle à la relecture,
# ex. noms massifs ou référents uniques : « récolte du blé » -> « récolte d'un blé »).
# Exclure une ligne ne change pas les autres tirages : la suivante dans l'ordre mélangé la remplace.
EXCLUDED = {
    "abattage du bétail",       # nom collectif
    "tamisage de la farine",    # nom massif
    "directeur du personnel",   # titre figé, nom collectif
    "obésité de la malbouffe",  # nom massif
    "émeutes de la faim",       # expression figée
    "dommages de la grêle",     # nom massif
    "patine du temps",          # référent unique
    "inauguration du maire",    # « d'un maire » fait lire le maire comme patient
    "traite du fermier",        # « une traite d'un fermier » = effet de commerce
}

# Préposition d'origine (normalisée) -> remplacements autorisés.
REWRITES = {"du": ["d'un "], "de la": ["d'une "]}
REWRITES_HOLO = {"du": ["d'un ", "de "], "de la": ["d'une "]}


def eligible_match(syntagme):
    """Renvoie le match de la préposition si la ligne peut recevoir une variante, sinon None."""
    cands = split_candidates(syntagme)
    if len(cands) != 1:
        return None  # ambigu ou non découpable
    c = cands[0]
    if norm(c["prep"]) not in REWRITES:
        return None  # « de l' » (genre inconnu), « des » (pluriel), « de », « d' »
    if c["B"][:1].isupper():
        return None  # entité nommée
    matches = [m for m in PREP_RE.finditer(syntagme) if syntagme[:m.start()].strip() == c["A"]]
    return matches[0] if len(matches) == 1 else None


def rewrite_line(raw_line, syntagme, m, new_prep):
    """Remplace uniquement la préposition dans la ligne brute ; le reste est conservé tel quel."""
    start = raw_line.index(syntagme)
    new_syntagme = syntagme[:m.start()] + new_prep + syntagme[m.end():]
    return raw_line[:start] + new_syntagme + raw_line[start + len(syntagme):], new_syntagme


def check_invariants(before, after):
    """A, B et relation strictement identiques ; seule la préposition change."""
    cb, ca = split_candidates(before), split_candidates(after)
    assert len(cb) == 1 and len(ca) == 1, (before, after)
    assert (cb[0]["A"], cb[0]["B"]) == (ca[0]["A"], ca[0]["B"]), (before, after)
    assert cb[0]["prep"] != ca[0]["prep"] or cb[0]["det"] != ca[0]["det"], (before, after)


def process_variable(path, relation, rng):
    raw_lines = path.read_text(encoding="utf-8").split("\n")
    entries, issues = parse_file(path)
    assert not issues, f"{path.name} : lignes malformées, corriger d'abord ({issues})"
    assert {e["relation"] for e in entries} == {relation}

    # Le mélange porte sur les candidats avant exclusion manuelle : la consommation du
    # générateur ne dépend donc pas de EXCLUDED, et une exclusion ne décale aucun autre tirage.
    pools = {"train": [], "test": []}
    for e in entries:
        m = eligible_match(e["syntagme"])
        if m:
            pools["train" if e["lineno"] <= TRAIN_SIZE else "test"].append((e, m))

    table = REWRITES_HOLO if relation == "r_holo" else REWRITES
    changes, shortfalls = [], []
    for split in ("train", "test"):
        order = rng.sample(pools[split], len(pools[split]))
        # Un tirage de variante par candidat, exclu ou non, pour la même raison.
        choices = [rng.choice(table[norm(m.group("prep"))]) for _, m in order]
        picked = [(e, m, c) for (e, m), c in zip(order, choices)
                  if e["syntagme"] not in EXCLUDED][:TARGET[split]]
        if len(picked) < TARGET[split]:
            shortfalls.append(f"{split} : {len(picked)} ligne(s) éligible(s) pour {TARGET[split]} visées")
        for e, m, new_prep in sorted(picked, key=lambda x: x[0]["lineno"]):
            idx = e["lineno"] - 1
            raw_lines[idx], new_syntagme = rewrite_line(raw_lines[idx], e["syntagme"], m, new_prep)
            check_invariants(e["syntagme"], new_syntagme)
            changes.append({"lineno": e["lineno"], "split": split,
                            "before": e["syntagme"], "after": new_syntagme})

    out = VARIANTS_DIR / path.name
    out.write_text("\n".join(raw_lines), encoding="utf-8")
    assert len(out.read_bytes().split(b"\n")) == len(path.read_bytes().split(b"\n"))
    eligible = {s: sum(1 for e, _ in p if e["syntagme"] not in EXCLUDED) for s, p in pools.items()}
    return {"eligible": eligible, "changes": changes, "shortfalls": shortfalls}


def build_report(results, n_lines):
    L = ["# Variantes de définitude", "",
         "Généré par `src/corpus_variants.py` (graine `random.Random(42)`). Source : `data/corpus/raw/` "
         "(inchangé). Sortie : `data/corpus/variants/`.", "",
         "Transformations : `du X` → `d'un X`, `de la X` → `d'une X` ; pour `r_holo` seulement, "
         "`du X` peut aussi devenir `de X` (tirage 50/50). Lignes éligibles : découpage non ambigu, "
         "préposition `du` ou `de la`, B sans majuscule initiale. `de l'` est exclu (genre non "
         "déductible du déterminant), `des` aussi (pluriel).", "",
         f"Cible : {TARGET['train']} lignes en train et {TARGET['test']} en test par type, soit "
         f"{sum(TARGET.values())}/80 = {100 * sum(TARGET.values()) / 80:.1f} %.", "",
         f"Exclusions manuelles (`EXCLUDED`) : {len(EXCLUDED)}"
         + (" — " + ", ".join(f"« {s} »" for s in sorted(EXCLUDED)) if EXCLUDED else "") + ".", "",
         "Types recopiés sans modification : " + ", ".join(f"`{t}`" for t in sorted(FROZEN_TYPES)) + ".", "",
         "## Synthèse", "",
         "| relation | fichier | éligibles train | éligibles test | modifiées train | modifiées test | total | % |",
         "|---|---|---|---|---|---|---|---|"]
    for rel, name, res in results:
        ch = res["changes"]
        tr = sum(c["split"] == "train" for c in ch)
        L.append(f"| {rel} | {name} | {res['eligible']['train']} | {res['eligible']['test']} | "
                 f"{tr} | {len(ch) - tr} | {len(ch)} | {100 * len(ch) / n_lines[name]:.1f} |")
    shortfalls = [(rel, s) for rel, _, res in results for s in res["shortfalls"]]
    if shortfalls:
        L += ["", "**Cible non atteinte :**", ""] + [f"- {rel} — {s}" for rel, s in shortfalls]
    L += [""]
    for rel, name, res in results:
        L += [f"## {rel}", "", f"Fichier `{name}.csv`, {len(res['changes'])} ligne(s) modifiée(s).", "",
              "| ligne | split | avant | après |", "|---|---|---|---|"]
        L += [f"| {c['lineno']} | {c['split']} | {c['before']} | {c['after']} |" for c in res["changes"]]
        L += [""]
    return "\n".join(L)


def main():
    VARIANTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    by_relation, n_lines = {}, {}
    for path in sorted(RAW_DIR.glob("*.csv")):
        entries, _ = parse_file(path)
        labels = {e["relation"] for e in entries}
        assert len(labels) == 1, f"{path.name} : plusieurs relations {labels}"
        by_relation[labels.pop()] = path
        n_lines[path.stem] = len(path.read_bytes().splitlines())

    missing = set(VARIABLE_TYPES) - set(by_relation)
    assert not missing, f"types introuvables : {missing}"

    rng = random.Random(SEED)
    results = []
    for rel in VARIABLE_TYPES:  # ordre fixe => tirages reproductibles
        path = by_relation[rel]
        results.append((rel, path.stem, process_variable(path, rel, rng)))

    for rel, path in sorted(by_relation.items()):
        if rel not in VARIABLE_TYPES:
            shutil.copyfile(path, VARIANTS_DIR / path.name)

    REPORT_PATH.write_text(build_report(results, n_lines) + "\n", encoding="utf-8")
    total = sum(len(res["changes"]) for _, _, res in results)
    print(f"{total} lignes modifiées sur {len(VARIABLE_TYPES)} types ; "
          f"{len(by_relation) - len(VARIABLE_TYPES)} fichiers recopiés à l'identique.")
    print(f"Rapport : {REPORT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
