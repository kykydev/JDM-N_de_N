#!/usr/bin/env python3
"""Contrôle et préparation hors-ligne du corpus « A de B ».

Lit data/corpus/raw/*.csv (jamais modifiés), produit :
  - data/corpus/clean/<nom>.csv   (une ligne par syntagme, ordre d'origine conservé)
  - data/corpus/clean/termes.csv  (termes dédupliqués, entrée de l'étape 2)
  - reports/rapport_corpus.md     (synthèse des contrôles)

Aucune suppression, aucune lemmatisation, aucun appel réseau.
Déterministe : même entrée -> mêmes fichiers octet pour octet.

Usage : python3 src/corpus_check.py [--raw DIR] [--clean DIR] [--report FICHIER]
        (défauts : data/corpus/raw, data/corpus/clean, reports/rapport_corpus.md)
"""

import argparse
import csv
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import config

APOSTROPHE = "['’]"
# Ordre des alternatives = priorité au motif le plus long (« de la » avant « de »).
# Chaque motif doit être précédé d'un espace : la préposition n'est jamais en tête.
PREPOSITION_RE = re.compile(
    rf"(?<=\s)(?P<prep>de\s+la\s+|de\s+l{APOSTROPHE}\s*|des\s+|du\s+|de\s+|d{APOSTROPHE}\s*)",
    re.IGNORECASE,
)
# Déterminant indéfini après « de »/« d' » : « d'un mariage », « d'une reine ».
INDEFINI_RE = re.compile(r"^(?P<det>une?)\s+(?=\S)", re.IGNORECASE)
# Autres déterminants non prévus par les règles du papier : signalés, pas traités.
AUTRE_DETERMINANT_RE = re.compile(
    r"^(ce|cet|cette|ces|mon|ma|mes|ton|ta|tes|son|sa|ses|notre|nos|votre|vos|leur|leurs)\s",
    re.IGNORECASE,
)

# Combinaisons de définitude comptées par la section 8.
COMBINAISONS_DEFINITUDE = ["Det+Def", "Det+NoDef", "NoDet+Def", "NoDet+NoDef"]

# Exemples du papier, vérifiés à chaque exécution : (syntagme, résultat attendu).
EXEMPLES_PAPIER = (
    ("chat du rabbin", "Det+Def"),
    ("écran de cinéma", "NoDet+NoDef"),
    ("tableau de Chagall", "NoDet+Def"),
)


# ---------------------------------------------------------------------------
# Normalisation (comparaison uniquement, jamais écrite dans les sorties)
# ---------------------------------------------------------------------------

def normaliser(texte):
    """Forme de comparaison : NFC, apostrophe droite, espaces réduits, minuscules.
    Retourne une chaîne."""
    texte = unicodedata.normalize("NFC", texte)
    texte = texte.replace("’", "'")
    texte = re.sub(r"\s+", " ", texte).strip()
    return texte.lower()


def chemin_relatif(chemin):
    """Chemin relatif à la racine du projet, en séparateurs POSIX pour que le rapport
    ne dépende pas du système. Retourne une chaîne."""
    try:
        return chemin.relative_to(config.RACINE).as_posix()
    except ValueError:
        return chemin.as_posix()


# ---------------------------------------------------------------------------
# Lecture des fichiers source
# ---------------------------------------------------------------------------

def analyser_fichier(chemin):
    """Lit un CSV source ligne à ligne, sans rien corriger. Retourne (entrées, anomalies) ;
    chaque entrée garde son numéro de ligne physique."""
    entrees, anomalies = [], []
    lignes_brutes = chemin.read_bytes().split(b"\n")
    if lignes_brutes and lignes_brutes[-1] == b"":
        lignes_brutes.pop()  # saut de ligne final

    for numero, brute in enumerate(lignes_brutes, start=1):
        try:
            ligne = brute.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            anomalies.append((numero, f"UTF-8 invalide ({exc.reason}, octet {exc.start})",
                              brute.decode("utf-8", "replace")))
            continue
        if numero == 1:
            ligne = ligne.lstrip("﻿")
        ligne = ligne.rstrip("\r")
        if not ligne.strip():
            anomalies.append((numero, "ligne vide", ligne))
            continue
        champs = re.split(r"\s*;\s*", ligne.strip())
        if len(champs) != 2:
            anomalies.append((numero, f"{len(champs)} champ(s) au lieu de 2", ligne))
            continue
        syntagme, relation = (re.sub(r"\s+", " ", c) for c in champs)
        if not syntagme or not relation:
            anomalies.append((numero, "champ vide", ligne))
            continue
        entrees.append({"ligne": numero, "syntagme": syntagme, "relation": relation})
    return entrees, anomalies


