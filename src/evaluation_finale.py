#!/usr/bin/env python3
"""Évaluation finale de la configuration retenue : somme · arbre · descente.

Deux temps, séparés pour que le test ne soit lu qu'UNE fois :

  1. `python3 src/evaluation_finale.py` réapprend les quinze arbres sur les 750
     exemples d'entraînement, classe les 450 exemples de test par descente, et écrit
     les prédictions complètes (chemin de la descente, réponse de chaque arbre) dans
     data/resultats/predictions_finales.json, puis le rapport.
  2. `python3 src/evaluation_finale.py --rapport-seulement` reconstruit le rapport
     depuis ce fichier, sans relire le test ni reclasser quoi que ce soit. C'est ce
     qui permet de retoucher l'analyse sans rouvrir le test.

Aucune configuration de contrôle n'est évaluée ici. Les chiffres du plus proche voisin
et de la méthode à seuil sont des résultats DÉJÀ obtenus, figés dans classify.py ; ceux de
l'article sont ceux du Tableau 3.

Aucun appel réseau.

Usage : python3 src/evaluation_finale.py [--rapport-seulement]
"""

import argparse
import csv
import json
import statistics
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone

import classify
import config
import grasp
import signatures as sig


# F1 publiés ou déjà mesurés, pour la mise en regard.
F1_ARTICLE = classify.ARTICLE_F1
F1_SEUIL = classify.ANCIEN_F1
F1_VOISIN = 0.585


def f1_signatures_ponderees():
    """F1 de test des signatures pondérées, relu de ses prédictions. Retourne un
    flottant, ou None si l'évaluation n'a pas été faite.

    Lit le fichier de prédictions déjà produit par evaluation_signatures.py : c'est un
    résultat acquis, pas une relecture du test."""
    if not config.FICHIER_PREDICTIONS_SIGNATURES.exists():
        return None
    enregistre = json.loads(
        config.FICHIER_PREDICTIONS_SIGNATURES.read_text(encoding="utf-8"))
    return enregistre["macro_stricte"]["f1"]

# Méthode à seuil, mesurée sur le même test (commit 7150875) : 180 erreurs, dont 104
# attribuées à la polysémie en attribution exclusive, soit 57,8 %.
SEUIL_ERREURS = 180
SEUIL_PART_POLYSEMIE = 0.578
# Taux d'erreur de la méthode à seuil selon que l'exemple contient un terme polysémique
# (A ou B avec au moins 2 raffinements de sens dans JDM) : 152 erreurs sur 371 exemples
# contre 28 erreurs sur 79.
SEUIL_TAUX_POLYSEMIQUE = (152, 371)
SEUIL_TAUX_AUTRES = (28, 79)

# Écart relatif maximal au meilleur score pour qu'un type compte comme « à égalité »,
# critère de classe multiple de l'article (§4.3).
TOLERANCE_CLASSE_MULTIPLE = 0.05

# En deçà de ce nombre de symboles, une signature est jugée trop pauvre pour décider.
SIGNATURE_PAUVRE = config.SEUIL_SIGNATURE_QUASI_VIDE

# Nombre d'exemples listés par type quand la descente va plus bas que la racine, et
# nombre d'erreurs confiantes commentées.
EXEMPLES_PAR_TYPE = 4
ERREURS_COMMENTEES = 10

# Ordre d'attribution exclusive des causes d'échec : du plus spécifique au plus général.
PRIORITE_CAUSES = ("défaut de connaissance", "dispersion morphologique",
                   "classe multiple", "polysémie", "autre")

