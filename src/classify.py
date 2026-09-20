#!/usr/bin/env python3
"""Étape 5 : classification d'une forme « A de B » et choix du seuil de fusion.

Formule 3 du papier : pour une forme « A de B » et une règle < sL, sR, rt >,

    score = ½ × [ sim(s(A), sL) + sim(s(B), sR) ]

Le score est calculé contre TOUTES les règles de TOUS les types ; le `rt` de la règle
la mieux classée est la prédiction. Les deux côtés restent séparés : jamais de
concaténation, « vin de France » n'est pas « France de vin ».

Trois mesures de similarité sont comparées. Elles ne diffèrent que par la pénalité
infligée à une règle large, ce qui est précisément la question que pose la fusion :
le cosinus divise par la racine de la taille de la règle, l'indice de Tversky par une
fraction de ce qu'elle contient en trop, la couverture par rien du tout.

Tout est mesuré sur le jeu de CALIBRAGE (10 exemples par type, tirés du train à
l'étape 4). **Le split test n'est ni lu ni ouvert.** Aucune des trois expériences de
l'article n'est menée ici : traits, définitude et élagage sont l'étape 6.

Usage : python3 src/classify.py
"""

import csv
import json
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

import config
import grasp
import signatures as sig


# ---------------------------------------------------------------------------
# Lecture des entrées
# ---------------------------------------------------------------------------

def charger_signatures():
    """Lit data/signatures/signatures_termes.json. Retourne terme -> ensemble."""
    brut = json.loads(config.FICHIER_SIGNATURES.read_text(encoding="utf-8"))
    return {terme: set(symboles) for terme, symboles in brut.items()}


def charger_calibrage():
    """Lit les exemples de calibrage. Retourne une liste de dicts {syntagme, A, B, rt}.

    Le fichier ne contient que du train : le split test n'y figure pas."""
    exemples = []
    with open(config.FICHIER_SPLIT_CALIBRAGE, encoding="utf-8", newline="") as f:
        for ligne in csv.DictReader(f):
            if ligne["sous_split"] != "calibrage":
                continue
            exemples.append({"syntagme": ligne["syntagme"], "A": ligne["A"],
                             "B": ligne["B"], "rt": ligne["relation"]})
    return exemples


def charger_modele(chemin):
    """Lit un fichier de règles fusionnées. Retourne une liste de règles.

    Les signatures redeviennent des ensembles, et chaque règle reçoit son rang, qui
    sert d'identifiant stable et départage les ex aequo."""
    charge = json.loads(chemin.read_text(encoding="utf-8"))
    regles = []
    for rang, regle in enumerate(charge["regles"]):
        regles.append({"id": rang, "rt": regle["rt"], "poids": regle["poids"],
                       "sL": set(regle["sL"]), "sR": set(regle["sR"]),
                       "exemples": regle["exemples"]})
    return regles


def modeles_disponibles():
    """Les modèles gloutons déjà appris, par seuil croissant. Retourne une liste."""
    trouves = []
    for seuil in config.GRASP_SEUILS:
        chemin = grasp.nom_fichier_modele("glouton", seuil)
        if chemin.exists():
            trouves.append({"seuil": seuil, "chemin": chemin})
    return trouves


# ---------------------------------------------------------------------------
# Les trois mesures de similarité
# ---------------------------------------------------------------------------

def mesure_cosinus(signature_terme, signature_regle):
    """Cosinus sur ensembles, la mesure du papier. Retourne un flottant de 0 à 1.

    Symétrique, et le dénominateur contient la taille de la règle : une règle large est
    pénalisée pour sa largeur. Déléguée telle quelle à signatures.py."""
    return sig.similarite(signature_terme, signature_regle)


def mesure_couverture(signature_terme, signature_regle):
    """Part de la signature du terme expliquée par la règle. Retourne un flottant.

    Asymétrique et sans aucune pénalité de taille : une règle qui contient tout couvre
    tout le monde. C'est l'hypothèse inverse du cosinus, pas un compromis."""
    if not signature_terme:
        return 0.0
    return len(signature_terme & signature_regle) / len(signature_terme)


def mesure_tversky(signature_terme, signature_regle):
    """Indice de Tversky asymétrique. Retourne un flottant de 0 à 1.

    |s∩r| / (|s∩r| + |s\\r| + β|r\\s|) : ce que la règle n'explique pas du terme compte
    plein pot, ce que la règle contient en trop ne compte qu'à hauteur de β. À β = 0 on
    retrouve la couverture, à β = 1 l'indice de Jaccard. C'est le compromis que les deux
    autres mesures encadrent."""
    communs = len(signature_terme & signature_regle)
    if not communs:
        return 0.0
    manquants = len(signature_terme - signature_regle)
    excedent = len(signature_regle - signature_terme)
    return communs / (communs + manquants + config.TVERSKY_BETA * excedent)


MESURES = {"cosinus": mesure_cosinus, "tversky": mesure_tversky,
           "couverture": mesure_couverture}


# ---------------------------------------------------------------------------
# Classification (formule 3)
# ---------------------------------------------------------------------------

def score_regle(signature_a, signature_b, regle, mesure):
    """Score d'une règle pour une forme « A de B ». Retourne un flottant.

    Moyenne des deux similarités, gauche avec gauche et droite avec droite."""
    return 0.5 * (mesure(signature_a, regle["sL"]) + mesure(signature_b, regle["sR"]))


