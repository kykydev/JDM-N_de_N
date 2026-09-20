#!/usr/bin/env python3
"""Variantes de déterminant pour casser la régularité artificielle de la définitude.

Lit data/corpus/raw/*.csv (jamais modifiés) et écrit data/corpus/variants/*.csv
au même format « <syntagme> ; <relation> », même ordre, même nombre de lignes.

Pour les huit types listés dans TYPES_VARIABLES seulement, environ 12,5 % des
lignes (stratifié train/test) reçoivent une variante de déterminant :
    « du X »    -> « d'un X »
    « de la X » -> « d'une X »
    « du X »    -> « de X »      (r_holo uniquement)
Le genre de X est lu sur le déterminant d'origine (du = masc., de la = fém.) ;
aucune détection de genre par dictionnaire. A, B et la relation sont inchangés.
Les autres fichiers sont recopiés à l'identique.

Sélection déterministe : un unique random.Random(42), consommé dans un ordre fixe.
Toute modification de cet ordre change les lignes tirées.

Usage : python3 src/corpus_variants.py
"""

import random
import shutil

import config
from corpus_check import (PREPOSITION_RE, analyser_fichier, chemin_relatif,
                          decoupages_possibles, normaliser)

CHEMIN_RAPPORT = config.DOSSIER_RAPPORTS / "variantes_definitude.md"

TYPES_VARIABLES = [
    "r_holo", "r_own-1", "r_processus_agent", "r_processus_patient",
    "r_product_of", "r_social_tie", "r_has_property-1", "r_has_causatif",
]
# Garde-fou : ces types ne doivent jamais être transformés.
TYPES_GELES = {
    "r_topic", "r_depict", "r_lieu", "r_lieu>origine",
    "r_objet>matiere", "r_quantificateur",
}
assert not TYPES_GELES & set(TYPES_VARIABLES)