# Commentaires des erreurs confiantes, écrits à la main après lecture des résultats.
COMMENTAIRES = {
    "ordinateur du développeur":
        "`r_own-1` contre `r_product_of`, 0,6 % d'écart, le bon type est 2ᵉ. Le B est une "
        "profession, et l'entraînement en donne aux deux types (`musicien`, `banquier` "
        "possèdent ; `boulanger`, `écrivain` produisent). Le profil de B ne départage pas ; "
        "un développeur possède un ordinateur et en écrit les programmes, seul le A "
        "(2 raffinements) pourrait trancher, et il ne le fait pas.",
    "article du journaliste":
        "La même paire, à l'envers : `r_product_of` attendu, `r_own-1` prédit, 1,7 % "
        "d'écart. « article » a 6 raffinements de sens (écrit de presse, pièce de "
        "marchandise…) : son profil mélange des choses produites et des choses possédées. "
        "Confusion la plus fréquente du test (`r_product_of` → `r_own-1`, 7 cas).",
    "rapport de l'expert":
        "`r_product_of` est 3ᵉ, à égalité avec `r_own-1` (0,727) derrière `r_processus_agent` "
        "(3,9 % d'écart). « rapport » a 14 raffinements de sens, le record de la liste. "
        "Lecture défendable : « le rapport de l'expert » comme acte de rapporter est un "
        "processus dont l'expert est l'agent ; le corpus retient le résultat, le texte.",
    "traduction de l'interprète":
        "Ici l'écart est net (8,5 %, le bon type est 4ᵉ) et pas du tout un quasi-ex aequo. "
        "Nom d'action : « traduction » désigne le geste autant que son résultat, et sa "
        "signature est celle d'un processus. Ambiguïté classique action/résultat, que le "
        "corpus tranche du côté résultat.",
    "plat du cuisinier":
        "0,3 % d'écart entre `r_own-1` et `r_product_of` : une égalité quasi parfaite. "
        "« plat » a 12 raffinements (mets, ustensile, adjectif…) et « cuisinier » est une "
        "profession, comme dans « ordinateur du développeur ». Le plat que cuisine le "
        "cuisinier et le plat qu'il possède sont deux lectures que le texte ne distingue pas.",
    "couverture du livre":
        "`r_holo` attendu, `r_topic` prédit, le bon type est 3ᵉ à 2,4 %. « couverture » a "
        "12 raffinements (celle d'un livre, d'un lit, médiatique, d'assurance…) et le côté B "
        "porte 88 symboles, l'une des signatures les plus riches. Les deux exemples "
        "`r_holo` → `r_topic` de cette liste ont pour B une œuvre (livre, film).",
    "bronzage de l'été":
        "Trois types à moins de 3 % : `r_processus_patient` (gagnant), `r_processus_agent`, "
        "`r_has_causatif` (attendu). Les signatures sont les plus petites de la liste (41 et "
        "51 symboles) et « bronzage » n'a aucun raffinement : peu de matière pour trancher. "
        "La descente s'arrête à la racine de `r_processus_patient` (poids 50).",
    "album du groupe":
        "La plus nette des dix erreurs de sens : le bon type est **6ᵉ**, à 9,0 % du "
        "gagnant. « groupe » a 10 raffinements de sens (ensemble musical, groupe de "
        "personnes, groupe chimique…), et la signature qui en résulte ne ressemble pas au "
        "créateur que suppose `r_product_of` (`boulanger`, `écrivain`). Vraisemblablement "
        "un cas de polysémie du B, la cause que le détecteur lui attribue.",
    "scène du film":
        "`r_holo` attendu, `r_topic` prédit, 4,1 % d'écart, même schéma que « couverture du "
        "livre » : le B est une œuvre, et dans l'entraînement `r_topic` a des B de genre ou "
        "de discipline (`roman de science-fiction`, `film d'aventure`). Une scène est une "
        "partie du film, mais la signature de « film » attire vers le thème.",
    "salon de thé":
        "Composé lexicalisé, étiqueté `r_topic` (comme `salon de coiffure` à l'entraînement). "
        "Le B « thé » est une boisson, le B typique de `r_quantificateur` (`tasse de café`, "
        "`verre de lait`), et l'écart est de 0,9 %. Seule une entrée JDM du syntagme entier "
        "lèverait l'ambiguïté ; les signatures de A et de B, séparément, ne le peuvent pas.",
}


# ---------------------------------------------------------------------------
# Temps 1 : évaluer et enregistrer
# ---------------------------------------------------------------------------

def apprendre_arbres(signatures):
    """Réapprend les quinze arbres sur les 750 exemples d'entraînement.
    Retourne (nœuds, racines)."""
    depart = grasp.feuilles_de_depart(grasp.charger_lignes("train"), signatures)
    noeuds, racines, _ = grasp.construire_foret(depart)
    grasp.ecrire_arbres(noeuds, racines)
    return noeuds, racines


def evaluer_le_test(signatures, noeuds, racines):
    """Classe les 450 exemples de test par descente, une seule fois.
    Retourne (prédictions, durée)."""
    test = grasp.charger_lignes("test")
    lignes = [ligne for rt in sorted(test) for ligne in test[rt]]
    return classify.lancer_descente(lignes, signatures, noeuds, racines)


def ecrire_predictions(predictions, evaluation, duree):
    """Écrit data/resultats/predictions_finales.json. Retourne le chemin."""
    charge = {
        "split": "test (450 exemples, 30 par type), lu une seule fois",
        "configuration": {"representation": config.REPRESENTATION,
                          "structure": config.STRUCTURE,
                          "classification": config.CLASSIFICATION},
        "arbres": config.FICHIER_ARBRES.name, "duree_classement": duree,
        "genere_le": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "macro_stricte": {k: evaluation[k] for k in
                          ("precision", "rappel", "f1", "exactitude")},
        "predictions": predictions,
    }
    config.FICHIER_PREDICTIONS_FINALES.parent.mkdir(parents=True, exist_ok=True)
    with open(config.FICHIER_PREDICTIONS_FINALES, "w", encoding="utf-8", newline="") as f:
        json.dump(charge, f, ensure_ascii=False, indent=1)
        f.write("\n")
    return config.FICHIER_PREDICTIONS_FINALES