def classer_exemple(exemple, regles, signatures, mesure):
    """Classe une forme contre toutes les règles. Retourne un dict de prédiction.

    Les ex aequo sont départagés par l'identifiant de la règle, pour que la prédiction
    ne dépende pas de l'ordre de parcours."""
    signature_a = signatures.get(exemple["A"], {exemple["A"]})
    signature_b = signatures.get(exemple["B"], {exemple["B"]})

    meilleure, meilleur_score = None, -1.0
    scores_du_bon_type = []
    for regle in regles:
        score = score_regle(signature_a, signature_b, regle, mesure)
        if regle["rt"] == exemple["rt"]:
            scores_du_bon_type.append(score)
        if score > meilleur_score or (score == meilleur_score
                                      and regle["id"] < meilleure["id"]):
            meilleure, meilleur_score = regle, score

    return {
        "syntagme": exemple["syntagme"], "A": exemple["A"], "B": exemple["B"],
        "attendu": exemple["rt"], "predit": meilleure["rt"], "score": meilleur_score,
        "correct": meilleure["rt"] == exemple["rt"],
        "regle": {"id": meilleure["id"], "rt": meilleure["rt"],
                  "poids": meilleure["poids"], "sL": len(meilleure["sL"]),
                  "sR": len(meilleure["sR"]),
                  "orpheline": meilleure["poids"] == 1,
                  "exemples": meilleure["exemples"]},
        "score_moyen_bon_type": (statistics.fmean(scores_du_bon_type)
                                 if scores_du_bon_type else 0.0),
        "score_max_bon_type": max(scores_du_bon_type) if scores_du_bon_type else 0.0,
    }


def classer_tous(exemples, regles, signatures, mesure):
    """Classe tous les exemples de calibrage. Retourne une liste de prédictions."""
    return [classer_exemple(exemple, regles, signatures, mesure)
            for exemple in exemples]


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
    """Précision, rappel et F1 macro, plus le détail par type. Retourne un dict.

    Macro : moyenne non pondérée sur les types attendus, chacun comptant pour un, quel
    que soit le nombre de prédictions qu'il a reçues."""
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


# ---------------------------------------------------------------------------
# Traçabilité des règles gagnantes
# ---------------------------------------------------------------------------

def grandes_regles(regles, part):
    """Identifiants des règles les plus grandes par taille totale. Retourne un ensemble."""
    if not regles:
        return set()
    classees = sorted(regles, key=lambda r: (-(len(r["sL"]) + len(r["sR"])), r["id"]))
    combien = max(1, int(round(part * len(classees))))
    return {regle["id"] for regle in classees[:combien]}


def tracer_gagnantes(predictions, regles):
    """Mesure qui gagne, et ce que coûtent les règles qui ne gagnent jamais.
    Retourne un dict."""
    par_id = {regle["id"]: regle for regle in regles}
    gagnantes = Counter(prediction["regle"]["id"] for prediction in predictions)
    jamais = [regle for regle in regles if regle["id"] not in gagnantes]

    victoires_orphelines = sum(1 for p in predictions if p["regle"]["orpheline"])
    poids_gagnants = [p["regle"]["poids"] for p in predictions]
    tailles_gagnantes = [p["regle"]["sL"] + p["regle"]["sR"] for p in predictions]

    fusionnees = [regle for regle in regles if regle["poids"] > 1]
    fusionnees_gagnantes = {identifiant for identifiant in gagnantes
                            if par_id[identifiant]["poids"] > 1}
    grandes = grandes_regles(regles, config.PART_GRANDES_REGLES)
    victoires_grandes = sum(1 for p in predictions if p["regle"]["id"] in grandes)

    orphelines = [regle for regle in regles if regle["poids"] == 1]
    orphelines_gagnantes = {identifiant for identifiant in gagnantes
                            if par_id[identifiant]["poids"] == 1}
    taux_orpheline = len(orphelines_gagnantes) / len(orphelines) if orphelines else 0.0
    taux_fusionnee = len(fusionnees_gagnantes) / len(fusionnees) if fusionnees else 0.0

    return {
        "regles": len(regles),
        "regles_distinctes_gagnantes": len(gagnantes),
        "n_orphelines": len(orphelines), "n_fusionnees": len(fusionnees),
        "taux_gagnantes_orphelines": taux_orpheline,
        "taux_gagnantes_fusionnees": taux_fusionnee,
        "rapport_taux": taux_fusionnee / taux_orpheline if taux_orpheline else 0.0,
        "part_victoires_orphelines": victoires_orphelines / len(predictions),
        "part_victoires_fusionnees": 1 - victoires_orphelines / len(predictions),
        "part_regles_fusionnees": len(fusionnees) / len(regles) if regles else 0.0,
        "fusionnees_gagnantes": len(fusionnees_gagnantes),
        "fusionnees_jamais": len(fusionnees) - len(fusionnees_gagnantes),
        "jamais_gagnantes": len(jamais),
        "exemples_gaspilles": sum(regle["poids"] for regle in jamais),
        "exemples_gaspilles_fusion": sum(regle["poids"] for regle in jamais
                                         if regle["poids"] > 1),
        "poids_gagnant_median": statistics.median(poids_gagnants),
        "poids_gagnant_max": max(poids_gagnants),
        "taille_gagnante_mediane": statistics.median(tailles_gagnantes),
        "taille_gagnante_max": max(tailles_gagnantes),
        "part_victoires_grandes": victoires_grandes / len(predictions),
        "score_gagnant_moyen": statistics.fmean([p["score"] for p in predictions]),
        "score_moyen_bon_type": statistics.fmean(
            [p["score_moyen_bon_type"] for p in predictions]),
        "score_max_bon_type": statistics.fmean(
            [p["score_max_bon_type"] for p in predictions]),
    }


# ---------------------------------------------------------------------------
# Abstention
# ---------------------------------------------------------------------------

