#!/usr/bin/env python3
"""Classification par descente dans les arbres, et évaluation sur le test (phase B).

Score d'une forme « A de B » contre un nœud < sL, sR > (formule 3 de l'article) :

    score = ½ × [ sim(s(A), sL) + sim(s(B), sR) ]

C'est la MOYENNE, alors que la construction des arbres fusionne sur le MINIMUM des deux
côtés. L'asymétrie est voulue : exigeant pour fusionner, fidèle à la formule publiée
pour classer.

Descente, dans chacun des quinze arbres : partir de la racine ; tant que le meilleur
des deux enfants fait STRICTEMENT mieux que le nœud courant, y descendre ; sinon
s'arrêter. Une feuille est un arrêt naturel. Un nœud interne peut donc répondre :
c'est le cas où la forme emprunte des traits à plusieurs exemples connus sans
ressembler parfaitement à aucun. L'arbre dont la réponse a le meilleur score donne la
prédiction.

Deux références sont classées avec les mêmes arbres : le plus proche voisin sur les
750 feuilles, et le meilleur des 1485 nœuds. Elles disent si la descente généralise et
si elle se trompe de branche.

La méthode n'a aucun paramètre libre : l'évaluation directe sur le test est légitime.

Usage : python3 src/classify.py
"""

import csv
import json
import statistics
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone

import config
import grasp


CHEMIN_PREDICTIONS = config.DOSSIER_RESULTATS / "test_predictions.json"
CHEMIN_MATRICE = config.DOSSIER_RESULTATS / "matrice_confusion.csv"

# Scores publiés par l'article (Tableau 3) : précision, rappel, F1 par type.
ARTICLE_PAR_TYPE = {
    "r_lieu>origine": (100, 86, 0.92), "r_social_tie": (83, 100, 0.91),
    "r_holo": (78, 86, 0.82), "r_quantificateur": (82, 80, 0.81),
    "r_processus_agent": (71, 93, 0.81), "r_depict": (88, 73, 0.80),
    "r_objet>matiere": (78, 83, 0.80), "r_processus>instr-1": (77, 80, 0.78),
    "r_lieu": (84, 70, 0.76), "r_topic": (68, 86, 0.76),
    "r_processus_patient": (74, 76, 0.75), "r_product_of": (76, 73, 0.74),
    "r_has_causatif": (76, 63, 0.69), "r_own-1": (65, 63, 0.64),
    "r_has_property-1": (71, 50, 0.59),
}
ARTICLE_F1 = 0.772

# F1 de la méthode à seuil précédente (fusion « les deux » à 0,50, classification
# exhaustive), relevés sur le même test avant son remplacement.
ANCIEN_F1 = 0.597
ANCIEN_PAR_TYPE = {
    "r_depict": 0.66, "r_has_causatif": 0.53, "r_has_property-1": 0.76,
    "r_holo": 0.35, "r_lieu": 0.67, "r_lieu>origine": 0.72, "r_objet>matiere": 0.68,
    "r_own-1": 0.54, "r_processus>instr-1": 0.61, "r_processus_agent": 0.50,
    "r_processus_patient": 0.69, "r_product_of": 0.48, "r_quantificateur": 0.57,
    "r_social_tie": 0.79, "r_topic": 0.41,
}

# Tranches de poids des nœuds d'arrêt, bornes incluses.
TRANCHES_POIDS = ((1, 1), (2, 2), (3, 5), (6, 10), (11, 25), (26, 50))

# En deçà de cette profondeur moyenne d'arrêt, un arbre est jugé court-circuité à la
# racine : ses descentes s'arrêtent presque toutes au premier pas.
PROFONDEUR_COURTE = 1.5

# Tolérance sur l'égalité de deux scores, pour ne pas compter un arrondi flottant comme
# une erreur de branche.
EPSILON = 1e-12


# ---------------------------------------------------------------------------
# Score et descente
# ---------------------------------------------------------------------------

def score_noeud(signature_a, signature_b, noeud):
    """Formule 3 : moyenne des deux similarités, côté par côté. Retourne un flottant."""
    return 0.5 * (grasp.similarite_cote(signature_a, noeud, "L")
                  + grasp.similarite_cote(signature_b, noeud, "R"))


def etape(noeud, score):
    """Trace d'un niveau de la descente. Retourne un dict."""
    return {"id": noeud["id"], "profondeur": noeud["profondeur"],
            "poids": noeud["poids"], "score": score, "enfants": []}


def descendre(signature_a, signature_b, noeuds, racine):
    """Descend un arbre tant qu'un enfant fait strictement mieux. Retourne un dict.

    À égalité entre les deux enfants, le premier — le plus ancien dans le corpus — est
    retenu. Chaque score calculé compte pour un calcul."""
    courant = noeuds[racine]
    score = score_noeud(signature_a, signature_b, courant)
    calculs, chemin = 1, []
    while True:
        niveau = etape(courant, score)
        chemin.append(niveau)
        if grasp.est_feuille(courant):
            break
        meilleur, meilleur_score = None, -1.0
        for enfant in courant["enfants"]:
            score_enfant = score_noeud(signature_a, signature_b, noeuds[enfant])
            calculs += 1
            niveau["enfants"].append({"id": enfant, "score": score_enfant})
            if score_enfant > meilleur_score:
                meilleur, meilleur_score = noeuds[enfant], score_enfant
        if meilleur_score <= score:
            break
        courant, score = meilleur, meilleur_score
    return {"rt": courant["rt"], "arret": courant["id"], "score": score,
            "chemin": chemin, "calculs": calculs}