# ---------------------------------------------------------------------------
# Découpage A / B et définitude
# ---------------------------------------------------------------------------

def definitude(preposition, b_brut):
    """Applique les règles de la section 4.4.2. Retourne (B, det, definitude, remarque)."""
    prep = normaliser(preposition)
    remarque = ""
    if prep in ("de la", "de l'", "du", "des"):
        det, defini = "Det", True
        b = b_brut
    else:  # « de » ou « d' »
        indefini = INDEFINI_RE.match(b_brut)
        if indefini:
            # d'un / d'une : déterminant présent mais indéfini.
            det, defini = "Det", False
            b = b_brut[indefini.end():]
        else:
            det, defini = "NoDet", False
            b = b_brut
            if AUTRE_DETERMINANT_RE.match(b_brut):
                remarque = f"déterminant non couvert par les règles : « {b_brut.split()[0]} »"
    b = b.strip()
    # Entité nommée : Def forcé même en NoDet.
    if b[:1].isupper():
        defini = True
    return b, det, "Def" if defini else "NoDef", remarque


def decoupages_possibles(syntagme):
    """Tous les découpages A / B d'un syntagme, un par préposition trouvée.
    Retourne une liste de dicts {A, B, preposition, det, definitude, remarque}."""
    candidats = []
    for trouvee in PREPOSITION_RE.finditer(syntagme):
        a = syntagme[:trouvee.start()].strip()
        b_brut = syntagme[trouvee.end():].strip()
        if not a or not b_brut:
            continue
        b, det, defini, remarque = definitude(trouvee.group("prep"), b_brut)
        if not b:
            continue
        candidats.append({
            "A": a, "B": b,
            "preposition": re.sub(r"\s+", " ", trouvee.group("prep")).strip(),
            "det": det, "definitude": defini, "remarque": remarque,
        })
    return candidats


def traiter_fichier(chemin):
    """Analyse un fichier source et découpe chaque syntagme. Retourne (lignes, anomalies)."""
    entrees, anomalies = analyser_fichier(chemin)
    lignes = []
    for entree in entrees:
        # Le split suit la position physique de la ligne, pas l'indice après filtrage.
        split = "train" if entree["ligne"] <= config.TAILLE_TRAIN else "test"
        candidats = decoupages_possibles(entree["syntagme"])
        ligne = {
            "syntagme": entree["syntagme"], "relation": entree["relation"], "split": split,
            "ligne": entree["ligne"], "candidats": candidats,
            "A": "", "B": "", "det": "", "definitude": "", "ambigu": "non",
        }
        if not candidats:
            anomalies.append((entree["ligne"], "aucune préposition de séparation trouvée",
                              entree["syntagme"]))
        elif len(candidats) == 1:
            seul = candidats[0]
            ligne.update(A=seul["A"], B=seul["B"], det=seul["det"],
                         definitude=seul["definitude"])
            if seul["remarque"]:
                anomalies.append((entree["ligne"], seul["remarque"], entree["syntagme"]))
        else:
            ligne["ambigu"] = "oui"
        lignes.append(ligne)
    return lignes, anomalies


# ---------------------------------------------------------------------------
# Écriture des sorties
# ---------------------------------------------------------------------------

def formater_candidats(candidats):
    """Sérialise les découpages candidats pour la colonne `candidats`. Retourne une chaîne."""
    return " | ".join(f"{c['A']} / {c['B']}" for c in candidats)


def ecrire_csv_propre(dossier_propre, nom, lignes):
    """Écrit le CSV nettoyé d'un type de relation. Ne retourne rien."""
    with open(dossier_propre / f"{nom}.csv", "w", encoding="utf-8", newline="") as f:
        redacteur = csv.writer(f, lineterminator="\n")
        redacteur.writerow(["syntagme", "A", "B", "relation", "split", "det", "definitude",
                            "ambigu", "candidats"])
        for ligne in lignes:
            candidats = formater_candidats(ligne["candidats"]) if ligne["ambigu"] == "oui" else ""
            redacteur.writerow([ligne["syntagme"], ligne["A"], ligne["B"], ligne["relation"],
                                ligne["split"], ligne["det"], ligne["definitude"],
                                ligne["ambigu"], candidats])