def lire_predictions():
    """Relit les prédictions enregistrées. Retourne (prédictions, durée)."""
    charge = json.loads(config.FICHIER_PREDICTIONS_FINALES.read_text(encoding="utf-8"))
    return charge["predictions"], charge["duree_classement"]


# ---------------------------------------------------------------------------
# Mesures de la descente
# ---------------------------------------------------------------------------

def nature_de_l_arret(prediction):
    """Feuille, racine ou nœud interne plus bas. Retourne une chaîne."""
    arret = prediction["noeud_arret"]
    if arret["feuille"]:
        return "feuille"
    return "racine" if arret["profondeur"] == 0 else "nœud interne"


def statistiques_descente(predictions, tailles):
    """Profondeur d'arrêt, part des racines, poids relatif, coût. Retourne un dict."""
    natures = Counter(nature_de_l_arret(p) for p in predictions)
    justes = Counter(nature_de_l_arret(p) for p in predictions if p["correct"])
    toutes = [r for p in predictions for r in p["reponses"]]
    return {
        "natures": natures, "justes": justes,
        "profondeurs": Counter(p["noeud_arret"]["profondeur"] for p in predictions),
        "profondeurs_toutes": Counter(r["profondeur"] for r in toutes),
        "poids_relatif": statistics.fmean(
            p["noeud_arret"]["poids"] / tailles[p["noeud_arret"]["rt"]]
            for p in predictions),
        "poids_relatif_toutes": statistics.fmean(r["poids"] / tailles[r["rt"]]
                                                 for r in toutes),
        "calculs": statistics.fmean(p["calculs"] for p in predictions),
        "calculs_max": max(p["calculs"] for p in predictions),
        "profondeur_moyenne": statistics.fmean(p["noeud_arret"]["profondeur"]
                                               for p in predictions),
    }


def descentes_profondes(predictions):
    """Prédictions dont la descente a dépassé la racine, par type prédit.
    Retourne relation -> liste de prédictions."""
    par_type = defaultdict(list)
    for prediction in predictions:
        if prediction["noeud_arret"]["profondeur"] >= 1:
            par_type[prediction["predit"]].append(prediction)
    return par_type


# ---------------------------------------------------------------------------
# Analyse des échecs (mêmes détecteurs que archive/rapport_evaluation.md)
# ---------------------------------------------------------------------------

def indices_de_cause(collecte, signatures):
    """Prépare les détecteurs de cause. Retourne un dict de fonctions."""
    def raffinements(terme):
        return len((collecte.get(terme) or {}).get("raffinements") or [])

    def singulier_mieux_dote(terme):
        diagnostic = (collecte.get(terme) or {}).get("diagnostic_singulier")
        return bool(diagnostic and diagnostic.get("existe") and diagnostic.get("H_taille"))

    def pauvre(terme):
        return len(signatures.get(terme, {terme})) < SIGNATURE_PAUVRE

    return {"raffinements": raffinements, "singulier": singulier_mieux_dote,
            "pauvre": pauvre}


def score_attendu(prediction):
    """Score de la réponse de l'arbre du type attendu. Retourne un flottant."""
    return next(r["score"] for r in prediction["reponses"]
                if r["rt"] == prediction["attendu"])


def ecart_au_bon_type(prediction):
    """Écart relatif entre le score gagnant et celui du type attendu. Retourne un flottant."""
    premier = prediction["score"]
    return (premier - score_attendu(prediction)) / premier if premier else 1.0


def est_polysemique(prediction, indices):
    """Dit si A ou B a au moins deux raffinements de sens dans JDM. Retourne un booléen."""
    return (indices["raffinements"](prediction["A"]) >= 2
            or indices["raffinements"](prediction["B"]) >= 2)


def drapeaux_de_cause(prediction, indices):
    """Toutes les causes possibles d'un échec, non exclusives. Retourne un ensemble."""
    a, b = prediction["A"], prediction["B"]
    drapeaux = set()
    if indices["pauvre"](a) or indices["pauvre"](b):
        drapeaux.add("défaut de connaissance")
    if indices["singulier"](a) or indices["singulier"](b):
        drapeaux.add("dispersion morphologique")
    if ecart_au_bon_type(prediction) <= TOLERANCE_CLASSE_MULTIPLE:
        drapeaux.add("classe multiple")
    if est_polysemique(prediction, indices):
        drapeaux.add("polysémie")
    return drapeaux or {"autre"}


def cause_principale(drapeaux):
    """Retient une seule cause par ordre de priorité. Retourne une chaîne."""
    for cause in PRIORITE_CAUSES:
        if cause in drapeaux:
            return cause
    return "autre"