def classer_par_descente(signature_a, signature_b, noeuds, racines):
    """Descend les quinze arbres et garde la meilleure réponse. Retourne un dict.

    Ex aequo entre arbres départagés par l'identifiant du nœud d'arrêt."""
    reponses = [descendre(signature_a, signature_b, noeuds, racines[rt])
                for rt in sorted(racines)]
    reponses.sort(key=lambda r: (-r["score"], r["arret"]))
    return {"gagnante": reponses[0], "reponses": reponses,
            "calculs": sum(r["calculs"] for r in reponses)}


def classer_exhaustif(signature_a, signature_b, candidats):
    """Score chaque candidat, garde le meilleur. Retourne (id, score, id -> score).

    Ex aequo départagés par le plus petit identifiant."""
    scores = {}
    meilleur, meilleur_score = None, -1.0
    for noeud in candidats:
        score = score_noeud(signature_a, signature_b, noeud)
        scores[noeud["id"]] = score
        if score > meilleur_score:
            meilleur, meilleur_score = noeud["id"], score
    return meilleur, meilleur_score, scores


# ---------------------------------------------------------------------------
# Structure des arbres
# ---------------------------------------------------------------------------

def parents_des_noeuds(noeuds):
    """Le parent de chaque nœud, None pour une racine. Retourne id -> id."""
    parents = {identifiant: None for identifiant in noeuds}
    for noeud in noeuds.values():
        for enfant in noeud["enfants"] or []:
            parents[enfant] = noeud["id"]
    return parents


def ancetres(identifiant, parents):
    """Le nœud et tous ses ancêtres jusqu'à la racine. Retourne une liste."""
    lignee = []
    while identifiant is not None:
        lignee.append(identifiant)
        identifiant = parents[identifiant]
    return lignee


def tailles_des_types(noeuds):
    """Nombre de feuilles de chaque type. Retourne relation -> entier."""
    tailles = defaultdict(int)
    for noeud in noeuds.values():
        if grasp.est_feuille(noeud):
            tailles[noeud["rt"]] += 1
    return dict(tailles)


def ids_par_type(noeuds):
    """Identifiants des nœuds de chaque arbre, croissants. Retourne relation -> liste."""
    par_type = defaultdict(list)
    for identifiant in sorted(noeuds):
        par_type[noeuds[identifiant]["rt"]].append(identifiant)
    return par_type


# ---------------------------------------------------------------------------
# Classification des trois méthodes
# ---------------------------------------------------------------------------

def signatures_de_ligne(ligne, signatures):
    """Signatures de A et de B d'une ligne de test. Retourne un couple d'ensembles."""
    return grasp.cotes_de_ligne(ligne, signatures)


def resume_noeud(noeud):
    """Ce qu'une prédiction retient du nœud qui l'a faite. Retourne un dict."""
    return {"id": noeud["id"], "rt": noeud["rt"], "poids": noeud["poids"],
            "profondeur": noeud["profondeur"], "hauteur": noeud["hauteur"],
            "feuille": grasp.est_feuille(noeud), "syntagmes": noeud["syntagmes"]}


def prediction_descente(ligne, resultat, noeuds):
    """Met en forme le résultat d'une descente pour une ligne. Retourne un dict."""
    gagnante = resultat["gagnante"]
    return {
        "syntagme": ligne["syntagme"], "A": ligne["A"], "B": ligne["B"],
        "attendu": ligne["rt"], "predit": gagnante["rt"], "score": gagnante["score"],
        "correct": gagnante["rt"] == ligne["rt"],
        "noeud_arret": resume_noeud(noeuds[gagnante["arret"]]),
        "chemin": gagnante["chemin"],
        "reponses": [{"rt": r["rt"], "id": r["arret"], "score": r["score"],
                      "profondeur": noeuds[r["arret"]]["profondeur"],
                      "poids": noeuds[r["arret"]]["poids"],
                      "feuille": grasp.est_feuille(noeuds[r["arret"]])}
                     for r in resultat["reponses"]],
        "calculs": resultat["calculs"],
    }


def prediction_exhaustive(ligne, identifiant, score, noeuds, calculs):
    """Met en forme le résultat d'une référence exhaustive. Retourne un dict."""
    noeud = noeuds[identifiant]
    return {"syntagme": ligne["syntagme"], "attendu": ligne["rt"],
            "predit": noeud["rt"], "score": score, "correct": noeud["rt"] == ligne["rt"],
            "noeud_arret": resume_noeud(noeud), "calculs": calculs}


def lancer_descente(lignes, signatures, noeuds, racines):
    """Classe le test par descente. Retourne (prédictions, durée)."""
    debut = time.perf_counter()
    predictions = []
    for ligne in lignes:
        signature_a, signature_b = signatures_de_ligne(ligne, signatures)
        resultat = classer_par_descente(signature_a, signature_b, noeuds, racines)
        predictions.append(prediction_descente(ligne, resultat, noeuds))
    return predictions, time.perf_counter() - debut


def lancer_exhaustif(lignes, signatures, noeuds, candidats):
    """Classe le test contre une liste de candidats. Retourne (prédictions, durée, scores)."""
    debut = time.perf_counter()
    predictions, tous_scores = [], []
    for ligne in lignes:
        signature_a, signature_b = signatures_de_ligne(ligne, signatures)
        identifiant, score, scores = classer_exhaustif(signature_a, signature_b,
                                                       candidats)
        predictions.append(prediction_exhaustive(ligne, identifiant, score, noeuds,
                                                 len(candidats)))
        tous_scores.append(scores)
    return predictions, time.perf_counter() - debut, tous_scores


# ---------------------------------------------------------------------------
# Évaluation
# ---------------------------------------------------------------------------

def comptes_par_type(predictions):
    """Vrais positifs, prédits et attendus par type. Retourne type -> dict."""
    comptes = defaultdict(lambda: {"vp": 0, "predits": 0, "attendus": 0})
    for prediction in predictions:
        comptes[prediction["attendu"]]["attendus"] += 1
        comptes[prediction["predit"]]["predits"] += 1
        if prediction["correct"]:
            comptes[prediction["attendu"]]["vp"] += 1
    return comptes