def compter_termes(toutes_lignes):
    """Compte les occurrences de chaque couple (terme, rôle). Retourne
    (occurrences fermes, occurrences comme candidat ambigu, relations par couple)."""
    fermes, ambigus = Counter(), Counter()
    relations = defaultdict(set)
    for ligne in toutes_lignes:
        if ligne["ambigu"] == "non" and ligne["A"]:
            for terme, role in ((ligne["A"], "A"), (ligne["B"], "B")):
                fermes[(terme, role)] += 1
                relations[(terme, role)].add(ligne["relation"])
        elif ligne["ambigu"] == "oui":
            for candidat in ligne["candidats"]:
                for terme, role in ((candidat["A"], "A"), (candidat["B"], "B")):
                    ambigus[(terme, role)] += 1
                    relations[(terme, role)].add(ligne["relation"])
    return fermes, ambigus, relations


def ecrire_termes(dossier_propre, toutes_lignes):
    """Écrit termes.csv. Clé = (forme originale, rôle) : aucune fusion morphologique ni de
    casse. Retourne (nombre de couples, nombre n'existant que comme candidat ambigu)."""
    fermes, ambigus, relations = compter_termes(toutes_lignes)
    couples = sorted(set(fermes) | set(ambigus), key=lambda k: (normaliser(k[0]), k[0], k[1]))
    with open(dossier_propre / "termes.csv", "w", encoding="utf-8", newline="") as f:
        redacteur = csv.writer(f, lineterminator="\n")
        redacteur.writerow(["terme", "role", "relations_associees", "nb_occurrences",
                            "nb_candidats_ambigus"])
        for couple in couples:
            redacteur.writerow([couple[0], couple[1], "|".join(sorted(relations[couple])),
                                fermes[couple], ambigus[couple]])
    return len(couples), sum(1 for c in couples if fermes[c] == 0)


# ---------------------------------------------------------------------------
# Outils de mise en forme du rapport
# ---------------------------------------------------------------------------

def echapper_markdown(texte):
    """Échappe les barres verticales, qui couperaient une cellule. Retourne une chaîne."""
    return str(texte).replace("|", "\\|")


def tableau(entete, lignes):
    """Construit un tableau Markdown. Retourne une liste de lignes."""
    sortie = ["| " + " | ".join(entete) + " |", "|" + "---|" * len(entete)]
    for ligne in lignes:
        sortie.append("| " + " | ".join(echapper_markdown(c) for c in ligne) + " |")
    return sortie


def tableau_ou_aucun(entete, lignes, mot="Aucun."):
    """Tableau Markdown, ou une phrase si la liste est vide. Retourne une liste de lignes."""
    return tableau(entete, lignes) if lignes else [mot]


# ---------------------------------------------------------------------------
# Rapport : une fonction par section
# ---------------------------------------------------------------------------

def section_comptes(fichiers, toutes_lignes):
    """Section 1 : comptes par fichier. Retourne une liste de lignes."""
    corps = []
    for fichier in fichiers:
        lignes = fichier["lignes"]
        etiquettes = sorted({l["relation"] for l in lignes})
        n_train = sum(l["split"] == "train" for l in lignes)
        n_ambigus = sum(l["ambigu"] == "oui" for l in lignes)
        conforme = (fichier["n_lignes"] == config.LIGNES_ATTENDUES
                    and not fichier["anomalies"] and len(etiquettes) == 1)
        corps.append([fichier["nom"], ", ".join(etiquettes), fichier["n_lignes"], len(lignes),
                      n_train, len(lignes) - n_train, n_ambigus, len(fichier["anomalies"]),
                      "OK" if conforme else "À VÉRIFIER"])
    sortie = ["## 1. Comptes par fichier", ""]
    sortie += tableau(["fichier", "relation", "lignes", "parsées", "train", "test", "ambiguës",
                       "anomalies", "statut"], corps)
    total_lignes = sum(f["n_lignes"] for f in fichiers)
    return sortie + ["", f"Total : {len(toutes_lignes)} syntagmes parsés sur {total_lignes} lignes.", ""]