def mesurer_abstention(predictions, types, seuil):
    """Effet d'un seuil d'abstention sur le calibrage. Retourne un dict."""
    retenues = [p for p in predictions if p["score"] >= seuil]
    abstenues = [p for p in predictions if p["score"] < seuil]
    perdues = sum(1 for p in abstenues if p["correct"])
    evaluation = evaluer(retenues, types) if retenues else None
    return {
        "seuil": seuil,
        "abstentions": len(abstenues),
        "taux_abstention": len(abstenues) / len(predictions),
        "f1": evaluation["f1"] if evaluation else 0.0,
        "exactitude": evaluation["exactitude"] if evaluation else 0.0,
        "bonnes_perdues": perdues,
        "part_abstenues_correctes": perdues / len(abstenues) if abstenues else 0.0,
    }


def distribution_scores(predictions):
    """Repères de la distribution des scores gagnants. Retourne un dict."""
    scores = sorted(p["score"] for p in predictions)
    return {"min": scores[0], "c10": sig.centile(scores, 0.10),
            "mediane": statistics.median(scores), "c90": sig.centile(scores, 0.90),
            "max": scores[-1], "moyenne": statistics.fmean(scores)}


# ---------------------------------------------------------------------------
# Écriture des résultats
# ---------------------------------------------------------------------------

def ecrire_resultats(mesure, seuil, predictions, evaluation, trace):
    """Écrit data/resultats/calibrage_<mesure>_<seuil>.json. Retourne le chemin."""
    marque = f"{int(round(seuil * 100)):03d}"
    chemin = config.DOSSIER_RESULTATS / f"calibrage_{mesure}_{marque}.json"
    chemin.parent.mkdir(parents=True, exist_ok=True)
    charge = {
        "mesure": mesure, "seuil_fusion": seuil, "split": "calibrage",
        "n_exemples": len(predictions),
        "genere_le": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "macro": {"precision": evaluation["precision"], "rappel": evaluation["rappel"],
                  "f1": evaluation["f1"], "exactitude": evaluation["exactitude"]},
        "trace": trace,
        "predictions": predictions,
    }
    with open(chemin, "w", encoding="utf-8", newline="") as f:
        json.dump(charge, f, ensure_ascii=False, indent=1)
        f.write("\n")
    return chemin


def ecrire_modele_final(regles_par_type, seuil, mesure, resume):
    """Écrit data/modeles/modele_final.json. Retourne le chemin."""
    contenu = []
    for relation in sorted(regles_par_type):
        for regle in regles_par_type[relation]:
            contenu.append(grasp.serialiser_regle(regle))
    charge = {
        "strategie": "glouton", "seuil": seuil,
        "mesure_similarite": mesure,
        "critere": "les deux (sim des A ET sim des B > seuil)",
        "split": "train complet (50 exemples par type)",
        "trt_centile": config.TRT_CENTILE,
        "choisi_sur": "calibrage (10 exemples par type), split test non touché",
        "f1_calibrage": resume.get("f1_calibrage"),
        "h_top": config.H_TOP, "trt_politique": config.TRT_POLITIQUE,
        "genere_le": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "n_regles": len(contenu), "resume": resume, "regles": contenu,
    }
    config.FICHIER_MODELE_FINAL.parent.mkdir(parents=True, exist_ok=True)
    with open(config.FICHIER_MODELE_FINAL, "w", encoding="utf-8", newline="") as f:
        json.dump(charge, f, ensure_ascii=False, indent=1)
        f.write("\n")
    return config.FICHIER_MODELE_FINAL


# ---------------------------------------------------------------------------
# Balayage
# ---------------------------------------------------------------------------

def lancer_balayage(exemples, signatures, types):
    """Classe le calibrage pour chaque mesure et chaque seuil. Retourne une liste."""
    resultats = []
    for entree in modeles_disponibles():
        regles = charger_modele(entree["chemin"])
        for nom_mesure in config.MESURES_SIMILARITE:
            predictions = classer_tous(exemples, regles, signatures,
                                       MESURES[nom_mesure])
            evaluation = evaluer(predictions, types)
            trace = tracer_gagnantes(predictions, regles)
            chemin = ecrire_resultats(nom_mesure, entree["seuil"], predictions,
                                      evaluation, trace)
            resultats.append({"mesure": nom_mesure, "seuil": entree["seuil"],
                              "predictions": predictions, "evaluation": evaluation,
                              "trace": trace, "fichier": chemin,
                              "distribution": distribution_scores(predictions),
                              "abstention": [mesurer_abstention(predictions, types, s)
                                             for s in config.SEUILS_ABSTENTION]})
            print(f"  {nom_mesure:11s} seuil {fr(entree['seuil'], 2)} : "
                  f"F1 macro {fr(evaluation['f1'])}, "
                  f"exactitude {pct(evaluation['exactitude'])}, "
                  f"{pct(trace['part_victoires_orphelines'])} de victoires orphelines",
                  flush=True)
    return resultats


# ---------------------------------------------------------------------------
# Mise en forme
# ---------------------------------------------------------------------------

def fr(valeur, decimales=3):
    """Formate un nombre à la française, virgule décimale. Retourne une chaîne."""
    return f"{valeur:.{decimales}f}".replace(".", ",")


def pct(part, decimales=1):
    """Formate une proportion en pourcentage. Retourne une chaîne."""
    return f"{100 * part:.{decimales}f} %".replace(".", ",")


def ecart_signe(valeur, decimales=3):
    """Formate un écart avec son signe, en typographie française. Retourne une chaîne."""
    if valeur > 0:
        return "+" + fr(valeur, decimales)
    if valeur < 0:
        return "−" + fr(-valeur, decimales)
    return "="