def analyser_echecs(predictions, indices):
    """Classe les erreurs par cause. Retourne (échecs, exclusives, non exclusives)."""
    echecs = []
    for prediction in predictions:
        if prediction["correct"]:
            continue
        drapeaux = drapeaux_de_cause(prediction, indices)
        echec = dict(prediction)
        echec["drapeaux"] = sorted(drapeaux)
        echec["cause"] = cause_principale(drapeaux)
        echecs.append(echec)
    exclusives = Counter(e["cause"] for e in echecs)
    non_exclusives = Counter(d for e in echecs for d in e["drapeaux"])
    return echecs, exclusives, non_exclusives


def taux_d_erreur_polysemie(predictions, indices):
    """Erreurs et effectifs des exemples polysémiques et des autres.
    Retourne ((erreurs, effectif), (erreurs, effectif))."""
    poly = [p for p in predictions if est_polysemique(p, indices)]
    autres = [p for p in predictions if not est_polysemique(p, indices)]
    compte = lambda lot: (sum(1 for p in lot if not p["correct"]), len(lot))
    return compte(poly), compte(autres)


# ---------------------------------------------------------------------------
# Mise en forme
# ---------------------------------------------------------------------------

fr, pct, tableau = grasp.fr, grasp.pct, grasp.tableau
ecart_signe = classify.ecart_signe


def taux(couple):
    """Part d'erreurs d'un couple (erreurs, effectif). Retourne un flottant."""
    return couple[0] / couple[1] if couple[1] else 0.0


def libelle_arret(prediction):
    """Nœud d'arrêt en une expression : poids et profondeur. Retourne une chaîne."""
    arret = prediction["noeud_arret"]
    return f"{'feuille' if arret['feuille'] else 'poids ' + str(arret['poids'])}, prof. {arret['profondeur']}"


# ---------------------------------------------------------------------------
# Rapport : une fonction par section
# ---------------------------------------------------------------------------

def section_dispositif(n_test, duree):
    """1 : la configuration et le protocole. Retourne des lignes."""
    return ["## 1. Configuration et protocole", "",
            f"- **Configuration** : `{config.REPRESENTATION}` · `{config.STRUCTURE}` · "
            f"`{config.CLASSIFICATION}`, choisie en validation croisée "
            "(`rapport_grille.md`). Aucune configuration de contrôle n'est évaluée ici.",
            "- **Signatures : les BINAIRES**, celles de `data/signatures/` "
            "(`H 20 · binaire · T0 · TRT tous · SST toutes`) — chaque symbole présent "
            "vaut 1, et le terme lui-même figure dans sa signature, sans préfixe. Ce "
            "rapport évalue **cette seule représentation** sur le test. Les **signatures "
            "retenues** depuis en validation croisée "
            "(`H 20 · jdm · T2 · TRT tous · SST toutes`, "
            "`rapport_signatures_variantes.md`) sont évaluées sur le même test dans "
            "`rapport_final_signatures.md` ; les deux F1 sont mis en regard au §2.",
            "- **Attention en comparant les deux** : elles diffèrent par **deux** réglages "
            "à la fois, les poids (`binaire` → `jdm`) et le symbole du terme (`T0` présent "
            "→ `T2` retiré). L'écart de test ne s'attribue donc pas à la seule "
            "pondération ; sa décomposition est au §2 de `rapport_final_signatures.md`.",
            "- **Arbres** : quinze, un par type, réappris sur les 750 exemples "
            "d'entraînement ; un nœud fusionné est la somme des vecteurs de comptes de "
            "ses enfants. Lien de construction : minimum des deux côtés.",
            "- **Classification** : descente depuis la racine de chaque arbre, vers le "
            "meilleur enfant tant qu'il fait **strictement** mieux ; le meilleur nœud "
            "d'arrêt sur les quinze arbres donne le type. Score : formule 3, moyenne des "
            "deux côtés.",
            f"- **Test** : {n_test} exemples, 30 par type, **lus une seule fois**. "
            f"Classement en {fr(duree, 2)} s. Ce rapport se reconstruit depuis "
            f"`{config.FICHIER_PREDICTIONS_FINALES.relative_to(config.RACINE).as_posix()}`"
            " sans relire le test.",
            "- **Références** : article (Tableau 3), méthode à seuil (fusion « les deux » "
            "à 0,50, classification exhaustive) et plus proche voisin sur les feuilles, "
            "tous trois **relus** de résultats déjà obtenus sur ce même test.", ""]