def precision_rappel_f1(vp, predits, attendus):
    """Les trois mesures d'un type. Retourne un triplet de flottants."""
    precision = vp / predits if predits else 0.0
    rappel = vp / attendus if attendus else 0.0
    f1 = 2 * precision * rappel / (precision + rappel) if precision + rappel else 0.0
    return precision, rappel, f1


def evaluer(predictions, types):
    """Précision, rappel et F1 par type puis en macro. Retourne un dict.

    Macro : moyenne non pondérée sur les types, chacun comptant pour un."""
    comptes = comptes_par_type(predictions)
    par_type = {}
    for type_relation in types:
        compte = comptes[type_relation]
        precision, rappel, f1 = precision_rappel_f1(compte["vp"], compte["predits"],
                                                    compte["attendus"])
        par_type[type_relation] = {"precision": precision, "rappel": rappel, "f1": f1,
                                   "vp": compte["vp"], "predits": compte["predits"],
                                   "attendus": compte["attendus"]}
    corrects = sum(1 for p in predictions if p["correct"])
    return {
        "par_type": par_type,
        "precision": statistics.fmean([v["precision"] for v in par_type.values()]),
        "rappel": statistics.fmean([v["rappel"] for v in par_type.values()]),
        "f1": statistics.fmean([v["f1"] for v in par_type.values()]),
        "exactitude": corrects / len(predictions) if predictions else 0.0,
        "corrects": corrects, "total": len(predictions),
    }


def evaluer_sous_ensemble(predictions):
    """F1 macro et exactitude d'une partie des prédictions. Retourne un dict ou None.

    La macro porte sur les types présents dans la partie, attendus ou prédits : un type
    absent n'a ni précision ni rappel à y mesurer."""
    if not predictions:
        return None
    types = sorted({p["attendu"] for p in predictions} | {p["predit"] for p in predictions})
    return evaluer(predictions, types)


def matrice_confusion(predictions, types):
    """Compte les prédictions pour chaque couple (attendu, prédit). Retourne un dict de dicts."""
    matrice = {attendu: {predit: 0 for predit in types} for attendu in types}
    for prediction in predictions:
        matrice[prediction["attendu"]][prediction["predit"]] += 1
    return matrice


def part_interne(predictions):
    """Part des prédictions faites par un nœud interne. Retourne un flottant."""
    if not predictions:
        return 0.0
    return sum(1 for p in predictions if not p["noeud_arret"]["feuille"]) / len(predictions)


# ---------------------------------------------------------------------------
# Mesures de généralisation
# ---------------------------------------------------------------------------

def tranche_de_poids(poids):
    """Libellé de la tranche d'un poids. Retourne une chaîne."""
    for bas, haut in TRANCHES_POIDS:
        if bas <= poids <= haut:
            return str(bas) if bas == haut else f"{bas}–{haut}"
    return f"> {TRANCHES_POIDS[-1][1]}"


def stats_generalisation(predictions):
    """Arrêts internes, poids et profondeurs des nœuds d'arrêt. Retourne un dict."""
    gagnants = [p["noeud_arret"] for p in predictions]
    toutes = [r for p in predictions for r in p["reponses"]]
    feuilles = [p for p in predictions if p["noeud_arret"]["feuille"]]
    internes = [p for p in predictions if not p["noeud_arret"]["feuille"]]
    par_arbre = defaultdict(list)
    for reponse in toutes:
        par_arbre[reponse["rt"]].append(reponse)
    return {
        "part_interne_gagnantes": part_interne(predictions),
        "part_interne_toutes": sum(1 for r in toutes if not r["feuille"]) / len(toutes),
        "n_descentes": len(toutes),
        "par_arbre": {rt: {"part_interne": sum(1 for r in lot if not r["feuille"])
                                           / len(lot),
                           "profondeur_moyenne": statistics.fmean(
                               r["profondeur"] for r in lot)}
                      for rt, lot in par_arbre.items()},
        "feuilles": evaluer_sous_ensemble(feuilles), "n_feuilles": len(feuilles),
        "internes": evaluer_sous_ensemble(internes), "n_internes": len(internes),
        "poids_gagnants": Counter(tranche_de_poids(n["poids"]) for n in gagnants),
        "poids_toutes": Counter(tranche_de_poids(r["poids"]) for r in toutes),
        "profondeurs_gagnantes": Counter(n["profondeur"] for n in gagnants),
        "profondeurs_toutes": Counter(r["profondeur"] for r in toutes),
        "calculs_moyens": statistics.fmean(p["calculs"] for p in predictions),
        "calculs_max": max(p["calculs"] for p in predictions),
    }


def interne_par_type_predit(predictions):
    """Part des prédictions de chaque type faites par un nœud interne.
    Retourne type -> (part, nombre)."""
    par_type = defaultdict(list)
    for prediction in predictions:
        par_type[prediction["predit"]].append(prediction)
    return {rt: (part_interne(lot), len(lot)) for rt, lot in par_type.items()}


# ---------------------------------------------------------------------------
# Diagnostic des erreurs de branche
# ---------------------------------------------------------------------------

def meilleur_du_type(scores, identifiants):
    """Le nœud de meilleur score parmi ceux d'un arbre. Retourne (id, score)."""
    meilleur = max(identifiants, key=lambda i: (scores[i], -i))
    return meilleur, scores[meilleur]