def tableau(entete, lignes):
    """Construit un tableau Markdown. Retourne une liste de lignes."""
    sortie = ["| " + " | ".join(entete) + " |", "|" + "---|" * len(entete)]
    for ligne in lignes:
        sortie.append("| " + " | ".join(str(c).replace("|", "\\|") for c in ligne) + " |")
    return sortie


def marque_papier(seuil):
    """Signale le seuil du papier dans un tableau. Retourne une chaîne."""
    texte = fr(seuil, 2)
    return f"**{texte}** (papier)" if seuil == config.GRASP_SEUIL_PAPIER else texte


def trouver(resultats, mesure, seuil):
    """Retrouve un résultat par mesure et seuil. Retourne un dict."""
    return next(r for r in resultats if r["mesure"] == mesure and r["seuil"] == seuil)


def par_mesure(resultats, mesure):
    """Résultats d'une mesure, par seuil croissant. Retourne une liste."""
    return [r for r in resultats if r["mesure"] == mesure]


def meilleur_resultat(resultats):
    """Le résultat au meilleur F1 macro. Retourne un dict.

    Ex aequo départagés par le seuil de fusion le plus élevé, qui donne le modèle le
    plus sobre, puis par l'ordre des mesures."""
    return max(resultats, key=lambda r: (r["evaluation"]["f1"], r["seuil"]))


# ---------------------------------------------------------------------------
# Rapport : une fonction par section
# ---------------------------------------------------------------------------

def section_dispositif(exemples, types, resultats):
    """Section 1 : ce qui est classé et comment. Retourne une liste de lignes."""
    seuils = sorted({r["seuil"] for r in resultats})
    return ["## 1. Dispositif", "",
            f"- **Jeu évalué** : les {len(exemples)} exemples de calibrage, "
            f"{len(exemples) // len(types)} par type, tirés du train à l'étape 4. "
            "**Le split test n'est ni lu ni ouvert.**",
            f"- **Modèles** : les {len(seuils)} modèles gloutons déjà appris "
            f"(`data/modeles/`), seuils de fusion {fr(min(seuils), 2)} à "
            f"{fr(max(seuils), 2)}. Rien n'est réappris pour le balayage.",
            "- **Formule 3** : `score = ½ [ sim(s(A), sL) + sim(s(B), sR) ]`, calculé "
            "contre toutes les règles de tous les types. Le `rt` de la mieux classée "
            "est la prédiction. Ex aequo départagés par l'identifiant de la règle.",
            "- **Macro** : chaque type compte pour un, quel que soit le nombre de "
            "prédictions qu'il reçoit.",
            f"- **Hasard** : {pct(1 / len(types))} d'exactitude attendue en tirant au "
            f"sort parmi {len(types)} types.", ""]


def section_classification(resultats):
    """Section 2 : les scores macro par mesure et par seuil. Retourne des lignes."""
    lignes = ["## 2. Tâche 1 — classification du calibrage", ""]
    for nom_mesure in config.MESURES_SIMILARITE:
        corps = []
        for resultat in par_mesure(resultats, nom_mesure):
            evaluation = resultat["evaluation"]
            corps.append([marque_papier(resultat["seuil"]),
                          resultat["trace"]["regles"],
                          fr(evaluation["precision"]), fr(evaluation["rappel"]),
                          f"**{fr(evaluation['f1'])}**",
                          f"{evaluation['corrects']}/{evaluation['total']} "
                          f"({pct(evaluation['exactitude'], 0)})"])
        lignes += [f"### 2.{list(config.MESURES_SIMILARITE).index(nom_mesure) + 1} "
                   f"Mesure « {nom_mesure} »", ""]
        lignes += tableau(["seuil de fusion", "règles", "précision macro",
                           "rappel macro", "F1 macro", "exactitude"], corps)
        lignes += [""]
    return lignes


def section_par_type(resultats, mesure, seuil):
    """Section 2.4 : le détail par type pour une combinaison. Retourne des lignes."""
    resultat = trouver(resultats, mesure, seuil)
    corps = []
    for type_relation in sorted(resultat["evaluation"]["par_type"]):
        detail = resultat["evaluation"]["par_type"][type_relation]
        corps.append([f"`{type_relation}`", detail["attendus"], detail["predits"],
                      detail["vp"], fr(detail["precision"]), fr(detail["rappel"]),
                      fr(detail["f1"])])
    return ([f"### 2.4 Détail par type — « {mesure} », seuil {fr(seuil, 2)}", "",
             "« prédits » est le nombre de fois où le type a été proposé : un type qui "
             "en reçoit beaucoup plus que 10 est un aimant, un type qui en reçoit zéro "
             "n'est jamais proposé.", ""]
            + tableau(["type", "attendus", "prédits", "corrects", "précision", "rappel",
                       "F1"], corps) + [""])