def section_resultats(evaluation):
    """2 : macro, puis détail par type. Retourne des lignes."""
    f1 = evaluation["f1"]
    lignes = ["## 2. Résultats", "",
              f"**F1 macro : {fr(f1)}** (précision {fr(evaluation['precision'])}, rappel "
              f"{fr(evaluation['rappel'])}, exactitude {pct(evaluation['exactitude'])}, "
              f"{evaluation['corrects']} exemples justes sur {evaluation['total']}).", ""]
    corps_macro = [["**somme · arbre · descente, signatures binaires** (ce rapport) — "
                    "`binaire · T0`", f"**{fr(f1)}**", "—"]]
    f1_pondere = f1_signatures_ponderees()
    if f1_pondere is not None:
        corps_macro.append(["mêmes arbres, **signatures retenues** "
                            "(`rapport_final_signatures.md`) — `jdm · T2`",
                            fr(f1_pondere), ecart_signe(f1 - f1_pondere)])
    corps_macro += [["article", fr(F1_ARTICLE), ecart_signe(f1 - F1_ARTICLE)],
                    ["méthode à seuil", fr(F1_SEUIL), ecart_signe(f1 - F1_SEUIL)],
                    ["plus proche voisin", fr(F1_VOISIN), ecart_signe(f1 - F1_VOISIN)]]
    lignes += tableau(["", "F1 macro sur les 450 exemples de test",
                       "écart avec ce rapport"], corps_macro)
    if f1_pondere is not None:
        lignes += ["", "Les deux premières lignes sont la **même méthode** "
                   "(somme · arbre · descente) sur le **même test**, et ne diffèrent que "
                   f"par la construction des signatures. L'écart de "
                   f"{fr(abs(f1_pondere - f1))} n'est pas analysé ici : il mêle deux "
                   "réglages et n'est pas établi statistiquement. Voir le **§2 de "
                   "`rapport_final_signatures.md`**, qui le décompose."]
    corps = []
    for rt in sorted(evaluation["par_type"], key=lambda t: -evaluation["par_type"][t]["f1"]):
        d = evaluation["par_type"][rt]
        article = classify.ARTICLE_PAR_TYPE[rt]
        corps.append([f"`{rt}`", d["predits"], fr(100 * d["precision"], 1),
                      fr(100 * d["rappel"], 1), f"**{fr(d['f1'], 2)}**",
                      fr(article[2], 2), fr(classify.ANCIEN_PAR_TYPE[rt], 2),
                      fr(classify.VOISIN_PAR_TYPE[rt], 2),
                      ecart_signe(d["f1"] - article[2], 2)])
    corps.append(["**macro**", "", fr(100 * evaluation["precision"], 1),
                  fr(100 * evaluation["rappel"], 1), f"**{fr(f1, 3)}**",
                  fr(F1_ARTICLE), fr(F1_SEUIL), fr(F1_VOISIN),
                  ecart_signe(f1 - F1_ARTICLE, 3)])
    lignes += ["", "### 2.1 Détail par type", "",
               "Trié par F1. Les trois colonnes de référence sont des F1 ; « prédits » est "
               "le nombre de fois où le type est proposé, pour 30 attendus.", ""]
    lignes += tableau(["type", "prédits", "P (%)", "R (%)", "F1", "F1 article",
                       "F1 seuil", "F1 voisin", "écart article"], corps)
    meilleurs = sum(1 for rt, d in evaluation["par_type"].items()
                    if d["f1"] > classify.ARTICLE_PAR_TYPE[rt][2])
    lignes += ["", f"Le F1 dépasse celui de l'article pour {meilleurs} types sur "
                   f"{len(evaluation['par_type'])}.", ""]
    return lignes


def section_confusion(matrice, types):
    """3 : matrice de confusion, types numérotés. Retourne des lignes."""
    entete = ["attendu \\ prédit"] + [str(i + 1) for i in range(len(types))]
    corps = []
    for i, attendu in enumerate(types):
        cellules = [f"**{matrice[attendu][p]}**" if attendu == p
                    else (str(matrice[attendu][p]) if matrice[attendu][p] else "·")
                    for p in types]
        corps.append([f"{i + 1}. `{attendu}`"] + cellules)
    couples = sorted(((a, p, matrice[a][p]) for a in types for p in types
                      if a != p and matrice[a][p]), key=lambda c: (-c[2], c[0], c[1]))
    return (["## 3. Matrice de confusion", "",
             "Lignes : type attendu. Colonnes : type prédit, numérotés comme les lignes. "
             f"Aussi écrite dans `{config.FICHIER_MATRICE_FINALE.relative_to(config.RACINE).as_posix()}`.",
             ""]
            + tableau(entete, corps)
            + ["", "Confusions les plus fréquentes : "
               + ", ".join(f"`{a}` → `{p}` ({n})" for a, p, n in couples[:6]) + ".", ""])