def diagnostiquer(reponse, scores, identifiants, parents, noeuds):
    """Compare l'arrêt d'une descente au meilleur nœud de son arbre. Retourne un dict.

    « optimale » : la descente trouve le maximum de l'arbre. « arrêt prématuré » : le
    maximum est sous le nœud d'arrêt, la descente s'est arrêtée trop tôt. « mauvaise
    branche » : le maximum est ailleurs ; le niveau est la profondeur du dernier
    ancêtre commun, là où la descente a pris le mauvais enfant."""
    meilleur, meilleur_score = meilleur_du_type(scores, identifiants)
    if reponse["score"] >= meilleur_score - EPSILON:
        return {"nature": "optimale", "niveau": None, "perte": 0.0}
    lignee_meilleur = ancetres(meilleur, parents)
    if reponse["arret"] in lignee_meilleur:
        return {"nature": "arrêt prématuré",
                "niveau": noeuds[reponse["arret"]]["profondeur"],
                "perte": meilleur_score - reponse["score"]}
    lignee_arret = set(ancetres(reponse["arret"], parents))
    commun = next(i for i in lignee_meilleur if i in lignee_arret)
    return {"nature": "mauvaise branche", "niveau": noeuds[commun]["profondeur"],
            "perte": meilleur_score - reponse["score"]}


def diagnostics_de_branche(predictions, tous_scores, noeuds):
    """Diagnostique les 15 descentes de chaque exemple. Retourne un dict.

    Distingue toutes les descentes, et celles de l'arbre du type attendu, qui sont les
    seules à pouvoir coûter un rappel."""
    parents = parents_des_noeuds(noeuds)
    par_type = ids_par_type(noeuds)
    toutes, attendues = [], []
    for prediction, scores in zip(predictions, tous_scores):
        for reponse in prediction["reponses"]:
            reponse_arbre = {"arret": reponse["id"], "score": reponse["score"]}
            diagnostic = diagnostiquer(reponse_arbre, scores, par_type[reponse["rt"]],
                                       parents, noeuds)
            diagnostic["rt"] = reponse["rt"]
            toutes.append(diagnostic)
            if reponse["rt"] == prediction["attendu"]:
                attendues.append(diagnostic)
    return {"toutes": toutes, "attendues": attendues}


def resume_diagnostics(diagnostics):
    """Compte natures et niveaux d'erreur. Retourne un dict."""
    natures = Counter(d["nature"] for d in diagnostics)
    branche = [d for d in diagnostics if d["nature"] == "mauvaise branche"]
    premature = [d for d in diagnostics if d["nature"] == "arrêt prématuré"]
    pertes = [d["perte"] for d in diagnostics if d["nature"] != "optimale"]
    return {"total": len(diagnostics), "natures": natures,
            "niveaux_branche": Counter(d["niveau"] for d in branche),
            "niveaux_premature": Counter(d["niveau"] for d in premature),
            "perte_mediane": statistics.median(pertes) if pertes else 0.0,
            "perte_max": max(pertes) if pertes else 0.0}


def croiser_references(descente, tous_noeuds, diagnostics):
    """Exemples où descente et exhaustif divergent, et pourquoi. Retourne un dict.

    Pour chaque exemple que l'exhaustif réussit et que la descente rate, on regarde la
    descente de l'arbre attendu : si elle est sous-optimale, c'est elle qui a coûté."""
    perdus, gagnes, attendues = [], [], diagnostics["attendues"]
    for rang, (c, b) in enumerate(zip(descente, tous_noeuds)):
        if b["correct"] and not c["correct"]:
            perdus.append((c, attendues[rang]))
        elif c["correct"] and not b["correct"]:
            gagnes.append(c)
    return {"perdus": perdus, "gagnes": gagnes,
            "perdus_par_nature": Counter(d["nature"] for _, d in perdus),
            "divergences": sum(1 for c, b in zip(descente, tous_noeuds)
                               if c["predit"] != b["predit"])}


def choix_de_descente(scores, noeuds, racine):
    """Rejoue une descente sur des scores déjà calculés. Retourne la liste des choix.

    Chaque choix est « léger », « lourd » ou « égal » selon le poids de l'enfant retenu
    face à son frère ; « arrêt » quand aucun enfant ne fait mieux."""
    choix, courant = [], noeuds[racine]
    while not grasp.est_feuille(courant):
        enfants = [noeuds[e] for e in courant["enfants"]]
        meilleur = max(enfants, key=lambda e: (scores[e["id"]], -enfants.index(e)))
        if scores[meilleur["id"]] <= scores[courant["id"]]:
            choix.append("arrêt")
            break
        poids = sorted(e["poids"] for e in enfants)
        if poids[0] == poids[1]:
            choix.append("égal")
        else:
            choix.append("léger" if meilleur["poids"] == poids[0] else "lourd")
        courant = meilleur
    return choix


def choix_aux_embranchements(tous_scores, noeuds, racines):
    """Compte vers quel enfant partent les descentes, à la racine et partout.
    Retourne un dict de compteurs."""
    racine, partout = Counter(), Counter()
    for scores in tous_scores:
        for rt in sorted(racines):
            choix = choix_de_descente(scores, noeuds, racines[rt])
            racine[choix[0]] += 1
            partout.update(choix)
    return {"racine": racine, "partout": partout}


# ---------------------------------------------------------------------------
# Écriture des sorties de données
# ---------------------------------------------------------------------------