def section_tracabilite(resultats):
    """Section 3 : qui gagne, et ce que la fusion gaspille. Retourne des lignes."""
    lignes = ["## 3. Tâche 2 — traçabilité des règles gagnantes", "",
              "L'hypothèse posée à l'étape 4 : le cosinus place la taille de la règle au "
              "dénominateur, donc une règle fusionnée volumineuse ne peut pas atteindre "
              "un score élevé ; les orphelines gagneraient presque toujours et la fusion "
              "ne ferait que rendre inaccessibles les exemples qu'elle absorbe.", ""]
    for nom_mesure in config.MESURES_SIMILARITE:
        corps = []
        for resultat in par_mesure(resultats, nom_mesure):
            trace = resultat["trace"]
            corps.append([marque_papier(resultat["seuil"]),
                          pct(trace["part_regles_fusionnees"], 0),
                          f"**{pct(trace['part_victoires_fusionnees'], 0)}**",
                          f"{fr(trace['poids_gagnant_median'], 0)} / "
                          f"{trace['poids_gagnant_max']}",
                          f"{fr(trace['taille_gagnante_mediane'], 0)} / "
                          f"{trace['taille_gagnante_max']}",
                          f"{pct(trace['taux_gagnantes_orphelines'], 0)} / "
                          f"{pct(trace['taux_gagnantes_fusionnees'], 0)}",
                          f"**{fr(trace['rapport_taux'], 2)}×**",
                          trace["exemples_gaspilles_fusion"]])
        lignes += [f"### 3.{list(config.MESURES_SIMILARITE).index(nom_mesure) + 1} "
                   f"Mesure « {nom_mesure} »", ""]
        lignes += tableau(["seuil", "part des règles fusionnées",
                           "part des victoires fusionnées", "poids gagnant méd./max",
                           "taille gagnante méd./max",
                           "règles gagnantes : orph. / fus.", "rapport",
                           "exemples absorbés perdus"], corps)
        lignes += [""]
    lignes += ["**Comment lire ces tableaux.** Avec 150 exemples de calibrage, au plus "
               "150 règles peuvent gagner ; un compte brut de règles perdantes mesure "
               "donc surtout la taille du jeu. Les deux colonnes qui testent vraiment "
               "l'hypothèse sont les dernières : « règles gagnantes : orph. / fus. » "
               "donne la part des règles orphelines qui gagnent au moins une fois et "
               "celle des règles fusionnées, et le « rapport » divise la seconde par la "
               "première. **Au-dessus de 1, une règle fusionnée a plus de chances de "
               "gagner qu'une orpheline ; en dessous, la fusion produit des règles que "
               "la mesure n'atteint pas.** C'est ce rapport, et non la part brute de "
               "victoires, qui départage — comparer 30 % de victoires à 24 % de la "
               "population n'aurait pas de sens sans normaliser.", ""]
    return lignes


def section_scores_compares(resultats):
    """Section 3.4 : le score gagnant contre le score du bon type. Retourne des lignes."""
    corps = []
    for nom_mesure in config.MESURES_SIMILARITE:
        for resultat in par_mesure(resultats, nom_mesure):
            trace = resultat["trace"]
            corps.append([nom_mesure, marque_papier(resultat["seuil"]),
                          fr(trace["score_gagnant_moyen"]),
                          fr(trace["score_max_bon_type"]),
                          fr(trace["score_moyen_bon_type"]),
                          fr(trace["score_gagnant_moyen"] - trace["score_moyen_bon_type"])])
    return (["### 3.4 Score gagnant contre score du bon type", "",
             "« meilleure du bon type » est le score de la meilleure règle portant le "
             "type attendu : quand il égale le score gagnant, la prédiction est juste. "
             "« moyenne du bon type » est la moyenne sur toutes les règles de ce type, "
             "elle dit à quel point la bonne réponse se détache du fond.", ""]
            + tableau(["mesure", "seuil", "score gagnant", "meilleure du bon type",
                       "moyenne du bon type", "écart gagnant − moyenne"], corps) + [""])


def section_mesures(resultats):
    """Section 4 : la comparaison des trois mesures. Retourne des lignes."""
    corps = []
    for nom_mesure in config.MESURES_SIMILARITE:
        lot = par_mesure(resultats, nom_mesure)
        meilleur = max(lot, key=lambda r: (r["evaluation"]["f1"], r["seuil"]))
        corps.append([f"**{nom_mesure}**",
                      fr(meilleur["evaluation"]["f1"]),
                      fr(meilleur["seuil"], 2),
                      pct(meilleur["evaluation"]["exactitude"], 0),
                      pct(meilleur["trace"]["part_victoires_fusionnees"], 0),
                      pct(meilleur["trace"]["part_victoires_grandes"], 0),
                      fr(meilleur["distribution"]["mediane"])])
    lignes = ["## 4. Tâche 3 — comparaison des trois mesures", "",
              "Les trois mesures ne diffèrent que par la pénalité infligée à une règle "
              "large :", "",
              "| mesure | formule | pénalité de largeur |",
              "|---|---|---|",
              "| cosinus | \\|s∩r\\| / √(\\|s\\|·\\|r\\|) | racine de la taille de la règle |",
              f"| tversky | \\|s∩r\\| / (\\|s∩r\\| + \\|s\\\\r\\| + β\\|r\\\\s\\|), "
              f"β = {fr(config.TVERSKY_BETA, 1)} | fraction de l'excédent |",
              "| couverture | \\|s∩r\\| / \\|s\\| | aucune |", "",
              "Tversky est la formulation que je propose en tiers : ce n'est pas une "
              "troisième idée mais le point intermédiaire d'une famille à un paramètre. "
              "À β = 0 elle vaut exactement la couverture, à β = 1 l'indice de Jaccard. "
              "Elle permet de savoir si l'écart entre les deux autres vient de la "
              "pénalité elle-même ou de son intensité.", "",
              "La colonne « victoires des 10 % plus grandes » mesure l'effet de bord "
              "annoncé : une règle très large couvre n'importe quel terme.", ""]
    lignes += tableau(["mesure", "meilleur F1 macro", "à quel seuil", "exactitude",
                       "victoires fusionnées", "victoires des 10 % plus grandes",
                       "score médian"], corps)
    return lignes + [""]