def section_descente(stats, n):
    """4 : comportement de la descente. Retourne des lignes."""
    natures, justes = stats["natures"], stats["justes"]
    corps = []
    for nature in ("racine", "nœud interne", "feuille"):
        total = natures.get(nature, 0)
        corps.append([nature, total, pct(total / n),
                      f"{justes.get(nature, 0)} ({pct(justes.get(nature, 0) / total) if total else '—'})"])
    profondeurs = sorted(set(stats["profondeurs"]) | set(stats["profondeurs_toutes"]))
    lignes = ["## 4. La descente", "",
              f"- **Part des prédictions faites par une racine** : "
              f"{pct(natures.get('racine', 0) / n)}.",
              f"- **Poids relatif moyen du nœud gagnant** : {fr(stats['poids_relatif'], 2)} "
              "(poids du nœud divisé par le nombre d'exemples de son type ; 1 = tout le "
              f"type, 0,02 = une feuille). Sur les {15 * n} descentes, tous arbres "
              f"confondus : {fr(stats['poids_relatif_toutes'], 2)}.",
              f"- **Profondeur d'arrêt moyenne** (racine = 0) : "
              f"{fr(stats['profondeur_moyenne'], 1)} pour les prédictions.",
              f"- **Calculs de score par exemple** : {fr(stats['calculs'], 1)} en moyenne, "
              f"{stats['calculs_max']} au plus.", "",
              "### 4.1 Où la descente s'arrête", ""]
    lignes += tableau(["nœud d'arrêt de la prédiction", "prédictions", "part",
                       "justes (exactitude)"], corps)
    lignes += ["", "**Profondeur d'arrêt** (racine = 0) :", ""]
    lignes += tableau(["profondeur"] + [str(p) for p in profondeurs],
                      [["prédictions"] + [stats["profondeurs"].get(p, 0) for p in profondeurs],
                       ["toutes les descentes"]
                       + [stats["profondeurs_toutes"].get(p, 0) for p in profondeurs]])
    return lignes + [""]


def section_types_profonds(profonds, evaluation):
    """4.2 : les types dont la descente dépasse la racine, et sur quels exemples.
    Retourne des lignes."""
    corps, exemples = [], []
    for rt in sorted(profonds, key=lambda t: -len(profonds[t])):
        lot = profonds[rt]
        attendus_du_type = evaluation["par_type"][rt]["predits"]
        justes = sum(1 for p in lot if p["correct"])
        corps.append([f"`{rt}`", attendus_du_type, len(lot),
                      f"{justes} ({pct(justes / len(lot), 0)})",
                      max(p["noeud_arret"]["profondeur"] for p in lot)])
        pris = sorted(lot, key=lambda p: (-p["noeud_arret"]["profondeur"], p["syntagme"]))
        exemples.append(f"- `{rt}` : " + " ; ".join(
            f"« {p['syntagme']} » ({libelle_arret(p)}"
            + ("" if p["correct"] else f", attendu `{p['attendu']}`") + ")"
            for p in pris[:EXEMPLES_PAR_TYPE]))
    return (["### 4.2 Les types où la descente dépasse la racine", "",
             "Une prédiction est comptée dans le type qu'elle **propose**. « justes » : "
             "parmi les prédictions de ce type qui s'arrêtent sous la racine, celles où "
             "le type attendu était bien celui-là. Les exemples sont les plus profonds "
             f"(jusqu'à {EXEMPLES_PAR_TYPE} par type).", ""]
            + tableau(["type prédit", "prédictions", "dont sous la racine", "justes",
                       "profondeur max"], corps)
            + [""] + exemples + [""])