def ecrire_predictions(predictions, evaluation, references):
    """Écrit data/resultats/test_predictions.json. Retourne le chemin.

    Pour chaque exemple : le chemin complet de la descente dans l'arbre gagnant, la
    réponse de chacun des quinze arbres, et ce que prédisent les deux références."""
    feuilles, tous = references
    lignes = []
    for prediction, a, b in zip(predictions, feuilles, tous):
        ligne = dict(prediction)
        ligne["exhaustif_feuilles"] = {"predit": a["predit"], "id": a["noeud_arret"]["id"],
                                       "score": a["score"]}
        ligne["exhaustif_noeuds"] = {"predit": b["predit"], "id": b["noeud_arret"]["id"],
                                     "score": b["score"]}
        lignes.append(ligne)
    charge = {
        "split": "test (450 exemples, 30 par type)",
        "methode": "descente dans 15 arbres de clustering hiérarchique, formule 3",
        "modele": config.FICHIER_ARBRES.name,
        "genere_le": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "macro_stricte": {k: evaluation[k] for k in
                          ("precision", "rappel", "f1", "exactitude")},
        "predictions": lignes,
    }
    CHEMIN_PREDICTIONS.parent.mkdir(parents=True, exist_ok=True)
    with open(CHEMIN_PREDICTIONS, "w", encoding="utf-8", newline="") as f:
        json.dump(charge, f, ensure_ascii=False, indent=1)
        f.write("\n")
    return CHEMIN_PREDICTIONS


def ecrire_matrice(matrice, types):
    """Écrit data/resultats/matrice_confusion.csv. Retourne le chemin."""
    CHEMIN_MATRICE.parent.mkdir(parents=True, exist_ok=True)
    with open(CHEMIN_MATRICE, "w", encoding="utf-8", newline="") as f:
        redacteur = csv.writer(f, lineterminator="\n")
        redacteur.writerow(["attendu \\ prédit"] + list(types))
        for attendu in types:
            redacteur.writerow([attendu] + [matrice[attendu][p] for p in types])
    return CHEMIN_MATRICE


# ---------------------------------------------------------------------------
# Mise en forme
# ---------------------------------------------------------------------------

fr, pct, tableau = grasp.fr, grasp.pct, grasp.tableau


def ecart_signe(valeur, decimales=3):
    """Formate un écart avec son signe, en typographie française. Retourne une chaîne."""
    if valeur > 0:
        return "+" + fr(valeur, decimales)
    if valeur < 0:
        return "−" + fr(-valeur, decimales)
    return "="


def libelle_niveaux(compte):
    """Résume un compte par niveau, du plus haut au plus profond. Retourne une chaîne."""
    if not compte:
        return "—"
    return ", ".join(f"{niveau} : {compte[niveau]}" for niveau in sorted(compte))


# ---------------------------------------------------------------------------
# Rapport de phase B : une fonction par section
# ---------------------------------------------------------------------------

def section_dispositif(lignes_test, noeuds, racines):
    """B.1 : ce qui est classé et comment. Retourne des lignes."""
    feuilles = sum(1 for n in noeuds.values() if grasp.est_feuille(n))
    return ["## B. Classification par descente", "",
            "### B.1 Dispositif", "",
            f"- **Jeu évalué** : les {len(lignes_test)} exemples de test, "
            f"{len(lignes_test) // len(racines)} par type. La méthode n'a **aucun "
            "paramètre libre** — ni seuil de fusion, ni seuil d'arrêt, ni mesure à "
            "choisir — donc rien n'a pu être réglé sur ce jeu.",
            "- **Score** : `½ [ sim(s(A), sL) + sim(s(B), sR) ]`, formule 3 de l'article, "
            "cosinus sur ensembles.",
            "- **Asymétrie voulue** : la construction fusionne sur le **minimum** des "
            "deux côtés, la classification score sur la **moyenne**. Exigeant pour "
            "fusionner, fidèle à la formule publiée pour classer. Conséquence à garder "
            "en tête : un côté parfait peut porter un côté nul à la classification, ce "
            "qu'il ne pouvait pas faire à la construction.",
            f"- **Descente** : dans chacun des {len(racines)} arbres, de la racine vers le "
            "meilleur enfant tant qu'il fait **strictement** mieux que le nœud courant. "
            "L'arbre dont la réponse a le meilleur score donne la prédiction.",
            f"- **Références**, avec les mêmes arbres : (a) plus proche voisin sur les "
            f"{feuilles} feuilles ; (b) meilleur des {len(noeuds)} nœuds ; (c) la "
            "descente.", ""]


def section_references(resultats):
    """B.2 : les trois méthodes côte à côte. Retourne des lignes."""
    corps = []
    for nom, cle in (("(a) feuilles, exhaustif", "a"), ("(b) tous les nœuds, exhaustif", "b"),
                     ("(c) descente", "c")):
        r = resultats[cle]
        corps.append([f"**{nom}**", fr(r["evaluation"]["precision"]),
                      fr(r["evaluation"]["rappel"]), f"**{fr(r['evaluation']['f1'])}**",
                      pct(r["evaluation"]["exactitude"]),
                      pct(part_interne(r["predictions"])),
                      fr(r["calculs"], 1), fr(r["duree"], 2)])
    a, b, c = (resultats[k]["evaluation"]["f1"] for k in "abc")
    lignes = ["### B.2 Les trois méthodes", ""]
    lignes += tableau(["méthode", "P macro", "R macro", "F1 macro", "exactitude",
                       "prédictions par un nœud interne", "calculs / exemple",
                       "temps total (s)"], corps)
    lignes += ["",
               f"Pour situer : article {fr(ARTICLE_F1)}, méthode à seuil précédente "
               f"{fr(ANCIEN_F1)}. La descente fait {ecart_signe(c - ANCIEN_F1)} par "
               f"rapport à la méthode à seuil et {ecart_signe(c - ARTICLE_F1)} par "
               "rapport à l'article.", "",
               "**Lecture.**", "",
               f"- (c) contre (a) : {ecart_signe(c - a)}. "
               + ("La descente fait **mieux que le plus proche voisin** : les nœuds "
                  "internes qui répondent apportent quelque chose, l'arbre généralise."
                  if c > a + EPSILON else
                  "La descente ne fait pas mieux que le plus proche voisin : l'arbre ne "
                  "généralise pas, ou sa généralisation ne sert pas."),
               f"- (c) contre (b) : {ecart_signe(c - b)}, pour "
               f"{fr(resultats['c']['calculs'], 1)} calculs par exemple au lieu de "
               f"{fr(resultats['b']['calculs'], 0)} "
               f"({fr(resultats['b']['calculs'] / resultats['c']['calculs'], 1)} fois "
               "moins). "
               + ("La descente est **au niveau** de l'exhaustif."
                  if abs(c - b) < 0.005 else
                  "La descente fait **mieux** que l'exhaustif : le meilleur nœud absolu "
                  "n'est pas toujours le bon, et la descente l'évite parfois (§ B.6)."
                  if c > b else
                  "La descente est **en dessous** de l'exhaustif : elle se trompe de "
                  "branche, § B.6 dit à quel niveau."),
               f"- (b) contre (a) : {ecart_signe(b - a)}. C'est ce que vaudrait la "
               "généralisation si on savait toujours trouver le meilleur nœud.", ""]
    return lignes