def section_abstention(resultats, mesure):
    """Section 5 : distribution des scores et effet de l'abstention. Retourne des lignes."""
    lignes = ["## 5. Tâche 4 — abstention", "",
              f"Mesuré sur la mesure « {mesure} ». Un terme mal décrit dans JDM produit "
              "des similarités faibles avec toutes les règles et sa prédiction est "
              "arbitraire ; l'abstention consiste à ne pas répondre en deçà d'un score.",
              "", "### 5.1 Distribution des scores gagnants", ""]
    corps = []
    for resultat in par_mesure(resultats, mesure):
        distribution = resultat["distribution"]
        corps.append([marque_papier(resultat["seuil"]), fr(distribution["min"]),
                      fr(distribution["c10"]), fr(distribution["mediane"]),
                      fr(distribution["c90"]), fr(distribution["max"])])
    lignes += tableau(["seuil de fusion", "min", "c10", "médiane", "c90", "max"], corps)

    lignes += ["", "### 5.2 Effet des seuils d'abstention", ""]
    for resultat in par_mesure(resultats, mesure):
        corps = []
        for abstention in resultat["abstention"]:
            marque = fr(abstention["seuil"], 2)
            if abstention["seuil"] not in config.SEUILS_ABSTENTION_DEMANDES:
                marque += " *"
            corps.append([marque, abstention["abstentions"],
                          pct(abstention["taux_abstention"], 1),
                          fr(abstention["f1"]),
                          ecart_signe(abstention["f1"]
                                      - resultat["evaluation"]["f1"]),
                          abstention["bonnes_perdues"]])
        lignes += [f"**Seuil de fusion {fr(resultat['seuil'], 2)}** — F1 sans "
                   f"abstention {fr(resultat['evaluation']['f1'])}", ""]
        lignes += tableau(["seuil d'abstention", "abstentions", "taux", "F1 des retenus",
                           "gain de F1", "bonnes prédictions perdues"], corps)
        lignes += [""]
    return lignes