def section_anomalies(fichiers):
    """Section 2 : lignes malformées. Retourne une liste de lignes."""
    corps = []
    for fichier in fichiers:
        for numero, message, texte in fichier["anomalies"]:
            corps.append([fichier["nom"], numero, message, f"`{texte}`"])
    for fichier in fichiers:
        etiquettes = Counter(l["relation"] for l in fichier["lignes"])
        if len(etiquettes) > 1:
            detail = ", ".join(f"{k} ({v})" for k, v in sorted(etiquettes.items()))
            corps.append([fichier["nom"], "-", "plusieurs étiquettes de relation", detail])
    sortie = ["## 2. Lignes malformées et anomalies", ""]
    return sortie + tableau_ou_aucun(["fichier", "ligne", "problème", "contenu"], corps,
                                     "Aucune.") + [""]


def section_ambigus(fichiers):
    """Section 3 : syntagmes à plusieurs prépositions. Retourne une liste de lignes."""
    sortie = ["## 3. Cas ambigus (plusieurs prépositions)", "",
              "Non tranchés ici : résolution via la base de connaissances à l'étape 2 (papier, §4.1). "
              "Ces lignes ont A, B, det et definitude vides dans les CSV nettoyés ; les candidats sont "
              "dans la colonne `candidats`.", ""]
    corps = []
    for fichier in fichiers:
        for ligne in fichier["lignes"]:
            if ligne["ambigu"] != "oui":
                continue
            candidats = "<br>".join(
                f"A=`{c['A']}` · B=`{c['B']}` ({c['preposition']}; {c['det']}+{c['definitude']})"
                for c in ligne["candidats"])
            corps.append([fichier["nom"], ligne["ligne"], ligne["split"],
                          f"**{ligne['syntagme']}**", candidats])
    return sortie + tableau_ou_aucun(["fichier", "ligne", "split", "syntagme",
                                      "découpages candidats"], corps) + [""]


def section_doublons_intra(fichiers):
    """Section 4 : doublons exacts dans un même fichier. Retourne une liste de lignes."""
    corps = []
    for fichier in fichiers:
        positions = defaultdict(list)
        for ligne in fichier["lignes"]:
            positions[ligne["syntagme"]].append(ligne)
        for syntagme, occurrences in positions.items():
            if len(occurrences) > 1:
                ou = ", ".join(f"{l['ligne']} ({l['split']})" for l in occurrences)
                corps.append([fichier["nom"], f"`{syntagme}`", ou])
    sortie = ["## 4. Doublons exacts intra-fichier", ""]
    return sortie + tableau_ou_aucun(["fichier", "syntagme", "lignes"], corps) + [""]


def section_doublons_inter(fichiers):
    """Section 5 : même syntagme dans plusieurs types. Retourne une liste de lignes."""
    sortie = ["## 5. Doublons inter-fichiers (classification multiple)", "",
              "Même syntagme (après normalisation casse/espaces/NFC) présent dans plusieurs types. "
              "À arbitrer manuellement ; rien n'est supprimé.", ""]
    par_forme = defaultdict(list)
    for fichier in fichiers:
        for ligne in fichier["lignes"]:
            par_forme[normaliser(ligne["syntagme"])].append((fichier["nom"], ligne))
    corps = []
    for forme in sorted(par_forme):
        occurrences = par_forme[forme]
        if len({nom for nom, _ in occurrences}) > 1:
            ou = "<br>".join(f"{nom} l.{l['ligne']} ({l['split']})" for nom, l in occurrences)
            corps.append([f"`{occurrences[0][1]['syntagme']}`", ou])
    return sortie + tableau_ou_aucun(["syntagme", "occurrences"], corps) + [""]


