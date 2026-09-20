#!/usr/bin/env python3
"""Étape 6 : évaluation sur le split test, et les trois expériences de l'article.

**C'est ici que le split test est ouvert.** Les 450 exemples (30 par type) n'avaient
jamais été lus. Tous les paramètres ont été arrêtés à l'étape 5, sur le jeu de
calibrage, et sont figés : aucun n'est ajusté en fonction des scores obtenus ici.

Contenu, dans l'ordre de l'article :
  - évaluation principale avec data/modeles/modele_final.json, par type (Tableau 3) ;
  - Expérience 1, apport de chaque trait (Tableau 2) ;
  - Expérience 2, trait de définitude (Tableau 4), étendue pour distinguer notre trait
    des annotations morphologiques déjà présentes dans JeuxDeMots ;
  - Expérience 3, élagage des règles (Tableau 5) ;
  - analyse des cas d'échec (section 4.5) ;
  - évaluation indulgente (section 4.3).

Chaque configuration des Expériences 1 et 2 demande un pipeline COMPLET : filtrer les
signatures sur les traits retenus, RÉAPPRENDRE les règles, puis classer. Se contenter
d'ignorer des symboles à la classification donnerait des règles apprises sur une autre
représentation que celle qu'on évalue.

Aucun appel réseau, aucune recollecte, aucun outil interactif.

Usage : python3 src/evaluate.py
"""

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


CHEMIN_RAPPORT = config.DOSSIER_RAPPORTS / "rapport_evaluation.md"
CHEMIN_PREDICTIONS = config.DOSSIER_RESULTATS / "test_predictions.json"
CHEMIN_MATRICE = config.DOSSIER_RESULTATS / "matrice_confusion.csv"

# Scores publiés par l'article, pour mise en regard. Tableau 3 pour le détail par type,
# Tableau 2 pour les configurations de traits, Tableau 4 pour la définitude.
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
ARTICLE_MACRO = (78.0, 77.3, 0.772)
ARTICLE_TRAITS = {"H": 0.653, "H+SST": 0.691, "H+TRT": 0.767, "H+TRT+SST": 0.772}
ARTICLE_DEFINITUDE = {"H+TRT+SST": 0.772, "H+TRT+SST+DEF": 0.795}
ARTICLE_ELAGAGE = {"Trim": (79.6, 77.6, 0.77, 49, 25.42),
                   "No Trim": (80.36, 80.0, 0.798, 1384, 92.78)}

# Écart relatif maximal au meilleur score pour qu'un second type compte comme correct
# dans l'évaluation indulgente (article, §4.3).
TOLERANCE_INDULGENTE = 0.05

# En deçà de ce nombre de symboles, une signature est jugée trop pauvre pour décider.
SIGNATURE_PAUVRE = config.SEUIL_SIGNATURE_QUASI_VIDE

# Préfixe des symboles de définitude ajoutés à la signature de B (Expérience 2).
PREFIXE_DEF = "DEF:"


# ---------------------------------------------------------------------------
# Lecture du corpus, train et test
# ---------------------------------------------------------------------------

def charger_lignes(split):
    """Lignes d'un split, par type de relation. Retourne relation -> liste de dicts."""
    par_type = defaultdict(list)
    for chemin in sorted(config.DOSSIER_CORPUS_PROPRE.glob("corpus_*.csv")):
        with open(chemin, encoding="utf-8", newline="") as f:
            for ligne in csv.DictReader(f):
                if ligne["split"] != split or not ligne["A"] or not ligne["B"]:
                    continue
                par_type[ligne["relation"]].append({
                    "syntagme": ligne["syntagme"], "A": ligne["A"], "B": ligne["B"],
                    "rt": ligne["relation"], "det": ligne["det"],
                    "definitude": ligne["definitude"],
                })
    return par_type


def aplatir(par_type):
    """Concatène les lignes de tous les types, types triés. Retourne une liste."""
    lignes = []
    for relation in sorted(par_type):
        lignes += par_type[relation]
    return lignes


# ---------------------------------------------------------------------------
# Signatures par configuration de traits
# ---------------------------------------------------------------------------

def symboles_sst_filtres(enregistrement, sans_morpho):
    """Symboles SST, avec ou sans les annotations morphologiques. Retourne un ensemble.

    Les annotations DET et NODET de JeuxDeMots portent déjà une information de
    déterminant : les retirer permet de mesurer ce que notre propre trait apporte."""
    symboles = set()
    for annotation in enregistrement.get("SST") or []:
        if annotation["poids"] <= 0:
            continue
        if sans_morpho and annotation["morpho"]:
            continue
        symboles.add(config.PREFIXE_SST + annotation["tag"])
    return symboles


def signature_de_terme(terme, enregistrement, traits, seuils, sans_morpho):
    """Signature d'un terme restreinte aux traits demandés. Retourne un ensemble.

    Le terme lui-même y figure toujours, quelle que soit la configuration : l'article
    le précise en section 3."""
    signature = {terme}
    if enregistrement is None or not enregistrement.get("existe"):
        return signature
    if "H" in traits:
        signature |= sig.symboles_h(enregistrement)
    if "TRT" in traits:
        signature |= sig.symboles_trt(enregistrement, seuils)
    if "SST" in traits:
        signature |= symboles_sst_filtres(enregistrement, sans_morpho)
    return signature