def section_echecs(echecs, exclusives, non_exclusives, total, taux_poly):
    """5 : échecs par cause et test de l'hypothèse de polysémie. Retourne des lignes."""
    n = len(echecs)
    poly_excl = exclusives.get("polysémie", 0)
    part = poly_excl / n if n else 0.0
    corps = []
    for cause in PRIORITE_CAUSES:
        corps.append([cause, exclusives.get(cause, 0),
                      pct(exclusives.get(cause, 0) / n) if n else "—",
                      non_exclusives.get(cause, 0)])
    (e_poly, n_poly), (e_autres, n_autres) = taux_poly
    baisse = part < SEUIL_PART_POLYSEMIE
    lignes = ["## 5. Analyse des cas d'échec", "",
              f"{n} erreurs sur {total} exemples (méthode à seuil : {SEUIL_ERREURS}). Mêmes "
              "détecteurs que `archive/rapport_evaluation.md` ; chaque erreur reçoit une cause "
              "unique par ordre de priorité, du plus spécifique au plus général :", "",
              "`" + "` → `".join(PRIORITE_CAUSES) + "`", ""]
    lignes += tableau(["cause", "attribution exclusive", "part des erreurs",
                       "présence (non exclusive)"], corps)
    lignes += ["",
               "### 5.1 Hypothèse : le profil moyen d'un type dilue la polysémie", "",
               f"**Part de la polysémie parmi les erreurs** : {pct(part)} "
               f"({poly_excl} sur {n}) contre {pct(SEUIL_PART_POLYSEMIE)} pour la méthode à "
               f"seuil. " + ("Elle baisse." if baisse else "Elle **ne baisse pas**."), "",
               "Cette part est fragile : la polysémie est la dernière cause dans l'ordre de "
               "priorité, donc sa part est un **résidu** — elle change dès que les autres "
               "causes changent, sans que la polysémie y soit pour rien. Le test direct est "
               "le taux d'erreur selon que l'exemple contient ou non un terme polysémique "
               "(A ou B avec au moins deux raffinements de sens dans JDM) :", ""]
    lignes += tableau(["", "exemples polysémiques", "exemples sans terme polysémique",
                       "écart"],
                      [["somme · arbre · descente", f"{e_poly} / {n_poly} "
                        f"({pct(taux((e_poly, n_poly)))})",
                        f"{e_autres} / {n_autres} ({pct(taux((e_autres, n_autres)))})",
                        ecart_signe(taux((e_poly, n_poly)) - taux((e_autres, n_autres)))],
                       ["méthode à seuil", f"{SEUIL_TAUX_POLYSEMIQUE[0]} / "
                        f"{SEUIL_TAUX_POLYSEMIQUE[1]} ({pct(taux(SEUIL_TAUX_POLYSEMIQUE))})",
                        f"{SEUIL_TAUX_AUTRES[0]} / {SEUIL_TAUX_AUTRES[1]} "
                        f"({pct(taux(SEUIL_TAUX_AUTRES))})",
                        ecart_signe(taux(SEUIL_TAUX_POLYSEMIQUE) - taux(SEUIL_TAUX_AUTRES))]])
    ecart_somme = taux((e_poly, n_poly)) - taux((e_autres, n_autres))
    ecart_seuil = taux(SEUIL_TAUX_POLYSEMIQUE) - taux(SEUIL_TAUX_AUTRES)
    lignes += ["",
               "Lecture : " + (
                   "l'écart entre exemples polysémiques et autres se **resserre** "
                   f"({ecart_signe(ecart_somme)} contre {ecart_signe(ecart_seuil)}), ce qui va "
                   "dans le sens de l'hypothèse."
                   if ecart_somme < ecart_seuil - 0.01 else
                   "l'écart entre exemples polysémiques et autres **ne se resserre pas** "
                   f"({ecart_signe(ecart_somme)} contre {ecart_signe(ecart_seuil)}) : "
                   "l'hypothèse n'est pas confirmée par ce test.")
               + " Le détecteur reste un indice, pas une preuve : un terme à raffinements "
               "peut être bien classé, et un terme sans raffinement peut être ambigu. Les "
               f"effectifs sont faibles côté « sans terme polysémique » ({n_autres} exemples),"
               " ce qui rend l'écart peu précis.", ""]
    return lignes


def commentaire_de(echec):
    """Commentaire d'une erreur confiante : écrit à la main s'il existe, sinon mécanique.
    Retourne une chaîne."""
    if echec["syntagme"] in COMMENTAIRES:
        return COMMENTAIRES[echec["syntagme"]]
    return (f"cause détectée : {echec['cause']} ; le type attendu est à "
            f"{pct(ecart_au_bon_type(echec))} du gagnant")


def rang_du_type_attendu(prediction):
    """Rang du type attendu parmi les réponses des quinze arbres, à partir de 1.
    Retourne un entier."""
    classees = sorted(prediction["reponses"], key=lambda r: -r["score"])
    return [r["rt"] for r in classees].index(prediction["attendu"]) + 1


def section_erreurs_confiantes(echecs):
    """6 : les dix erreurs les plus confiantes, commentées. Retourne des lignes."""
    retenues = sorted(echecs, key=lambda e: (-e["score"], e["syntagme"]))[:ERREURS_COMMENTEES]
    corps = [[f"« {e['syntagme']} »", f"`{e['attendu']}`", f"`{e['predit']}`",
              fr(e["score"]), fr(score_attendu(e)), libelle_arret(e), e["cause"]]
             for e in retenues]
    serrees = sum(1 for e in retenues if ecart_au_bon_type(e) <= TOLERANCE_CLASSE_MULTIPLE)
    rang_2 = sum(1 for e in retenues if rang_du_type_attendu(e) == 2)
    lignes = ["## 6. Les dix erreurs les plus confiantes", "",
              "Erreurs au score gagnant le plus élevé : le système s'est trompé avec "
              "assurance. Ce sont celles qui coûtent le plus cher, et celles qui renseignent "
              "le mieux sur ce qui manque à la base de connaissances.", "",
              f"**Attention à ce que « confiant » veut dire ici.** Le score absolu est haut "
              "quand les signatures sont riches, pas quand un type se détache : les scores des "
              "trois premiers types tiennent le plus souvent dans quelques centièmes. Pour "
              f"{serrees} de ces dix erreurs le type attendu est à moins de "
              f"{pct(TOLERANCE_CLASSE_MULTIPLE, 0)} du gagnant, et il est 2ᵉ pour {rang_2}. "
              "Ce sont donc surtout des égalités perdues, pas des erreurs assurées.", ""]
    lignes += tableau(["syntagme", "attendu", "prédit", "score gagnant", "score du bon type",
                       "nœud d'arrêt", "cause"], corps)
    lignes += [""]
    for rang, echec in enumerate(retenues, 1):
        lignes.append(f"{rang}. **« {echec['syntagme']} »** — {commentaire_de(echec)}")
    return lignes + [""]