def section_doublons_paires(fichiers):
    """Section 6 : paires (A, B) identiques après normalisation. Retourne une liste de lignes."""
    sortie = ["## 6. Doublons de la paire (A, B) normalisée", "",
              "Paires identiques après normalisation (minuscules, NFC, espaces, apostrophes), "
              "que le syntagme de surface soit identique ou non. Les lignes ambiguës sont exclues. "
              "Une même paire avec des déterminants différents dans deux types (ex. « photo de famille » "
              "vs « photo d'une famille ») est précisément le cas que le trait de définitude doit séparer.", ""]
    par_paire = defaultdict(list)
    for fichier in fichiers:
        for ligne in fichier["lignes"]:
            if ligne["ambigu"] == "non" and ligne["A"]:
                par_paire[(normaliser(ligne["A"]), normaliser(ligne["B"]))].append(
                    (fichier["nom"], ligne))
    corps = []
    for paire in sorted(par_paire):
        occurrences = par_paire[paire]
        if len(occurrences) <= 1:
            continue
        meme_surface = len({normaliser(l["syntagme"]) for _, l in occurrences}) == 1
        meme_type = len({nom for nom, _ in occurrences}) == 1
        nature = ("même syntagme" if meme_surface else "surfaces différentes") \
            + (", même type" if meme_type else ", types différents")
        ou = "<br>".join(
            f"`{l['syntagme']}` — {nom} l.{l['ligne']} ({l['split']}, {l['det']}+{l['definitude']})"
            for nom, l in occurrences)
        corps.append([f"{paire[0]} / {paire[1]}", nature, ou])
    return sortie + tableau_ou_aucun(["paire A / B", "nature", "occurrences"], corps) + [""]


def section_diversite(fichiers):
    """Section 7 : diversité lexicale par type. Retourne une liste de lignes."""
    seuil = config.SEUIL_REPETITION
    sortie = ["## 7. Diversité lexicale par type", "",
              f"Nombre de termes A et B distincts (formes normalisées, lignes non ambiguës) et termes "
              f"apparaissant au moins {seuil} fois dans un même type.", ""]
    corps = []
    for fichier in fichiers:
        lignes = [l for l in fichier["lignes"] if l["ambigu"] == "non" and l["A"]]
        compte_a = Counter(normaliser(l["A"]) for l in lignes)
        compte_b = Counter(normaliser(l["B"]) for l in lignes)
        repetes_a = ", ".join(f"{t} ({n})" for t, n in
                              sorted(compte_a.items(), key=lambda kv: (-kv[1], kv[0])) if n >= seuil)
        repetes_b = ", ".join(f"{t} ({n})" for t, n in
                              sorted(compte_b.items(), key=lambda kv: (-kv[1], kv[0])) if n >= seuil)
        corps.append([fichier["nom"], len(lignes), len(compte_a), len(compte_b),
                      sum(1 for n in compte_a.values() if n >= 2),
                      sum(1 for n in compte_b.values() if n >= 2),
                      repetes_a or "—", repetes_b or "—"])
    sortie += tableau(["fichier", "n", "A distincts", "B distincts", "A vus ≥2 fois",
                       "B vus ≥2 fois", f"A répétés (≥{seuil})", f"B répétés (≥{seuil})"], corps)
    return sortie + [""]


def section_definitude(fichiers):
    """Section 8 : répartition des traits de définitude. Retourne une liste de lignes."""
    sortie = ["## 8. Répartition des traits de définitude par type", "",
              "Règles (§4.4.2) : Det = du, de la, de l', des, d'un, d'une ; NoDet = de, d' ; "
              "Def = déterminant défini ; NoDef = absence de déterminant ou indéfini ; "
              "B à majuscule initiale (entité nommée) ⇒ Def forcé. Lignes ambiguës exclues.", ""]
    corps, totaux = [], Counter()
    for fichier in fichiers:
        comptes = Counter(f"{l['det']}+{l['definitude']}" for l in fichier["lignes"]
                          if l["ambigu"] == "non" and l["A"])
        totaux.update(comptes)
        corps.append([fichier["nom"]] + [comptes[c] for c in COMBINAISONS_DEFINITUDE])
    corps.append(["**total**"] + [f"**{totaux[c]}**" for c in COMBINAISONS_DEFINITUDE])
    sortie += tableau(["fichier"] + COMBINAISONS_DEFINITUDE, corps)

    sortie += ["", "Contrôle des exemples du papier :", ""]
    for syntagme, attendu in EXEMPLES_PAPIER:
        candidat = decoupages_possibles(syntagme)[0]
        obtenu = f"{candidat['det']}+{candidat['definitude']}"
        verdict = "OK" if obtenu == attendu else "ÉCHEC, attendu " + attendu
        sortie.append(f"- {syntagme} → {obtenu} ({verdict})")
    return sortie + [""]