def construire_signatures(collecte, termes, traits, sans_morpho=False):
    """Signatures de tous les termes du corpus pour une configuration.
    Retourne terme -> ensemble."""
    seuils = {}
    if config.TRT_POLITIQUE == "centile":
        effectifs = {}
        for terme in sorted(termes):
            enregistrement = collecte.get(terme)
            effectifs[terme] = sig.effectifs_trt(enregistrement) if enregistrement else {}
        seuils = sig.seuils_par_type(effectifs, config.TRT_CENTILE)
    signatures = {}
    for terme in sorted(termes):
        signatures[terme] = signature_de_terme(terme, collecte.get(terme), traits,
                                               seuils, sans_morpho)
    return signatures


def symboles_definitude(ligne):
    """Les deux symboles de définitude d'une ligne de corpus. Retourne un ensemble.

    Ils dépendent de la LIGNE et non du terme : « photo de famille » et « photo d'une
    famille » partagent le terme B mais pas le déterminant."""
    symboles = set()
    if ligne["det"]:
        symboles.add(PREFIXE_DEF + ligne["det"])
    if ligne["definitude"]:
        symboles.add(PREFIXE_DEF + ligne["definitude"])
    return symboles


def cotes_de_ligne(ligne, signatures, avec_definitude):
    """Signatures gauche et droite d'une ligne. Retourne un couple d'ensembles."""
    gauche = set(signatures.get(ligne["A"], {ligne["A"]}))
    droite = set(signatures.get(ligne["B"], {ligne["B"]}))
    if avec_definitude:
        droite |= symboles_definitude(ligne)
    return gauche, droite


# ---------------------------------------------------------------------------
# Apprentissage d'une configuration
# ---------------------------------------------------------------------------

def regles_de_depart(lignes_par_type, signatures, avec_definitude):
    """Une règle de poids 1 par ligne d'entraînement. Retourne relation -> liste."""
    depart = {}
    for relation in sorted(lignes_par_type):
        regles = []
        for rang, ligne in enumerate(lignes_par_type[relation]):
            gauche, droite = cotes_de_ligne(ligne, signatures, avec_definitude)
            regles.append({"sL": gauche, "sR": droite, "rt": relation, "poids": 1,
                           "exemples": [ligne["syntagme"]], "ordre": rang})
        depart[relation] = regles
    return depart


def apprendre_configuration(lignes_train, signatures, avec_definitude):
    """Réapprend le modèle complet pour une configuration.
    Retourne (règles finales, toutes les règles ayant existé)."""
    depart = regles_de_depart(lignes_train, signatures, avec_definitude)
    finales, historique = [], []
    for relation in sorted(depart):
        trace = []
        apres, _ = grasp.fusionner_glouton(depart[relation], config.GRASP_SEUIL_PAPIER,
                                           historique=trace)
        finales += apres
        historique += trace
    return numeroter(finales), numeroter(historique)


def numeroter(regles):
    """Donne un identifiant stable à chaque règle. Retourne une liste."""
    numerotees = []
    for identifiant, regle in enumerate(regles):
        copie = dict(regle)
        copie["id"] = identifiant
        numerotees.append(copie)
    return numerotees


def charger_modele_final():
    """Lit data/modeles/modele_final.json. Retourne une liste de règles."""
    charge = json.loads(config.FICHIER_MODELE_FINAL.read_text(encoding="utf-8"))
    regles = []
    for identifiant, regle in enumerate(charge["regles"]):
        regles.append({"id": identifiant, "rt": regle["rt"], "poids": regle["poids"],
                       "sL": set(regle["sL"]), "sR": set(regle["sR"]),
                       "exemples": regle["exemples"]})
    return regles, charge


# ---------------------------------------------------------------------------
# Classification (formule 3, mesure figée)
# ---------------------------------------------------------------------------

def classer_ligne(ligne, regles, signatures, avec_definitude):
    """Classe une ligne de test contre toutes les règles. Retourne un dict."""
    gauche, droite = cotes_de_ligne(ligne, signatures, avec_definitude)
    mesure = classify.MESURES[config.MESURE_FIGEE]

    meilleure, meilleur_score = None, -1.0
    meilleur_par_type = {}
    scores_du_bon_type = []
    for regle in regles:
        score = 0.5 * (mesure(gauche, regle["sL"]) + mesure(droite, regle["sR"]))
        if score > meilleur_par_type.get(regle["rt"], -1.0):
            meilleur_par_type[regle["rt"]] = score
        if regle["rt"] == ligne["rt"]:
            scores_du_bon_type.append(score)
        if score > meilleur_score or (score == meilleur_score
                                      and regle["id"] < meilleure["id"]):
            meilleure, meilleur_score = regle, score

    classement = sorted(meilleur_par_type, key=lambda t: (-meilleur_par_type[t], t))
    return {
        "syntagme": ligne["syntagme"], "A": ligne["A"], "B": ligne["B"],
        "attendu": ligne["rt"], "predit": meilleure["rt"], "score": meilleur_score,
        "correct": meilleure["rt"] == ligne["rt"],
        "classement": [{"rt": t, "score": meilleur_par_type[t]} for t in classement[:3]],
        "score_attendu": meilleur_par_type.get(ligne["rt"], 0.0),
        "score_max_bon_type": max(scores_du_bon_type) if scores_du_bon_type else 0.0,
        "score_moyen_bon_type": (statistics.fmean(scores_du_bon_type)
                                 if scores_du_bon_type else 0.0),
        "regle": {"id": meilleure["id"], "rt": meilleure["rt"],
                  "poids": meilleure["poids"], "sL": len(meilleure["sL"]),
                  "sR": len(meilleure["sR"]),
                  "orpheline": meilleure["poids"] == 1,
                  "exemples": meilleure["exemples"]},
        "taille_sA": len(gauche), "taille_sB": len(droite),
    }