def section_recommandation(resultats, retenu, final):
    """Section 6 : verdict, seuil recommandé, modèle final. Retourne des lignes."""
    cosinus = par_mesure(resultats, "cosinus")
    papier = trouver(resultats, "cosinus", config.GRASP_SEUIL_PAPIER)
    plus_bas = min(cosinus, key=lambda r: r["seuil"])
    plus_haut = max(cosinus, key=lambda r: r["seuil"])
    trace_bas = plus_bas["trace"]

    lignes = ["## 6. Tâche 5 — verdict et recommandation", "",
              "### 6.1 Verdict sur l'hypothèse des règles gagnantes", "",
              "L'hypothèse formulée à l'étape 4 était la suivante : le cosinus place la "
              "taille de la règle au dénominateur, donc une règle fusionnée volumineuse "
              "ne peut pas atteindre un score élevé ; les orphelines gagneraient presque "
              "toujours et la fusion ne ferait que rendre inaccessibles les exemples "
              "qu'elle absorbe.", "",
              "**Elle est réfutée.** Non pas sur la prémisse, qui est exacte, mais sur "
              "la conclusion.", ""]

    corps = []
    for resultat in cosinus:
        trace = resultat["trace"]
        corps.append([marque_papier(resultat["seuil"]),
                      f"{trace['n_orphelines']} / {trace['n_fusionnees']}",
                      pct(trace["taux_gagnantes_orphelines"], 0),
                      pct(trace["taux_gagnantes_fusionnees"], 0),
                      f"**{fr(trace['rapport_taux'], 2)}×**"])
    lignes += tableau(["seuil", "règles orph. / fus.",
                       "part des orphelines qui gagnent",
                       "part des fusionnées qui gagnent", "rapport"], corps)

    rapports = [r["trace"]["rapport_taux"] for r in cosinus
                if r["trace"]["n_fusionnees"]]
    lignes += ["",
               f"Sous le cosinus, une règle fusionnée gagne **plus** souvent qu'une "
               f"orpheline, à tous les seuils : le rapport va de "
               f"{fr(min(rapports), 2)} à {fr(max(rapports), 2)}. Au seuil "
               f"{fr(plus_bas['seuil'], 2)}, les règles fusionnées sont "
               f"{pct(trace_bas['part_regles_fusionnees'], 0)} de la population et "
               f"remportent {pct(trace_bas['part_victoires_fusionnees'], 0)} des "
               "prédictions. La part brute de victoires orphelines, spectaculaire, ne "
               "disait rien d'autre que le fait qu'il y a beaucoup plus d'orphelines.",
               "",
               "La raison pour laquelle la prémisse n'entraîne pas la conclusion : "
               "fusionner agrandit le dénominateur, mais la signature élargie recoupe "
               "aussi davantage de termes, donc le numérateur grandit lui aussi. Le "
               "cosinus ne neutralise pas la fusion, il la tempère — et la tempérer "
               "suffisait, puisque c'est la mesure sans pénalité qui s'effondre.", "",
               "**Ce que le balayage montre à la place** : le seuil de fusion ne change "
               f"presque rien au F1. De {fr(plus_bas['seuil'], 2)} à "
               f"{fr(plus_haut['seuil'], 2)}, il va de "
               f"{fr(plus_bas['evaluation']['f1'])} à "
               f"{fr(plus_haut['evaluation']['f1'])}, soit "
               f"{plus_bas['evaluation']['corrects'] - plus_haut['evaluation']['corrects']} "
               "exemples d'écart sur 150. La fusion aide un peu, régulièrement, sans "
               "jamais être décisive. L'étape 4 s'inquiétait d'un emballement ; "
               "l'emballement existe bien dans les signatures, mais il ne se traduit ni "
               "par un gain ni par une catastrophe à la classification.", "",
               "### 6.2 Ce que la comparaison des mesures établit", ""]

    meilleur_par_mesure = {}
    for nom in config.MESURES_SIMILARITE:
        lot = par_mesure(resultats, nom)
        meilleur_par_mesure[nom] = max(lot, key=lambda r: (r["evaluation"]["f1"],
                                                           r["seuil"]))
    couverture = meilleur_par_mesure["couverture"]
    tversky = meilleur_par_mesure["tversky"]
    cos = meilleur_par_mesure["cosinus"]
    lignes += [f"**Le cosinus reste la meilleure des trois** : "
               f"{fr(cos['evaluation']['f1'])} de F1 macro contre "
               f"{fr(tversky['evaluation']['f1'])} pour Tversky et "
               f"{fr(couverture['evaluation']['f1'])} pour la couverture.", "",
               "L'effet de bord annoncé pour la couverture est vérifié et il est massif :"
               f" {pct(couverture['trace']['part_victoires_grandes'], 0)} de ses "
               "prédictions sont remportées par les 10 % de règles les plus grandes, et "
               f"seulement {couverture['trace']['regles_distinctes_gagnantes']} règles "
               f"distinctes gagnent quoi que ce soit sur "
               f"{couverture['trace']['regles']}. Une poignée de règles énormes couvre "
               "tout le monde. Ses scores sont aussi bien plus hauts "
               f"(médiane {fr(couverture['distribution']['mediane'])} contre "
               f"{fr(cos['distribution']['mediane'])}) sans être plus justes : la "
               "couverture est confiante et fausse.", "",
               f"Tversky à β = {fr(config.TVERSKY_BETA, 1)} se place exactement où on "
               f"l'attendait, entre les deux — "
               f"{pct(tversky['trace']['part_victoires_grandes'], 0)} de victoires pour "
               "les plus grandes règles, contre "
               f"{pct(cos['trace']['part_victoires_grandes'], 0)} au cosinus et "
               f"{pct(couverture['trace']['part_victoires_grandes'], 0)} à la "
               "couverture. Comme le F1 décroît de façon monotone du cosinus vers la "
               "couverture, **la pénalité de largeur n'est pas un défaut à corriger : "
               "plus on la retire, plus on classe mal.** C'est le résultat que la "
               "famille à un paramètre permettait d'établir, et qui n'aurait pas été "
               "lisible avec deux mesures seulement.", "",
               "### 6.3 Abstention", ""]

    seuils_demandes = config.SEUILS_ABSTENTION_DEMANDES
    retenu_abst = [a for a in retenu["abstention"] if a["seuil"] in seuils_demandes]
    maximum = max(retenu["abstention"], key=lambda a: a["f1"])
    lignes += [f"Le score gagnant le plus faible du calibrage est "
               f"{fr(retenu['distribution']['min'])}. **Les quatre seuils demandés — "
               + ", ".join(fr(s, 2) for s in seuils_demandes) +
               " — sont donc tous sous le plancher observé** : le plus élevé ne fait "
               f"abstenir que {retenu_abst[-1]['abstentions']} exemple sur 150. Il n'y a "
               "rien à trancher dans cette plage, et c'est en soi un résultat : sur ce "
               "corpus, aucun terme n'est assez mal décrit dans JDM pour produire un "
               "score quasi nul.", "",
               "J'ai prolongé le balayage jusqu'à "
               f"{fr(max(config.SEUILS_ABSTENTION), 2)} pour que la courbe soit "
               f"lisible. Le meilleur F1 des retenus, {fr(maximum['f1'])}, est atteint à "
               f"{fr(maximum['seuil'], 2)} pour "
               f"{pct(maximum['taux_abstention'], 0)} d'abstention et "
               f"{maximum['bonnes_perdues']} bonnes prédictions perdues. Le gain sur le "
               f"F1 est de {ecart_signe(maximum['f1'] - retenu['evaluation']['f1'])} : "
               "l'abstention ne sauve pas ce classifieur. Je ne fixe pas de seuil.", "",
               "### 6.4 Seuil de fusion recommandé", "",
               f"**{fr(retenu['seuil'], 2)}**, avec le cosinus. F1 macro "
               f"{fr(retenu['evaluation']['f1'])} sur le calibrage, "
               f"{retenu['evaluation']['corrects']}/{retenu['evaluation']['total']} "
               f"exemples justes, contre {pct(1 / 15)} attendus au hasard.", ""]
    corps = []
    for resultat in cosinus:
        corps.append([marque_papier(resultat["seuil"]),
                      fr(resultat["evaluation"]["f1"]),
                      f"{resultat['evaluation']['corrects']}/150",
                      resultat["trace"]["regles"],
                      pct(resultat["trace"]["part_victoires_fusionnees"], 0)])
    lignes += tableau(["seuil", "F1 macro", "corrects", "règles",
                       "victoires fusionnées"], corps)
    ecart_papier = retenu["evaluation"]["f1"] - papier["evaluation"]["f1"]
    lignes += ["",
               "La franchise s'impose sur ce choix : l'écart entre "
               f"{fr(retenu['seuil'], 2)} et les deux seuils suivants vaut "
               f"{fr(retenu['evaluation']['f1'] - trouver(resultats, 'cosinus', 0.45)['evaluation']['f1'])} "
               "de F1, soit trois exemples sur 150. **Ce n'est pas significatif à cette "
               f"taille de jeu.** Ce qui départage vraiment {fr(retenu['seuil'], 2)}, "
               f"c'est la compacité : {retenu['trace']['regles']} règles contre "
               f"{papier['trace']['regles']} au seuil du papier, pour un F1 supérieur de "
               f"{fr(ecart_papier)}. À performance équivalente, le modèle le plus petit "
               "est préférable, et c'est le seul argument que les chiffres autorisent.",
               "",
               f"Le seuil {fr(config.GRASP_SEUIL_PAPIER, 2)} de l'article donne "
               f"{fr(papier['evaluation']['f1'])}, soit "
               f"{fr(abs(ecart_papier))} de moins. Il reste dans le rapport comme point "
               "de comparaison, mais il n'est pas le meilleur choix sur ce corpus.", "",
               "### 6.5 Modèle final", "",
               f"Réappris sur le train complet — "
               f"{config.TAILLE_APPRENTISSAGE + config.TAILLE_CALIBRAGE} exemples par "
               f"type, {15 * (config.TAILLE_APPRENTISSAGE + config.TAILLE_CALIBRAGE)} en "
               f"tout — au seuil {fr(retenu['seuil'], 2)}, stratégie gloutonne, critère "
               f"« les deux ». **{final['n_regles']} règles**, dont "
               f"{final['orphelines']} orphelines "
               f"({pct(final['part_orphelines'], 0)}), écrites dans "
               f"`{config.FICHIER_MODELE_FINAL.relative_to(config.RACINE).as_posix()}`.",
               "",
               "Il n'est pas classé contre le test : c'est l'étape 6. Le calibrage a "
               "servi à choisir le seuil, il ne peut donc plus servir à estimer la "
               "performance ; les 53 % d'exactitude ci-dessus sont une valeur de "
               "sélection, pas une mesure de généralisation.", ""]
    return lignes