# Syntagmes d'origine à ne jamais transformer (variante jugée non naturelle à la relecture,
# ex. noms massifs ou référents uniques : « récolte du blé » -> « récolte d'un blé »).
# Exclure une ligne ne change pas les autres tirages : la suivante dans l'ordre mélangé la remplace.
SYNTAGMES_EXCLUS = {
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
REECRITURES = {"du": ["d'un "], "de la": ["d'une "]}
REECRITURES_HOLO = {"du": ["d'un ", "de "], "de la": ["d'une "]}


# ---------------------------------------------------------------------------
# Éligibilité et réécriture d'une ligne
# ---------------------------------------------------------------------------

def preposition_eligible(syntagme):
    """Cherche la préposition à réécrire dans un syntagme. Retourne le match de
    PREPOSITION_RE si la ligne peut recevoir une variante, sinon None."""
    candidats = decoupages_possibles(syntagme)
    if len(candidats) != 1:
        return None  # ambigu ou non découpable
    candidat = candidats[0]
    if normaliser(candidat["preposition"]) not in REECRITURES:
        return None  # « de l' » (genre inconnu), « des » (pluriel), « de », « d' »
    if candidat["B"][:1].isupper():
        return None  # entité nommée
    trouvees = [m for m in PREPOSITION_RE.finditer(syntagme)
                if syntagme[:m.start()].strip() == candidat["A"]]
    return trouvees[0] if len(trouvees) == 1 else None


def reecrire_ligne(ligne_brute, syntagme, trouvee, nouvelle_preposition):
    """Remplace uniquement la préposition dans la ligne brute ; le reste est conservé tel
    quel. Retourne (ligne réécrite, nouveau syntagme)."""
    debut = ligne_brute.index(syntagme)
    nouveau_syntagme = (syntagme[:trouvee.start()] + nouvelle_preposition
                        + syntagme[trouvee.end():])
    fin = ligne_brute[debut + len(syntagme):]
    return ligne_brute[:debut] + nouveau_syntagme + fin, nouveau_syntagme


def verifier_invariants(avant, apres):
    """Vérifie que A, B et la relation sont inchangés et que seule la préposition varie.
    Lève AssertionError sinon. Ne retourne rien."""
    candidats_avant = decoupages_possibles(avant)
    candidats_apres = decoupages_possibles(apres)
    assert len(candidats_avant) == 1 and len(candidats_apres) == 1, (avant, apres)
    assert (candidats_avant[0]["A"], candidats_avant[0]["B"]) \
        == (candidats_apres[0]["A"], candidats_apres[0]["B"]), (avant, apres)
    assert candidats_avant[0]["preposition"] != candidats_apres[0]["preposition"] \
        or candidats_avant[0]["det"] != candidats_apres[0]["det"], (avant, apres)


# ---------------------------------------------------------------------------
# Traitement d'un type de relation
# ---------------------------------------------------------------------------

def viviers_eligibles(entrees):
    """Range les lignes éligibles par split. Retourne {split: [(entrée, match)]}."""
    viviers = {"train": [], "test": []}
    for entree in entrees:
        trouvee = preposition_eligible(entree["syntagme"])
        if trouvee:
            split = "train" if entree["ligne"] <= config.TAILLE_TRAIN else "test"
            viviers[split].append((entree, trouvee))
    return viviers


def tirer_lignes_a_modifier(vivier, table_reecritures, cible, rng):
    """Tire les lignes à modifier dans un vivier. Retourne [(entrée, match, préposition)].

    Le mélange porte sur les candidats AVANT exclusion manuelle, et une variante est tirée
    pour chaque candidat, exclu ou non : la consommation du générateur ne dépend donc pas
    de SYNTAGMES_EXCLUS, et exclure une ligne ne décale aucun autre tirage."""
    ordre = rng.sample(vivier, len(vivier))
    variantes = []
    for _, trouvee in ordre:
        variantes.append(rng.choice(table_reecritures[normaliser(trouvee.group("prep"))]))
    retenues = []
    for (entree, trouvee), variante in zip(ordre, variantes):
        if entree["syntagme"] not in SYNTAGMES_EXCLUS:
            retenues.append((entree, trouvee, variante))
    return retenues[:cible]


def traiter_type_variable(chemin, relation, rng):
    """Écrit la variante d'un type de relation. Retourne {eligibles, modifications, manques}."""
    lignes_brutes = chemin.read_text(encoding="utf-8").split("\n")
    entrees, anomalies = analyser_fichier(chemin)
    assert not anomalies, f"{chemin.name} : lignes malformées, corriger d'abord ({anomalies})"
    assert {e["relation"] for e in entrees} == {relation}

    viviers = viviers_eligibles(entrees)
    table = REECRITURES_HOLO if relation == "r_holo" else REECRITURES
    modifications, manques = [], []
    for split in ("train", "test"):
        cible = config.CIBLE_VARIANTES[split]
        retenues = tirer_lignes_a_modifier(viviers[split], table, cible, rng)
        if len(retenues) < cible:
            manques.append(f"{split} : {len(retenues)} ligne(s) éligible(s) pour {cible} visées")
        for entree, trouvee, variante in sorted(retenues, key=lambda x: x[0]["ligne"]):
            indice = entree["ligne"] - 1
            lignes_brutes[indice], nouveau = reecrire_ligne(
                lignes_brutes[indice], entree["syntagme"], trouvee, variante)
            verifier_invariants(entree["syntagme"], nouveau)
            modifications.append({"ligne": entree["ligne"], "split": split,
                                  "avant": entree["syntagme"], "apres": nouveau})

    sortie = config.DOSSIER_CORPUS_VARIANTES / chemin.name
    sortie.write_text("\n".join(lignes_brutes), encoding="utf-8")
    assert len(sortie.read_bytes().split(b"\n")) == len(chemin.read_bytes().split(b"\n"))

    eligibles = {}
    for split, vivier in viviers.items():
        eligibles[split] = sum(1 for entree, _ in vivier
                               if entree["syntagme"] not in SYNTAGMES_EXCLUS)
    return {"eligibles": eligibles, "modifications": modifications, "manques": manques}


# ---------------------------------------------------------------------------
# Rapport
# ---------------------------------------------------------------------------

def section_entete():
    """En-tête et règles appliquées. Retourne une liste de lignes."""
    cible_train = config.CIBLE_VARIANTES["train"]
    cible_test = config.CIBLE_VARIANTES["test"]
    total_cible = cible_train + cible_test
    exclusions = ", ".join(f"« {s} »" for s in sorted(SYNTAGMES_EXCLUS))
    return ["# Variantes de définitude", "",
            "Généré par `src/corpus_variants.py` (graine `random.Random(42)`). Source : `data/corpus/raw/` "
            "(inchangé). Sortie : `data/corpus/variants/`.", "",
            "Transformations : `du X` → `d'un X`, `de la X` → `d'une X` ; pour `r_holo` seulement, "
            "`du X` peut aussi devenir `de X` (tirage 50/50). Lignes éligibles : découpage non ambigu, "
            "préposition `du` ou `de la`, B sans majuscule initiale. `de l'` est exclu (genre non "
            "déductible du déterminant), `des` aussi (pluriel).", "",
            f"Cible : {cible_train} lignes en train et {cible_test} en test par type, soit "
            f"{total_cible}/80 = {100 * total_cible / 80:.1f} %.", "",
            f"Exclusions manuelles (`SYNTAGMES_EXCLUS`) : {len(SYNTAGMES_EXCLUS)}"
            + (" — " + exclusions if SYNTAGMES_EXCLUS else "") + ".", "",
            "Types recopiés sans modification : "
            + ", ".join(f"`{t}`" for t in sorted(TYPES_GELES)) + ".", ""]


def section_synthese(resultats, nb_lignes):
    """Tableau de synthèse et cibles non atteintes. Retourne une liste de lignes."""
    lignes = ["## Synthèse", "",
              "| relation | fichier | éligibles train | éligibles test | modifiées train | "
              "modifiées test | total | % |",
              "|---|---|---|---|---|---|---|---|"]
    for relation, nom, resultat in resultats:
        modifications = resultat["modifications"]
        n_train = sum(m["split"] == "train" for m in modifications)
        part = 100 * len(modifications) / nb_lignes[nom]
        lignes.append(f"| {relation} | {nom} | {resultat['eligibles']['train']} | "
                      f"{resultat['eligibles']['test']} | {n_train} | "
                      f"{len(modifications) - n_train} | {len(modifications)} | {part:.1f} |")
    manques = [(relation, m) for relation, _, resultat in resultats for m in resultat["manques"]]
    if manques:
        lignes += ["", "**Cible non atteinte :**", ""]
        lignes += [f"- {relation} — {m}" for relation, m in manques]
    return lignes + [""]


def section_detail(resultats):
    """Détail ligne à ligne par type de relation. Retourne une liste de lignes."""
    lignes = []
    for relation, nom, resultat in resultats:
        modifications = resultat["modifications"]
        lignes += [f"## {relation}", "",
                   f"Fichier `{nom}.csv`, {len(modifications)} ligne(s) modifiée(s).", "",
                   "| ligne | split | avant | après |", "|---|---|---|---|"]
        for m in modifications:
            lignes.append(f"| {m['ligne']} | {m['split']} | {m['avant']} | {m['apres']} |")
        lignes += [""]
    return lignes


def construire_rapport(resultats, nb_lignes):
    """Assemble le rapport des variantes. Retourne le texte Markdown complet."""
    lignes = section_entete()
    lignes += section_synthese(resultats, nb_lignes)
    lignes += section_detail(resultats)
    return "\n".join(lignes)


def indexer_sources():
    """Associe chaque relation à son fichier source. Retourne (relation -> chemin,
    nom de fichier -> nombre de lignes)."""
    par_relation, nb_lignes = {}, {}
    for chemin in sorted(config.DOSSIER_CORPUS_BRUT.glob("*.csv")):
        entrees, _ = analyser_fichier(chemin)
        etiquettes = {e["relation"] for e in entrees}
        assert len(etiquettes) == 1, f"{chemin.name} : plusieurs relations {etiquettes}"
        par_relation[etiquettes.pop()] = chemin
        nb_lignes[chemin.stem] = len(chemin.read_bytes().splitlines())
    return par_relation, nb_lignes


def main():
    config.DOSSIER_CORPUS_VARIANTES.mkdir(parents=True, exist_ok=True)
    CHEMIN_RAPPORT.parent.mkdir(parents=True, exist_ok=True)

    par_relation, nb_lignes = indexer_sources()
    absents = set(TYPES_VARIABLES) - set(par_relation)
    assert not absents, f"types introuvables : {absents}"

    rng = random.Random(config.GRAINE_ALEATOIRE)
    resultats = []
    for relation in TYPES_VARIABLES:  # ordre fixe => tirages reproductibles
        chemin = par_relation[relation]
        resultats.append((relation, chemin.stem, traiter_type_variable(chemin, relation, rng)))

    for relation, chemin in sorted(par_relation.items()):
        if relation not in TYPES_VARIABLES:
            shutil.copyfile(chemin, config.DOSSIER_CORPUS_VARIANTES / chemin.name)

    CHEMIN_RAPPORT.write_text(construire_rapport(resultats, nb_lignes) + "\n", encoding="utf-8")
    total = sum(len(resultat["modifications"]) for _, _, resultat in resultats)
    recopies = len(par_relation) - len(TYPES_VARIABLES)
    print(f"{total} lignes modifiées sur {len(TYPES_VARIABLES)} types ; "
          f"{recopies} fichiers recopiés à l'identique.")
    print(f"Rapport : {chemin_relatif(CHEMIN_RAPPORT)}")


if __name__ == "__main__":
    main()