def classer_tout(lignes_test, regles, signatures, avec_definitude):
    """Classe les 450 exemples de test. Retourne (prédictions, durée en secondes)."""
    debut = time.perf_counter()
    predictions = [classer_ligne(ligne, regles, signatures, avec_definitude)
                   for ligne in lignes_test]
    return predictions, time.perf_counter() - debut


# ---------------------------------------------------------------------------
# Métriques (section 4.4 de l'article)
# ---------------------------------------------------------------------------

def evaluer(predictions, types):
    """Précision, rappel et F1 par type puis en macro. Retourne un dict."""
    return classify.evaluer(predictions, types)


def evaluation_indulgente(predictions, types):
    """Compte correct un type attendu classé 2e à moins de 5 % du 1er. Retourne un dict.

    Alternative évoquée en §4.3 de l'article. Elle ne remplace pas l'évaluation
    stricte : elle dit combien d'erreurs sont des quasi-égalités."""
    indulgentes, repeches = [], []
    for prediction in predictions:
        copie = dict(prediction)
        if not prediction["correct"] and len(prediction["classement"]) > 1:
            premier = prediction["classement"][0]["score"]
            second = prediction["classement"][1]
            ecart = (premier - second["score"]) / premier if premier else 1.0
            if second["rt"] == prediction["attendu"] and ecart <= TOLERANCE_INDULGENTE:
                copie["predit"] = prediction["attendu"]
                copie["correct"] = True
                repeches.append(prediction)
        indulgentes.append(copie)
    resultat = evaluer(indulgentes, types)
    resultat["repeches"] = repeches
    return resultat


def matrice_confusion(predictions, types):
    """Compte les prédictions pour chaque couple (attendu, prédit).
    Retourne un dict de dicts."""
    matrice = {attendu: {predit: 0 for predit in types} for attendu in types}
    for prediction in predictions:
        matrice[prediction["attendu"]][prediction["predit"]] += 1
    return matrice


def confusions_frequentes(matrice, types, combien):
    """Les couples (attendu, prédit) distincts les plus fréquents. Retourne une liste."""
    couples = []
    for attendu in types:
        for predit in types:
            if attendu != predit and matrice[attendu][predit]:
                couples.append((attendu, predit, matrice[attendu][predit]))
    couples.sort(key=lambda c: (-c[2], c[0], c[1]))
    return couples[:combien]


# ---------------------------------------------------------------------------
# Analyse des cas d'échec (section 4.5)
# ---------------------------------------------------------------------------

def indices_de_cause(collecte, signatures):
    """Prépare ce qu'il faut pour attribuer une cause. Retourne un dict de fonctions."""
    def raffinements(terme):
        enregistrement = collecte.get(terme) or {}
        return len(enregistrement.get("raffinements") or [])

    def singulier_mieux_doté(terme):
        enregistrement = collecte.get(terme) or {}
        diagnostic = enregistrement.get("diagnostic_singulier")
        return bool(diagnostic and diagnostic.get("existe")
                    and diagnostic.get("H_taille"))

    def pauvre(terme):
        return len(signatures.get(terme, {terme})) < SIGNATURE_PAUVRE

    return {"raffinements": raffinements, "singulier": singulier_mieux_doté,
            "pauvre": pauvre}


def drapeaux_de_cause(prediction, indices):
    """Toutes les causes possibles d'un échec, non exclusives. Retourne un ensemble."""
    a, b = prediction["A"], prediction["B"]
    drapeaux = set()
    if indices["pauvre"](a) or indices["pauvre"](b):
        drapeaux.add("défaut de connaissance")
    if indices["singulier"](a) or indices["singulier"](b):
        drapeaux.add("dispersion morphologique")
    premier = prediction["classement"][0]["score"]
    ecart = (premier - prediction["score_attendu"]) / premier if premier else 1.0
    if ecart <= TOLERANCE_INDULGENTE:
        drapeaux.add("classe multiple")
    if indices["raffinements"](a) >= 2 or indices["raffinements"](b) >= 2:
        drapeaux.add("polysémie")
    return drapeaux or {"autre"}


# Ordre d'attribution exclusive : du plus spécifique au plus général. La polysémie
# passe en dernier parce qu'elle est très répandue — 61 % des termes ont au moins un
# raffinement — et absorberait tout le reste si elle venait en premier.
PRIORITE_CAUSES = ("défaut de connaissance", "dispersion morphologique",
                   "classe multiple", "polysémie", "autre")