def section_termes(n_termes, n_termes_seulement_ambigus):
    """Section 9 : fichier des termes. Retourne une liste de lignes."""
    return ["## 9. Fichier des termes", "",
            f"`data/corpus/clean/termes.csv` : {n_termes} couples (terme, rôle) distincts, formes originales "
            f"conservées. `nb_occurrences` compte les lignes non ambiguës ; `nb_candidats_ambigus` compte "
            f"les apparitions comme candidat d'une ligne ambiguë. {n_termes_seulement_ambigus} terme(s) "
            f"n'existent que comme candidats.", ""]


def construire_rapport(fichiers, n_termes, n_termes_seulement_ambigus, source):
    """Assemble le rapport de contrôle. Retourne le texte Markdown complet."""
    toutes_lignes = [l for f in fichiers for l in f["lignes"]]
    lignes = ["# Rapport de contrôle du corpus", "",
              f"Généré par `src/corpus_check.py` sur `{source}/`. Rien n'a été supprimé ni modifié dans "
              f"`{source}/` : ce rapport signale, les décisions restent manuelles.", ""]
    lignes += section_comptes(fichiers, toutes_lignes)
    lignes += section_anomalies(fichiers)
    lignes += section_ambigus(fichiers)
    lignes += section_doublons_intra(fichiers)
    lignes += section_doublons_inter(fichiers)
    lignes += section_doublons_paires(fichiers)
    lignes += section_diversite(fichiers)
    lignes += section_definitude(fichiers)
    lignes += section_termes(n_termes, n_termes_seulement_ambigus)
    return "\n".join(lignes)


def main():
    analyseur = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    analyseur.add_argument("--raw", type=Path, default=config.DOSSIER_CORPUS_BRUT,
                           help="dossier des CSV source")
    analyseur.add_argument("--clean", type=Path, default=config.DOSSIER_CORPUS_PROPRE,
                           help="dossier des CSV nettoyés")
    analyseur.add_argument("--report", type=Path,
                           default=config.DOSSIER_RAPPORTS / "rapport_corpus.md",
                           help="chemin du rapport Markdown")
    arguments = analyseur.parse_args()
    dossier_brut, dossier_propre, chemin_rapport = (
        p.resolve() for p in (arguments.raw, arguments.clean, arguments.report))
    if dossier_propre == dossier_brut:
        analyseur.error("--clean doit différer de --raw (les sources ne sont jamais réécrites)")
    dossier_propre.mkdir(parents=True, exist_ok=True)
    chemin_rapport.parent.mkdir(parents=True, exist_ok=True)

    fichiers = []
    for chemin in sorted(dossier_brut.glob("*.csv")):
        lignes, anomalies = traiter_fichier(chemin)
        n_lignes = len(chemin.read_bytes().splitlines())
        if n_lignes != config.LIGNES_ATTENDUES:
            anomalies.insert(0, ("-", f"{n_lignes} lignes au lieu de {config.LIGNES_ATTENDUES}", ""))
        fichiers.append({"nom": chemin.stem, "lignes": lignes, "anomalies": anomalies,
                         "n_lignes": n_lignes})
        ecrire_csv_propre(dossier_propre, chemin.stem, lignes)

    toutes_lignes = [l for f in fichiers for l in f["lignes"]]
    n_termes, n_seulement_ambigus = ecrire_termes(dossier_propre, toutes_lignes)
    rapport = construire_rapport(fichiers, n_termes, n_seulement_ambigus,
                                 chemin_relatif(dossier_brut))
    chemin_rapport.write_text(rapport + "\n", encoding="utf-8")

    n_ambigus = sum(l["ambigu"] == "oui" for l in toutes_lignes)
    n_anomalies = sum(len(f["anomalies"]) for f in fichiers)
    print(f"{len(fichiers)} fichiers, {len(toutes_lignes)} syntagmes, {n_ambigus} ambigus, "
          f"{n_anomalies} anomalies.")
    print(f"Rapport : {chemin_relatif(chemin_rapport)}")


if __name__ == "__main__":
    main()