def section_sorties():
    """7 : les fichiers écrits. Retourne des lignes."""
    return ["## 7. Sorties écrites", "",
            f"- `{config.FICHIER_PREDICTIONS_FINALES.relative_to(config.RACINE).as_posix()}` : "
            "pour chaque exemple, le chemin complet de la descente dans l'arbre gagnant, la "
            "réponse des quinze arbres et le nœud d'arrêt.",
            f"- `{config.FICHIER_MATRICE_FINALE.relative_to(config.RACINE).as_posix()}` : la "
            "matrice de confusion.",
            f"- `{config.FICHIER_ARBRES.relative_to(config.RACINE).as_posix()}` : les quinze "
            "arbres, 1485 nœuds.", ""]


def ecrire_matrice(matrice, types):
    """Écrit data/resultats/matrice_confusion_finale.csv. Retourne le chemin."""
    with open(config.FICHIER_MATRICE_FINALE, "w", encoding="utf-8", newline="") as f:
        redacteur = csv.writer(f, lineterminator="\n")
        redacteur.writerow(["attendu \\ prédit"] + list(types))
        for attendu in types:
            redacteur.writerow([attendu] + [matrice[attendu][p] for p in types])
    return config.FICHIER_MATRICE_FINALE


def construire_rapport(predictions, duree):
    """Écrit reports/rapport_final.md depuis les prédictions. Retourne le dict des mesures."""
    signatures = grasp.charger_signatures()
    noeuds, _ = grasp.charger_arbres()
    tailles = classify.tailles_des_types(noeuds)
    types = sorted({p["attendu"] for p in predictions})
    evaluation = classify.evaluer(predictions, types)
    matrice = classify.matrice_confusion(predictions, types)
    ecrire_matrice(matrice, types)
    indices = indices_de_cause(sig.charger_collecte(), signatures)
    echecs, exclusives, non_exclusives = analyser_echecs(predictions, indices)
    stats = statistiques_descente(predictions, tailles)

    lignes = ["# Évaluation finale : somme · arbre · descente", "",
              f"Configuration figée en validation croisée, évaluée une seule fois sur les "
              f"{len(predictions)} exemples de test.", ""]
    lignes += section_dispositif(len(predictions), duree)
    lignes += section_resultats(evaluation)
    lignes += section_confusion(matrice, types)
    lignes += section_descente(stats, len(predictions))
    lignes += section_types_profonds(descentes_profondes(predictions), evaluation)
    lignes += section_echecs(echecs, exclusives, non_exclusives, len(predictions),
                             taux_d_erreur_polysemie(predictions, indices))
    lignes += section_erreurs_confiantes(echecs)
    lignes += section_sorties()
    config.FICHIER_RAPPORT_FINAL.write_text("\n".join(lignes), encoding="utf-8")
    print(f"Rapport : {config.FICHIER_RAPPORT_FINAL}", flush=True)
    return {"evaluation": evaluation, "stats": stats, "echecs": len(echecs)}


# ---------------------------------------------------------------------------
# Enchaînement
# ---------------------------------------------------------------------------

def main():
    analyseur = argparse.ArgumentParser(description="Évaluation finale, une lecture du test.")
    analyseur.add_argument("--rapport-seulement", action="store_true",
                           dest="rapport_seulement",
                           help="reconstruit le rapport sans relire le test")
    options = analyseur.parse_args()

    if options.rapport_seulement:
        predictions, duree = lire_predictions()
        print(f"Prédictions relues : {len(predictions)}. Test non lu.", flush=True)
    else:
        signatures = grasp.charger_signatures()
        noeuds, racines = apprendre_arbres(signatures)
        print(f"Arbres réappris : {len(noeuds)} nœuds. Lecture du test.", flush=True)
        predictions, duree = evaluer_le_test(signatures, noeuds, racines)
        types = sorted({p["attendu"] for p in predictions})
        evaluation = classify.evaluer(predictions, types)
        ecrire_predictions(predictions, evaluation, duree)
        print(f"F1 macro {fr(evaluation['f1'])}, exactitude "
              f"{pct(evaluation['exactitude'])}, {fr(duree, 2)} s.", flush=True)
    mesures = construire_rapport(predictions, duree)
    print(f"{mesures['echecs']} erreurs analysées.", flush=True)


if __name__ == "__main__":
    main()