def cause_principale(drapeaux):
    """Retient une seule cause par ordre de priorité. Retourne une chaîne."""
    for cause in PRIORITE_CAUSES:
        if cause in drapeaux:
            return cause
    return "autre"


def analyser_echecs(predictions, indices):
    """Classe les erreurs par cause. Retourne (liste des échecs, comptes)."""
    echecs = []
    for prediction in predictions:
        if prediction["correct"]:
            continue
        drapeaux = drapeaux_de_cause(prediction, indices)
        echec = dict(prediction)
        echec["drapeaux"] = sorted(drapeaux)
        echec["cause"] = cause_principale(drapeaux)
        echecs.append(echec)
    exclusives = Counter(echec["cause"] for echec in echecs)
    non_exclusives = Counter()
    for echec in echecs:
        for drapeau in echec["drapeaux"]:
            non_exclusives[drapeau] += 1
    return echecs, exclusives, non_exclusives


# ---------------------------------------------------------------------------
# Traçabilité sur le test
# ---------------------------------------------------------------------------

def tracer(predictions, regles):
    """Qui gagne sur le test, et ce que la fusion immobilise. Retourne un dict."""
    return classify.tracer_gagnantes(predictions, regles)


# ---------------------------------------------------------------------------
# Écriture des sorties de données
# ---------------------------------------------------------------------------

def ecrire_predictions(predictions, evaluation, indulgente, modele):
    """Écrit data/resultats/test_predictions.json. Retourne le chemin."""
    CHEMIN_PREDICTIONS.parent.mkdir(parents=True, exist_ok=True)
    charge = {
        "split": "test (450 exemples, 30 par type) — ouvert à l'étape 6",
        "modele": config.FICHIER_MODELE_FINAL.name,
        "parametres_figes": parametres_figes(modele),
        "genere_le": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "macro_stricte": {k: evaluation[k] for k in
                          ("precision", "rappel", "f1", "exactitude")},
        "macro_indulgente": {k: indulgente[k] for k in
                             ("precision", "rappel", "f1", "exactitude")},
        "predictions": predictions,
    }
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


def parametres_figes(modele):
    """Les réglages arrêtés à l'étape 5. Retourne un dict."""
    return {
        "seuil_fusion": modele["seuil"], "strategie": modele["strategie"],
        "critere_fusion": modele["critere"], "mesure_similarite": config.MESURE_FIGEE,
        "seuil_abstention": None, "trt_politique": config.TRT_POLITIQUE,
        "h_top": config.H_TOP, "sst_exclure_morpho": config.SST_EXCLURE_MORPHO,
        "trt_types_exclus": len(config.TRT_TYPES_EXCLUS),
    }


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
    """Formate un écart avec son signe. Retourne une chaîne."""
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


# ---------------------------------------------------------------------------
# Rapport : une fonction par section
# ---------------------------------------------------------------------------

def section_parametres(modele, lignes_test):
    """Section 1 : les réglages figés et l'ouverture du test. Retourne des lignes."""
    figes = parametres_figes(modele)
    corps = [
        ["seuil de fusion", fr(figes["seuil_fusion"], 2)],
        ["stratégie d'ordonnancement", figes["strategie"]],
        ["critère de fusion", figes["critere_fusion"]],
        ["mesure de similarité", figes["mesure_similarite"]],
        ["seuil d'abstention", "aucun — mesuré inutile au calibrage"],
        ["politique de sélection TRT", f"`{figes['trt_politique']}` (lecture de l'article)"],
        ["hyperonymes gardés", f"top {figes['h_top']}"],
        ["annotations SST morphologiques", "conservées"],
        ["types TRT exclus", f"{figes['trt_types_exclus']} types non sémantiques"],
        ["modèle", f"`{config.FICHIER_MODELE_FINAL.name}`, {modele['n_regles']} règles"],
    ]
    return (["## 1. Ouverture du split test", "",
             f"**Les {len(lignes_test)} exemples de test (30 par type) sont lus pour la "
             "première fois.** Tous les réglages ci-dessous ont été arrêtés à l'étape 5 "
             "sur le jeu de calibrage, avant toute lecture du test. **Aucun n'est ajusté "
             "en fonction des scores de ce rapport.**", ""]
            + tableau(["paramètre", "valeur figée"], corps)
            + ["",
               "Rappel de méthode : le F1 de 0,520 obtenu au calibrage était une valeur "
               "de sélection, pas une estimation de généralisation. Les chiffres qui "
               "suivent sont la première mesure honnête de ce que vaut le système.", ""])