def section_sorties(resultats, chemin_final):
    """Section 7 : les fichiers écrits. Retourne des lignes."""
    return (["## 7. Sorties écrites", "",
             f"- **{len(resultats)} fichiers de prédictions** dans "
             f"`{config.DOSSIER_RESULTATS.relative_to(config.RACINE).as_posix()}/`, un "
             "par couple mesure × seuil, nommés `calibrage_<mesure>_<seuil>.json`. "
             "Chacun porte, pour ses 150 exemples, le type attendu, le type prédit, le "
             "score, et la règle gagnante avec son poids, la taille de ses deux "
             "signatures et les exemples qu'elle couvre.",
             f"- **Le modèle final** dans "
             f"`{chemin_final.relative_to(config.RACINE).as_posix()}`.",
             "- Aucune matrice de similarité n'est stockée : les scores sont calculés à "
             "la volée et seuls les gagnants sont conservés.", ""])


def construire_rapport(resultats, retenu, final, chemin_final, exemples, types):
    """Assemble reports/rapport_classification.md. Ne retourne rien."""
    chemin = config.DOSSIER_RAPPORTS / "rapport_classification.md"
    lignes = ["# Classification et choix du seuil de fusion", "",
              "Étape 5 : la formule 3 de l'article appliquée aux règles apprises à "
              "l'étape 4, trois mesures de similarité comparées, et le seuil de fusion "
              "arrêté sur le jeu de calibrage. **Le split test n'est ni lu ni ouvert.** "
              "Aucune des trois expériences de l'article n'est menée ici.", ""]
    lignes += section_dispositif(exemples, types, resultats)
    lignes += section_classification(resultats)
    lignes += section_par_type(resultats, retenu["mesure"], retenu["seuil"])
    lignes += section_tracabilite(resultats)
    lignes += section_scores_compares(resultats)
    lignes += section_mesures(resultats)
    lignes += section_abstention(resultats, retenu["mesure"])
    lignes += section_recommandation(resultats, retenu, final)
    lignes += section_sorties(resultats, chemin_final)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    print(f"Rapport écrit : {chemin}", flush=True)


# ---------------------------------------------------------------------------
# Modèle final
# ---------------------------------------------------------------------------

def reapprendre_sur_train(signatures, seuil):
    """Réapprend sur les 50 exemples de train de chaque type. Retourne (règles, résumé)."""
    lignes_train = grasp.charger_lignes_train()
    regles_par_type, mesures = {}, []
    for relation in sorted(lignes_train):
        depart = grasp.regles_initiales(lignes_train[relation], signatures)
        apres, journal = grasp.apprendre(depart, "glouton", seuil)
        regles_par_type[relation] = apres
        mesures.append(grasp.instrumenter(relation, depart, apres, journal))
    resume = grasp.agreger(mesures)
    resume["orphelines"] = sum(m["orphelines"] for m in mesures)
    resume["n_regles"] = resume["apres"]
    resume["part_orphelines"] = resume["orphelines"] / resume["apres"]
    return regles_par_type, resume


# ---------------------------------------------------------------------------
# Enchaînement
# ---------------------------------------------------------------------------

def main():
    if not modeles_disponibles():
        print("Aucun modèle de balayage dans "
              f"{config.DOSSIER_MODELES.relative_to(config.RACINE).as_posix()}/ : "
              "lancez d'abord `python3 src/grasp.py`, qui les produit.", file=sys.stderr)
        return

    signatures = charger_signatures()
    exemples = charger_calibrage()
    types = sorted({exemple["rt"] for exemple in exemples})
    print(f"Signatures : {len(signatures)}. Calibrage : {len(exemples)} exemples sur "
          f"{len(types)} types. Test non touché.", flush=True)

    resultats = lancer_balayage(exemples, signatures, types)

    retenu = meilleur_resultat(resultats)
    print(f"Retenu : « {retenu['mesure']} » au seuil {fr(retenu['seuil'], 2)}, "
          f"F1 macro {fr(retenu['evaluation']['f1'])}.", flush=True)

    regles_finales, resume = reapprendre_sur_train(signatures, retenu["seuil"])
    resume["f1_calibrage"] = retenu["evaluation"]["f1"]
    chemin_final = ecrire_modele_final(regles_finales, retenu["seuil"],
                                       retenu["mesure"], resume)
    print(f"Modèle final : {resume['n_regles']} règles sur le train complet "
          f"-> {chemin_final}", flush=True)

    construire_rapport(resultats, retenu, resume, chemin_final, exemples, types)


if __name__ == "__main__":
    main()