def section_par_type(evaluation, generalisation, internes_par_type):
    """B.3 : précision, rappel, F1 par type, et arrêts internes. Retourne des lignes."""
    corps = []
    for rt in sorted(evaluation["par_type"], key=lambda t: -evaluation["par_type"][t]["f1"]):
        d = evaluation["par_type"][rt]
        part, nombre = internes_par_type.get(rt, (0.0, 0))
        arbre = generalisation["par_arbre"][rt]
        corps.append([f"`{rt}`", d["predits"], fr(100 * d["precision"], 1),
                      fr(100 * d["rappel"], 1), f"**{fr(d['f1'], 2)}**",
                      fr(ANCIEN_PAR_TYPE[rt], 2), fr(ARTICLE_PAR_TYPE[rt][2], 2),
                      pct(arbre["part_interne"], 0), fr(arbre["profondeur_moyenne"], 1),
                      f"{pct(part, 0)} ({nombre})"])
    return (["### B.3 Détail par type", "",
             "- **prédits** : nombre de fois où le type est proposé, pour 30 attendus.",
             "- **arrêts internes (arbre)** : sur les 450 descentes de cet arbre, part "
             "qui s'arrêtent sur un nœud interne ; **profondeur moy.** : profondeur "
             "moyenne d'arrêt dans cet arbre.",
             "- **prédictions internes** : parmi les prédictions de ce type, part faite "
             "par un nœud interne.", ""]
            + tableau(["type", "prédits", "P (%)", "R (%)", "F1", "F1 seuil",
                       "F1 article", "arrêts internes (arbre)", "profondeur moy.",
                       "prédictions internes"], corps) + [""])


def section_confusion(matrice, types):
    """B.4 : la matrice de confusion, types numérotés. Retourne des lignes."""
    entete = ["attendu \\ prédit"] + [str(i + 1) for i in range(len(types))]
    corps = []
    for i, attendu in enumerate(types):
        cellules = []
        for predit in types:
            valeur = matrice[attendu][predit]
            if attendu == predit:
                cellules.append(f"**{valeur}**")
            else:
                cellules.append(str(valeur) if valeur else "·")
        corps.append([f"{i + 1}. `{attendu}`"] + cellules)
    couples = sorted(((a, p, matrice[a][p]) for a in types for p in types
                      if a != p and matrice[a][p]), key=lambda c: (-c[2], c[0], c[1]))
    return (["### B.4 Matrice de confusion", "",
             "Lignes : type attendu. Colonnes : type prédit, numérotés comme les lignes. "
             "Aussi écrite dans `data/resultats/matrice_confusion.csv`.", ""]
            + tableau(entete, corps)
            + ["", "Confusions les plus fréquentes : "
               + ", ".join(f"`{a}` → `{p}` ({n})" for a, p, n in couples[:6]) + ".", ""])


def section_generalisation(generalisation):
    """B.5 : où la descente s'arrête, et si la généralisation est juste. Retourne des lignes."""
    g = generalisation
    feuilles, internes = g["feuilles"], g["internes"]
    lignes = ["### B.5 Généralisation", "",
              f"- **Arrêts internes** : {pct(g['part_interne_gagnantes'])} des "
              f"prédictions ({g['n_internes']} sur {g['n_internes'] + g['n_feuilles']}) "
              f"sont faites par un nœud interne ; sur l'ensemble des {g['n_descentes']} "
              f"descentes, tous arbres confondus, {pct(g['part_interne_toutes'])} "
              "s'arrêtent sur un nœud interne.",
              f"- **Calculs** : {fr(g['calculs_moyens'], 1)} scores par exemple en "
              f"moyenne, {g['calculs_max']} au plus.", "",
              "**La généralisation est-elle juste quand elle se produit ?**", ""]
    corps = []
    for nom, lot, n in (("feuille", feuilles, g["n_feuilles"]),
                        ("nœud interne", internes, g["n_internes"])):
        if lot is None:
            corps.append([nom, 0, "—", "—"])
            continue
        corps.append([nom, n, f"{lot['corrects']} ({pct(lot['exactitude'])})",
                      fr(lot["f1"])])
    lignes += tableau(["prédiction faite par", "exemples", "justes (exactitude)",
                       "F1 macro"], corps)
    lignes += ["",
               "Le F1 macro d'une partie est calculé sur les types qu'elle contient ; "
               "l'exactitude, qui ne dépend pas de cette convention, est le chiffre à "
               "comparer.", "",
               "**Poids du nœud d'arrêt**", ""]
    tranches = [tranche_de_poids(bas) for bas, _ in TRANCHES_POIDS]
    lignes += tableau(["poids"] + tranches,
                      [["prédictions"] + [g["poids_gagnants"].get(t, 0) for t in tranches],
                       ["toutes les descentes"] + [g["poids_toutes"].get(t, 0)
                                                   for t in tranches]])
    profondeurs = sorted(set(g["profondeurs_toutes"]) | set(g["profondeurs_gagnantes"]))
    lignes += ["", "**Profondeur d'arrêt** (racine = 0)", ""]
    lignes += tableau(["profondeur"] + [str(p) for p in profondeurs],
                      [["prédictions"] + [g["profondeurs_gagnantes"].get(p, 0)
                                          for p in profondeurs],
                       ["toutes les descentes"] + [g["profondeurs_toutes"].get(p, 0)
                                                   for p in profondeurs]])
    return lignes + [""]