def section_principale(evaluation, indulgente, predictions):
    """Section 2 : le Tableau 3 de l'article, en regard. Retourne des lignes."""
    par_type = evaluation["par_type"]
    classes = sorted(par_type, key=lambda t: (-par_type[t]["f1"], t))
    corps = []
    for relation in classes:
        detail = par_type[relation]
        p_art, r_art, f1_art = ARTICLE_PAR_TYPE.get(relation, (0, 0, 0.0))
        corps.append([f"`{relation}`",
                      fr(100 * detail["precision"], 1), fr(100 * detail["rappel"], 1),
                      f"**{fr(detail['f1'], 2)}**",
                      fr(f1_art, 2), ecart_signe(detail["f1"] - f1_art, 2)])
    corps.append(["**moyenne macro**",
                  f"**{fr(100 * evaluation['precision'], 1)}**",
                  f"**{fr(100 * evaluation['rappel'], 1)}**",
                  f"**{fr(evaluation['f1'], 3)}**",
                  f"**{fr(ARTICLE_MACRO[2], 3)}**",
                  f"**{ecart_signe(evaluation['f1'] - ARTICLE_MACRO[2])}**"])
    return (["## 2. Évaluation principale (Tableau 3 de l'article)", "",
             f"{evaluation['corrects']}/{evaluation['total']} exemples correctement "
             f"classés, soit {pct(evaluation['exactitude'])} d'exactitude, contre "
             f"{pct(1 / len(par_type))} attendus en tirant au hasard. Types triés par F1 "
             "décroissant.", ""]
            + tableau(["type", "P (%)", "R (%)", "F1", "F1 article", "écart"], corps)
            + ["",
               f"**Évaluation indulgente** (§4.3 de l'article : le type attendu compte "
               f"comme correct s'il arrive 2ᵉ à moins de "
               f"{pct(TOLERANCE_INDULGENTE, 0)} du 1ᵉʳ) : F1 macro "
               f"{fr(indulgente['f1'])}, soit {ecart_signe(indulgente['f1'] - evaluation['f1'])} "
               f"et {len(indulgente['repeches'])} exemples repêchés sur "
               f"{evaluation['total'] - evaluation['corrects']} erreurs. Elle ne remplace "
               "pas l'évaluation stricte, elle dit seulement quelle part des erreurs sont "
               "des quasi-égalités.", ""])


def section_confusion(matrice, types, evaluation):
    """Section 3 : la matrice de confusion. Retourne des lignes."""
    entete = ["attendu \\ prédit"] + [t.replace("r_", "") for t in types]
    corps = []
    for attendu in types:
        ligne = [f"`{attendu}`"]
        for predit in types:
            valeur = matrice[attendu][predit]
            if not valeur:
                ligne.append("·")
            elif attendu == predit:
                ligne.append(f"**{valeur}**")
            else:
                ligne.append(str(valeur))
        corps.append(ligne)
    lignes = ["## 3. Matrice de confusion", "",
              "Lignes : type attendu. Colonnes : type prédit. La diagonale en gras est "
              "le nombre de bonnes réponses, sur 30 par type. Le préfixe `r_` est retiré "
              "des en-têtes de colonnes pour la lisibilité.", ""]
    lignes += tableau(entete, corps)
    lignes += ["", "### 3.1 Confusions les plus fréquentes", ""]
    corps = []
    for attendu, predit, nombre in confusions_frequentes(matrice, types, 10):
        corps.append([f"`{attendu}`", f"`{predit}`", nombre, pct(nombre / 30, 0)])
    lignes += tableau(["attendu", "prédit à la place", "cas", "part du type"], corps)
    aimants = sorted(types, key=lambda t: -evaluation["par_type"][t]["predits"])
    lignes += ["",
               "Les types les plus souvent proposés, tous attendus confondus : "
               + ", ".join(f"`{t}` ({evaluation['par_type'][t]['predits']})"
                           for t in aimants[:3])
               + f". Un type qui reçoit nettement plus de 30 prédictions est un aimant : "
               "il attire des exemples qui ne lui appartiennent pas.", ""]
    return lignes


def section_experience_1(resultats):
    """Section 4 : Expérience 1, apport de chaque trait. Retourne des lignes."""
    corps = []
    for nom in ("H", "H+SST", "H+TRT", "H+TRT+SST"):
        resultat = resultats[nom]
        evaluation = resultat["evaluation"]
        article = ARTICLE_TRAITS[nom]
        corps.append([f"**{nom}**", resultat["n_regles"],
                      fr(100 * evaluation["precision"], 1),
                      fr(100 * evaluation["rappel"], 1),
                      f"**{fr(evaluation['f1'])}**", fr(article, 3),
                      ecart_signe(evaluation["f1"] - article)])
    base = resultats["H"]["evaluation"]["f1"]
    complet = resultats["H+TRT+SST"]["evaluation"]["f1"]
    return (["## 4. Expérience 1 — apport de chaque trait (Tableau 2)", "",
             "Chaque configuration est un **pipeline complet** : signatures filtrées sur "
             "les traits retenus, règles réapprises au même seuil et avec la même "
             "stratégie, puis classification. Les règles diffèrent donc d'une "
             "configuration à l'autre, ce qui est le point de l'expérience.", ""]
            + tableau(["configuration", "règles", "P (%)", "R (%)", "F1", "F1 article",
                       "écart"], corps)
            + ["",
               f"Chez nous, passer de H seul à la configuration complète fait gagner "
               f"{ecart_signe(complet - base)} ; l'article gagne "
               f"{ecart_signe(ARTICLE_TRAITS['H+TRT+SST'] - ARTICLE_TRAITS['H'])}.", ""])


