#!/usr/bin/env python3
"""Classification par descente dans les arbres, et métriques d'évaluation.

Score d'une forme « A de B » contre un nœud < sL, sR > (formule 3 de l'article) :

    score = ½ × [ sim(s(A), sL) + sim(s(B), sR) ]

C'est la MOYENNE, alors que la construction des arbres fusionne sur le MINIMUM des deux
côtés. L'asymétrie est voulue : exigeant pour fusionner, fidèle à la formule publiée
pour classer.

Descente, dans chacun des quinze arbres : partir de la racine ; tant que le meilleur
des deux enfants fait STRICTEMENT mieux que le nœud courant, y descendre ; sinon
s'arrêter. Une feuille est un arrêt naturel. L'arbre dont la réponse a le meilleur score
donne la prédiction.

Ce module n'a pas de point d'entrée : il est importé par grille.py,
variantes_signatures.py, evaluation_finale.py, evaluation_signatures.py et predire.py.
Le code de la phase union · arbre · descente (références exhaustives, diagnostics de
branche, rapport) a été retiré ; il reste dans le commit 8bd078a.
"""

import statistics
import time
from collections import defaultdict

import grasp


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

# F1 par type du plus proche voisin sur les feuilles (F1 macro 0,585), mesuré sur le même
# test lors de l'évaluation de la version en union, puis figé ici : le fichier de
# prédictions d'où il vient n'est plus conservé.
VOISIN_PAR_TYPE = {
    "r_depict": 0.7778, "r_has_causatif": 0.5965, "r_has_property-1": 0.6970,
    "r_holo": 0.4528, "r_lieu": 0.7812, "r_lieu>origine": 0.6923,
    "r_objet>matiere": 0.5660, "r_own-1": 0.4516, "r_processus>instr-1": 0.6250,
    "r_processus_agent": 0.4746, "r_processus_patient": 0.5397, "r_product_of": 0.5000,
    "r_quantificateur": 0.4667, "r_social_tie": 0.7500, "r_topic": 0.4000,
}


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


def tailles_des_types(noeuds):
    """Nombre de feuilles de chaque type. Retourne relation -> entier."""
    tailles = defaultdict(int)
    for noeud in noeuds.values():
        if grasp.est_feuille(noeud):
            tailles[noeud["rt"]] += 1
    return dict(tailles)


# ---------------------------------------------------------------------------
# Classification d'un ensemble d'exemples
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


def lancer_descente(lignes, signatures, noeuds, racines):
    """Classe le test par descente. Retourne (prédictions, durée)."""
    debut = time.perf_counter()
    predictions = []
    for ligne in lignes:
        signature_a, signature_b = signatures_de_ligne(ligne, signatures)
        resultat = classer_par_descente(signature_a, signature_b, noeuds, racines)
        predictions.append(prediction_descente(ligne, resultat, noeuds))
    return predictions, time.perf_counter() - debut


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


def matrice_confusion(predictions, types):
    """Compte les prédictions pour chaque couple (attendu, prédit). Retourne un dict de dicts."""
    matrice = {attendu: {predit: 0 for predit in types} for attendu in types}
    for prediction in predictions:
        matrice[prediction["attendu"]][prediction["predit"]] += 1
    return matrice


# ---------------------------------------------------------------------------
# Mise en forme
# ---------------------------------------------------------------------------

def ecart_signe(valeur, decimales=3):
    """Formate un écart avec son signe, en typographie française. Retourne une chaîne."""
    if valeur > 0:
        return "+" + grasp.fr(valeur, decimales)
    if valeur < 0:
        return "−" + grasp.fr(-valeur, decimales)
    return "="