def section_branches(diagnostics, croisement):
    """B.6 : où la descente se trompe de branche. Retourne des lignes."""
    toutes = resume_diagnostics(diagnostics["toutes"])
    attendues = resume_diagnostics(diagnostics["attendues"])
    corps = []
    for nom, r in (("toutes les descentes", toutes), ("arbre du type attendu", attendues)):
        corps.append([nom, r["total"],
                      pct(r["natures"].get("optimale", 0) / r["total"]),
                      r["natures"].get("arrêt prématuré", 0),
                      r["natures"].get("mauvaise branche", 0),
                      fr(r["perte_mediane"]), fr(r["perte_max"])])
    lignes = ["### B.6 Erreurs de branche : la descente contre l'exhaustif", "",
              "Pour chaque descente, on compare le nœud d'arrêt au meilleur nœud du même "
              "arbre, trouvé par l'exhaustif.", "",
              "- **optimale** : la descente trouve le maximum de l'arbre ;",
              "- **arrêt prématuré** : le maximum est sous le nœud d'arrêt — aucun des "
              "deux enfants ne faisait mieux, mais un descendant plus profond, si ;",
              "- **mauvaise branche** : le maximum est dans l'autre sous-arbre ; le "
              "niveau est la profondeur du dernier ancêtre commun, là où la descente a "
              "choisi le mauvais enfant.", ""]
    lignes += tableau(["descentes", "nombre", "optimales", "arrêts prématurés",
                       "mauvaises branches", "perte de score méd.", "perte max"], corps)
    lignes += ["", "**Niveau des erreurs**, dans l'arbre du type attendu :", "",
               f"- mauvaise branche, profondeur de l'embranchement → "
               f"{libelle_niveaux(attendues['niveaux_branche'])}",
               f"- arrêt prématuré, profondeur de l'arrêt → "
               f"{libelle_niveaux(attendues['niveaux_premature'])}", "",
               "Et sur toutes les descentes :", "",
               f"- mauvaise branche → {libelle_niveaux(toutes['niveaux_branche'])}",
               f"- arrêt prématuré → {libelle_niveaux(toutes['niveaux_premature'])}", ""]
    perdus = croisement["perdus_par_nature"]
    lignes += ["**Ce que cela coûte en prédictions.** "
               f"(b) et (c) prédisent un type différent pour {croisement['divergences']} "
               f"exemples. L'exhaustif réussit et la descente échoue sur "
               f"{len(croisement['perdus'])} exemples ; l'inverse arrive sur "
               f"{len(croisement['gagnes'])}. Parmi les exemples perdus, la descente de "
               f"l'arbre attendu était : optimale {perdus.get('optimale', 0)}, arrêtée "
               f"trop tôt {perdus.get('arrêt prématuré', 0)}, dans la mauvaise branche "
               f"{perdus.get('mauvaise branche', 0)}. Par construction, un exemple que "
               "l'exhaustif réussit a son meilleur nœud absolu dans l'arbre attendu : si "
               "la descente de cet arbre le trouvait, elle gagnerait aussi. Toute perte "
               "est donc une descente sous-optimale dans l'arbre attendu, sauf égalité "
               "exacte de scores.", ""]
    return lignes


def section_mecanisme(choix, mesures_arbres, generalisation):
    """B.7 : pourquoi la descente part dans la mauvaise branche. Retourne des lignes."""
    courts = [m for m in mesures_arbres
              if generalisation["par_arbre"][m["rt"]]["profondeur_moyenne"]
              < PROFONDEUR_COURTE]
    racine, partout = choix["racine"], choix["partout"]
    n_racine = sum(racine.values())
    decisions = sum(v for k, v in partout.items() if k != "arrêt")
    tailles = [(m["racine_sL"] + m["racine_sR"]) / 2 for m in mesures_arbres]
    avec_isolat = sum(1 for m in mesures_arbres if m["isolats"])
    return (["### B.7 Le mécanisme : le cosinus tire la descente vers l'enfant léger", "",
            "Le cosinus divise par la racine de la taille de la signature du nœud. "
            "Plus un nœud couvre d'exemples, plus sa signature est grande et plus son "
            "score baisse, **quel que soit son contenu**. À chaque embranchement, "
            "l'enfant le plus léger part donc avantagé.", ""]
            + tableau(["embranchement", "vers l'enfant léger", "vers l'enfant lourd",
                       "enfants de même poids", "arrêt"],
                      [["racine", f"**{racine.get('léger', 0)}** "
                                  f"({pct(racine.get('léger', 0) / n_racine, 0)})",
                        racine.get("lourd", 0), racine.get("égal", 0),
                        racine.get("arrêt", 0)],
                       ["tous niveaux", f"{partout.get('léger', 0)} "
                                        f"({pct(partout.get('léger', 0) / decisions, 0)} "
                                        "des descentes effectives)",
                        partout.get("lourd", 0), partout.get("égal", 0),
                        partout.get("arrêt", 0)]])
            + ["",
               f"Les signatures des racines comptent en moyenne "
               f"{fr(statistics.fmean(tailles), 0)} symboles par côté, contre une "
               "cinquantaine pour un exemple. Or dans "
               f"{avec_isolat} arbres sur {len(mesures_arbres)}, l'enfant léger de la "
               "racine est un **isolat** (partie A.4) : un à trois exemples que le "
               "type n'a rapprochés de personne. La descente y entre dès le premier pas "
               "et s'y arrête, sur l'exemple le **moins** représentatif du type.", "",
               f"Les arbres où la descente s'arrête en moyenne avant la profondeur "
               f"{fr(PROFONDEUR_COURTE, 1)} sont "
               + ", ".join(f"`{m['rt']}`" + (" (isolat)" if m["isolats"] else "")
                           for m in courts)
               + f" : {sum(1 for m in courts if m['isolats'])} sur {len(courts)} ont un "
               "isolat à la racine. Leurs F1 en B.3 sont parmi les plus bas.", "",
               "L'exhaustif ne souffre pas de ce biais de la même façon : il compare "
               "tous les nœuds entre eux et trouve la feuille qui colle, là où la "
               "descente ne compare que deux frères de tailles très différentes. C'est "
               "aussi pourquoi (b) ne fait pas mieux que (a) : les nœuds internes, plus "
               "gros, ne battent presque jamais la meilleure feuille.", ""])