def section_experience_2(resultats):
    """Section 5 : Expérience 2, définitude. Retourne des lignes."""
    noms = ("H+TRT+SST", "H+TRT+SST sans morpho", "H+TRT+SST+DEF",
            "H+TRT+SST sans morpho +DEF")
    corps = []
    for nom in noms:
        resultat = resultats[nom]
        evaluation = resultat["evaluation"]
        corps.append([f"**{nom}**", resultat["n_regles"],
                      fr(100 * evaluation["precision"], 1),
                      fr(100 * evaluation["rappel"], 1),
                      f"**{fr(evaluation['f1'])}**"])
    reference = resultats["H+TRT+SST"]["evaluation"]["f1"]
    avec_def = resultats["H+TRT+SST+DEF"]["evaluation"]["f1"]
    sans_morpho = resultats["H+TRT+SST sans morpho"]["evaluation"]["f1"]
    notre_trait = resultats["H+TRT+SST sans morpho +DEF"]["evaluation"]["f1"]

    lignes = ["## 5. Expérience 2 — trait de définitude (Tableau 4)", "",
              "Deux symboles sont ajoutés à la signature du terme B : `DEF:Det` ou "
              "`DEF:NoDet`, et `DEF:Def` ou `DEF:NoDef`. Ils dépendent de la **ligne** et "
              "non du terme — « photo de famille » et « photo d'une famille » partagent "
              "le terme B mais pas le déterminant, et c'est justement ce qui les "
              "distingue.", "",
              "**Mesure ajoutée, absente de l'article.** JeuxDeMots porte déjà des "
              "annotations `DET` et `NODET` dans le trait SST. Les garder revient à "
              "compter deux fois la même information. Les quatre lignes isolent ce que "
              "chaque source apporte vraiment.", ""]
    lignes += tableau(["configuration", "règles", "P (%)", "R (%)", "F1"], corps)
    lignes += ["",
               f"- Le trait de définitude ajouté aux annotations de JDM : "
               f"{ecart_signe(avec_def - reference)} (l'article gagne "
               f"{ecart_signe(ARTICLE_DEFINITUDE['H+TRT+SST+DEF'] - ARTICLE_DEFINITUDE['H+TRT+SST'])}).",
               f"- Retirer les annotations morphologiques de JDM, sans rien ajouter : "
               f"{ecart_signe(sans_morpho - reference)}.",
               f"- Notre trait seul, les annotations de JDM retirées : "
               f"{ecart_signe(notre_trait - sans_morpho)} par rapport à la ligne sans "
               "morpho.", ""]
    return lignes


def section_experience_3(trim, no_trim):
    """Section 6 : Expérience 3, élagage. Retourne des lignes."""
    corps = []
    for nom, resultat in (("Trim", trim), ("No Trim", no_trim)):
        evaluation = resultat["evaluation"]
        p_art, r_art, f1_art, r_nb, t_art = ARTICLE_ELAGAGE[nom]
        corps.append([f"**{nom}**",
                      fr(100 * evaluation["precision"], 1),
                      fr(100 * evaluation["rappel"], 1),
                      f"**{fr(evaluation['f1'])}**",
                      resultat["n_regles"], fr(resultat["duree"], 2),
                      fr(f1_art, 3), r_nb, fr(t_art, 2)])
    gain_temps = no_trim["duree"] / trim["duree"] if trim["duree"] else 0.0
    perte = no_trim["evaluation"]["f1"] - trim["evaluation"]["f1"]
    return (["## 6. Expérience 3 — élagage des règles (Tableau 5)", "",
             "**No Trim** : toutes les règles ayant existé pendant l'apprentissage, "
             "intermédiaires absorbées comprises. **Trim** : seulement celles qui n'ont "
             "pas servi d'entrée à une fusion, c'est-à-dire les règles fusionnées "
             "finales et les orphelines. Le temps est mesuré sur les 450 instances de "
             "test, mesure de similarité identique.", ""]
            + tableau(["configuration", "P (%)", "R (%)", "F1", "règles", "temps (s)",
                       "F1 article", "règles article", "temps article (s)"], corps)
            + ["",
               f"Chez nous, l'élagage divise le temps par {fr(gain_temps, 1)} et "
               + ("y gagne même " if perte < 0 else "coûte ")
               + f"{fr(abs(perte))} de F1"
               + (" : garder les règles intermédiaires ne sert à rien, elles ne font "
                  "qu'ajouter des concurrentes moins bonnes que la règle qui les a "
                  "absorbées." if perte < 0 else ".")
               + " L'article rapporte un facteur "
               f"{fr(ARTICLE_ELAGAGE['No Trim'][4] / ARTICLE_ELAGAGE['Trim'][4], 1)} "
               f"pour {fr(abs(ARTICLE_ELAGAGE['No Trim'][2] - ARTICLE_ELAGAGE['Trim'][2]))} "
               "de F1.", "",
               "Les nombres absolus de règles ne sont pas comparables à ceux de "
               "l'article : ils dépendent du nombre de fusions, donc du corpus et de la "
               "représentation. C'est le rapport temps/qualité qui se compare.", ""])


def section_echecs(echecs, exclusives, non_exclusives, total):
    """Section 7 : analyse des cas d'échec. Retourne des lignes."""
    lignes = ["## 7. Analyse des cas d'échec (section 4.5)", "",
              f"{len(echecs)} erreurs sur {total} exemples. Chaque erreur reçoit une "
              "cause unique, par ordre de priorité du plus spécifique au plus général :",
              "",
              "`" + "` → `".join(PRIORITE_CAUSES) + "`", "",
              "La polysémie passe en dernier parce qu'elle est très répandue — 61 % des "
              "termes du corpus ont au moins un raffinement dans JDM — et absorberait "
              "tout le reste si elle venait en tête.", ""]
    corps = []
    for cause in PRIORITE_CAUSES:
        exclusif = exclusives.get(cause, 0)
        toutes = non_exclusives.get(cause, 0)
        corps.append([cause, exclusif, pct(exclusif / len(echecs)) if echecs else "—",
                      toutes])
    lignes += tableau(["cause", "attribution exclusive", "part des erreurs",
                       "présence (non exclusive)"], corps)
    lignes += ["",
               "La dernière colonne compte toutes les erreurs où la cause est présente, "
               "sans exclusivité : leur somme dépasse le nombre d'erreurs, puisqu'une "
               "même erreur cumule souvent plusieurs faiblesses.", "",
               "**Comment chaque cause est détectée.** Ce sont des indices mesurables, "
               "pas un jugement manuel :", "",
               f"- *défaut de connaissance* — la signature de A ou de B compte moins de "
               f"{SIGNATURE_PAUVRE} symboles ;",
               "- *dispersion morphologique* — le diagnostic de la collecte montre que le "
               "singulier du terme existe dans JDM et porte des hyperonymes, alors que la "
               "forme du corpus n'en a pas ;",
               f"- *classe multiple* — le type attendu est à moins de "
               f"{pct(TOLERANCE_INDULGENTE, 0)} du type gagnant : la prédiction est "
               "défendable ;",
               "- *polysémie* — A ou B a au moins deux raffinements de sens dans JDM, donc "
               "sa signature mélange plusieurs sens. C'est un **indice**, pas une preuve "
               "que la confusion vient de là.", ""]

    lignes += ["### 7.1 Dix erreurs instructives", ""]
    interessants = sorted(echecs, key=lambda e: (-e["score"], e["syntagme"]))[:10]
    corps = []
    for echec in interessants:
        corps.append([f"« {echec['syntagme']} »", f"`{echec['attendu']}`",
                      f"`{echec['predit']}`", fr(echec["score"]),
                      fr(echec["score_attendu"]),
                      f"{echec['regle']['poids']}",
                      echec["cause"]])
    lignes += tableau(["syntagme", "attendu", "prédit", "score gagnant",
                       "score du bon type", "poids de la règle", "cause"], corps)
    lignes += ["",
               "Ce sont les erreurs les plus **confiantes** : le système s'est trompé avec "
               "un score élevé. Ce sont celles qui coûtent le plus cher, et celles qui "
               "renseignent le mieux sur ce qui manque à la base de connaissances.", ""]
    return lignes


def section_tracabilite(trace, evaluation):
    """Section 8 : qui gagne sur le test. Retourne des lignes."""
    return (["## 8. Traçabilité des règles gagnantes sur le test", "",
             "Même mesure qu'à l'étape 5, cette fois sur les 450 exemples de test.", ""]
            + tableau(["mesure", "valeur"], [
                ["règles du modèle", trace["regles"]],
                ["dont orphelines / fusionnées",
                 f"{trace['n_orphelines']} / {trace['n_fusionnees']}"],
                ["prédictions gagnées par une orpheline",
                 pct(trace["part_victoires_orphelines"])],
                ["prédictions gagnées par une fusionnée",
                 pct(trace["part_victoires_fusionnees"])],
                ["part des orphelines qui gagnent au moins une fois",
                 pct(trace["taux_gagnantes_orphelines"])],
                ["part des fusionnées qui gagnent au moins une fois",
                 pct(trace["taux_gagnantes_fusionnees"])],
                ["rapport des deux taux", f"{fr(trace['rapport_taux'], 2)}×"],
                ["règles distinctes ayant gagné", trace["regles_distinctes_gagnantes"]],
                ["exemples d'entraînement absorbés par des règles qui ne gagnent jamais",
                 trace["exemples_gaspilles_fusion"]],
                ["score gagnant moyen", fr(trace["score_gagnant_moyen"])],
                ["score moyen des règles du bon type", fr(trace["score_moyen_bon_type"])],
            ])
            + ["",
               f"Un rapport supérieur à 1 signifie qu'une règle fusionnée a plus de "
               f"chances de gagner qu'une orpheline. Avec {trace['regles']} règles pour "
               f"{evaluation['total']} exemples de test, au plus {evaluation['total']} "
               "règles peuvent gagner : le compte brut de règles perdantes mesure surtout "
               "la taille du jeu, c'est le rapport qui informe.", ""])


def construire_rapport(sections):
    """Assemble reports/rapport_evaluation.md. Ne retourne rien."""
    lignes = ["# Évaluation sur le split test", "",
              "Étape 6 : première et unique lecture des 450 exemples de test, avec les "
              "paramètres figés à l'étape 5. Les trois expériences de l'article suivent, "
              "chacune en regard des valeurs publiées.", ""]
    for section in sections:
        lignes += section
    CHEMIN_RAPPORT.parent.mkdir(parents=True, exist_ok=True)
    CHEMIN_RAPPORT.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    print(f"Rapport écrit : {CHEMIN_RAPPORT}", flush=True)