def section_sorties():
    """B.8 : les fichiers écrits. Retourne des lignes."""
    return ["### B.8 Sorties écrites", "",
            f"- `{CHEMIN_PREDICTIONS.relative_to(config.RACINE).as_posix()}` : pour "
            "chaque exemple, le chemin complet de la descente dans l'arbre gagnant (score "
            "de chaque nœud visité et de ses deux enfants), le nœud d'arrêt, la réponse "
            "des quinze arbres, et les prédictions des deux références.",
            f"- `{CHEMIN_MATRICE.relative_to(config.RACINE).as_posix()}` : la matrice de "
            "confusion de la descente.", ""]


def construire_rapport(contexte):
    """Écrit la partie B du rapport commun. Ne retourne rien."""
    lignes = section_dispositif(contexte["lignes"], contexte["noeuds"], contexte["racines"])
    lignes += section_references(contexte["resultats"])
    lignes += section_par_type(contexte["evaluation"], contexte["generalisation"],
                               contexte["internes_par_type"])
    lignes += section_confusion(contexte["matrice"], contexte["types"])
    lignes += section_generalisation(contexte["generalisation"])
    lignes += section_branches(contexte["diagnostics"], contexte["croisement"])
    lignes += section_mecanisme(contexte["choix"], contexte["mesures_arbres"],
                                contexte["generalisation"])
    lignes += section_sorties()
    grasp.ecrire_partie_rapport("B", lignes)


# ---------------------------------------------------------------------------
# Enchaînement
# ---------------------------------------------------------------------------

def mesures_des_arbres(noeuds, racines):
    """Les mesures de phase A, recalculées sur les arbres lus. Retourne une liste."""
    return [grasp.mesurer_arbre(noeuds, rt, racines[rt], {"liens_calcules": 0})
            for rt in sorted(racines)]


def resultat_methode(predictions, duree, types):
    """Évalue une méthode et note son coût. Retourne un dict."""
    return {"predictions": predictions, "duree": duree,
            "evaluation": evaluer(predictions, types),
            "calculs": statistics.fmean(p["calculs"] for p in predictions)}


def main():
    signatures = grasp.charger_signatures()
    noeuds, racines = grasp.charger_arbres()
    lignes_par_type = grasp.charger_lignes("test")
    lignes = [l for rt in sorted(lignes_par_type) for l in lignes_par_type[rt]]
    types = sorted(lignes_par_type)
    print(f"Arbres : {len(noeuds)} nœuds, {len(racines)} racines. Test : {len(lignes)} "
          "exemples.", flush=True)

    feuilles = [noeuds[i] for i in sorted(noeuds) if grasp.est_feuille(noeuds[i])]
    tous = [noeuds[i] for i in sorted(noeuds)]
    pred_a, duree_a, _ = lancer_exhaustif(lignes, signatures, noeuds, feuilles)
    pred_b, duree_b, scores_b = lancer_exhaustif(lignes, signatures, noeuds, tous)
    pred_c, duree_c = lancer_descente(lignes, signatures, noeuds, racines)
    resultats = {"a": resultat_methode(pred_a, duree_a, types),
                 "b": resultat_methode(pred_b, duree_b, types),
                 "c": resultat_methode(pred_c, duree_c, types)}
    for cle, nom in (("a", "feuilles"), ("b", "tous les nœuds"), ("c", "descente")):
        r = resultats[cle]
        print(f"  ({cle}) {nom:15s} F1 macro {fr(r['evaluation']['f1'])}, "
              f"{pct(part_interne(r['predictions']))} internes, "
              f"{fr(r['calculs'], 1)} calculs/exemple, {fr(r['duree'], 2)} s", flush=True)

    evaluation = resultats["c"]["evaluation"]
    matrice = matrice_confusion(pred_c, types)
    diagnostics = diagnostics_de_branche(pred_c, scores_b, noeuds)
    ecrire_matrice(matrice, types)
    ecrire_predictions(pred_c, evaluation, (pred_a, pred_b))
    construire_rapport({
        "lignes": lignes, "noeuds": noeuds, "racines": racines, "types": types,
        "resultats": resultats, "evaluation": evaluation, "matrice": matrice,
        "generalisation": stats_generalisation(pred_c),
        "internes_par_type": interne_par_type_predit(pred_c),
        "diagnostics": diagnostics,
        "croisement": croiser_references(pred_c, pred_b, diagnostics),
        "choix": choix_aux_embranchements(scores_b, noeuds, racines),
        "mesures_arbres": mesures_des_arbres(noeuds, racines),
    })


if __name__ == "__main__":
    main()