# ---------------------------------------------------------------------------
# Enchaînement d'une configuration complète
# ---------------------------------------------------------------------------

def pipeline(nom, collecte, termes, lignes_train, lignes_test, types, traits,
             sans_morpho=False, avec_definitude=False):
    """Signatures, réapprentissage, classification pour une configuration.
    Retourne un dict."""
    signatures = construire_signatures(collecte, termes, traits, sans_morpho)
    finales, historique = apprendre_configuration(lignes_train, signatures,
                                                  avec_definitude)
    predictions, duree = classer_tout(lignes_test, finales, signatures, avec_definitude)
    evaluation = evaluer(predictions, types)
    print(f"  {nom:28s} {len(finales):4d} règles, F1 macro {fr(evaluation['f1'])}",
          flush=True)
    return {"nom": nom, "signatures": signatures, "regles": finales,
            "historique": historique, "predictions": predictions,
            "evaluation": evaluation, "duree": duree, "n_regles": len(finales)}


def main():
    modele_regles, modele = charger_modele_final()
    collecte = sig.charger_collecte()
    corpus, _ = sig.charger_corpus()
    termes = sig.termes_du_corpus(corpus)
    lignes_train = charger_lignes("train")
    lignes_test_par_type = charger_lignes("test")
    lignes_test = aplatir(lignes_test_par_type)
    types = sorted(lignes_test_par_type)
    print(f"Test ouvert : {len(lignes_test)} exemples sur {len(types)} types.", flush=True)

    # --- Évaluation principale, avec le modèle figé ---
    signatures = construire_signatures(collecte, termes, {"H", "TRT", "SST"})
    predictions, _ = classer_tout(lignes_test, modele_regles, signatures, False)
    evaluation = evaluer(predictions, types)
    indulgente = evaluation_indulgente(predictions, types)
    print(f"Évaluation principale : F1 macro {fr(evaluation['f1'])}, "
          f"exactitude {pct(evaluation['exactitude'])} "
          f"(indulgente {fr(indulgente['f1'])}).", flush=True)

    matrice = matrice_confusion(predictions, types)
    ecrire_matrice(matrice, types)
    ecrire_predictions(predictions, evaluation, indulgente, modele)

    indices = indices_de_cause(collecte, signatures)
    echecs, exclusives, non_exclusives = analyser_echecs(predictions, indices)
    trace = tracer(predictions, modele_regles)

    # --- Expérience 1 ---
    print("Expérience 1 — apport de chaque trait", flush=True)
    exp1 = {}
    for nom, traits in (("H", {"H"}), ("H+SST", {"H", "SST"}),
                        ("H+TRT", {"H", "TRT"}), ("H+TRT+SST", {"H", "TRT", "SST"})):
        exp1[nom] = pipeline(nom, collecte, termes, lignes_train, lignes_test, types,
                             traits)

    # --- Expérience 2 ---
    print("Expérience 2 — définitude", flush=True)
    exp2 = {"H+TRT+SST": exp1["H+TRT+SST"]}
    exp2["H+TRT+SST sans morpho"] = pipeline(
        "H+TRT+SST sans morpho", collecte, termes, lignes_train, lignes_test, types,
        {"H", "TRT", "SST"}, sans_morpho=True)
    exp2["H+TRT+SST+DEF"] = pipeline(
        "H+TRT+SST+DEF", collecte, termes, lignes_train, lignes_test, types,
        {"H", "TRT", "SST"}, avec_definitude=True)
    exp2["H+TRT+SST sans morpho +DEF"] = pipeline(
        "H+TRT+SST sans morpho +DEF", collecte, termes, lignes_train, lignes_test, types,
        {"H", "TRT", "SST"}, sans_morpho=True, avec_definitude=True)

    # --- Expérience 3 : le même apprentissage, deux ensembles de règles ---
    print("Expérience 3 — élagage", flush=True)
    complet = exp1["H+TRT+SST"]
    trim = {"n_regles": len(complet["regles"]), "duree": complet["duree"],
            "evaluation": complet["evaluation"]}
    predictions_no_trim, duree_no_trim = classer_tout(
        lignes_test, complet["historique"], complet["signatures"], False)
    no_trim = {"n_regles": len(complet["historique"]), "duree": duree_no_trim,
               "evaluation": evaluer(predictions_no_trim, types)}
    print(f"  Trim    {trim['n_regles']:5d} règles, {fr(trim['duree'], 2)} s, "
          f"F1 {fr(trim['evaluation']['f1'])}", flush=True)
    print(f"  No Trim {no_trim['n_regles']:5d} règles, {fr(no_trim['duree'], 2)} s, "
          f"F1 {fr(no_trim['evaluation']['f1'])}", flush=True)

    construire_rapport([
        section_parametres(modele, lignes_test),
        section_principale(evaluation, indulgente, predictions),
        section_confusion(matrice, types, evaluation),
        section_experience_1(exp1),
        section_experience_2(exp2),
        section_experience_3(trim, no_trim),
        section_echecs(echecs, exclusives, non_exclusives, len(predictions)),
        section_tracabilite(trace, evaluation),
    ])


if __name__ == "__main__":
    main()
