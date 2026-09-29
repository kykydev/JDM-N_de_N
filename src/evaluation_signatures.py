#!/usr/bin/env python3
"""Évaluation finale des signatures retenues en validation croisée.

Méthode figée (somme · arbre · descente) ; signatures de config.SIGNATURES_RETENUES :
20 hyperonymes, poids issus de la collecte, terme lui-même absent, TRT et SST actuels.

Deux temps, pour que le test ne soit lu qu'UNE fois :

  1. `python3 src/evaluation_signatures.py` réapprend les quinze arbres sur les 750
     exemples d'entraînement, classe les 450 exemples de test, enregistre les
     prédictions complètes puis écrit le rapport ;
  2. `python3 src/evaluation_signatures.py --rapport-seulement` reconstruit le rapport
     depuis ces prédictions, sans relire le test.

Les statistiques tirées des données (ici, les seules qui existent : aucune pondération
idf, aucun centile) ne portent que sur les termes d'entraînement.

Le F1 de test de la configuration actuelle est REPRIS tel quel de
data/resultats/predictions_finales.json : il n'est pas recalculé.

Aucun appel réseau, data/signatures/ n'est pas touché.

Usage : python3 src/evaluation_signatures.py [--rapport-seulement]
"""

import argparse
import csv
import json
import math
import statistics
import time
from datetime import datetime, timezone

import classify
import config
import evaluation_finale as ef
import grasp
import signatures as sig
import variantes_signatures as vs


# ---------------------------------------------------------------------------
# Temps 1 : apprendre, classer le test, enregistrer
# ---------------------------------------------------------------------------

def signatures_du_test(termes_train, lignes_test):
    """Signatures de tous les termes de l'entraînement et du test, en mémoire.
    Retourne terme -> (symbole -> poids).

    Les poids ne dépendent que du terme et de la configuration ; les statistiques, s'il y
    en avait, seraient prises sur `termes_train`."""
    collecte = sig.charger_collecte()
    termes_test = vs.termes_des_lignes(lignes_test)
    for terme in termes_test - set(vs.DONNEES["bases"]):
        vs.DONNEES["bases"][terme] = vs.base_du_terme(collecte.get(terme))
    cle = vs.cle_de(config.SIGNATURES_RETENUES)
    return vs.signatures_ponderees(termes_train | termes_test, termes_train, cle)


def apprendre_et_classer(lignes_train, lignes_test, signatures):
    """Réapprend les arbres sur le train, classe le test. Retourne (prédictions, durée)."""
    noeuds, racines, _ = grasp.construire_foret(
        vs.feuilles_ponderees(lignes_train, signatures), "somme")
    debut = time.perf_counter()
    predictions = []
    for relation in sorted(lignes_test):
        for ligne in lignes_test[relation]:
            resultat = classify.classer_par_descente(
                signatures[ligne["A"]], signatures[ligne["B"]], noeuds, racines)
            predictions.append(classify.prediction_descente(ligne, resultat, noeuds))
    return predictions, time.perf_counter() - debut


def ecrire_predictions(predictions, evaluation, duree):
    """Écrit data/resultats/predictions_finales_jdm.json. Retourne le chemin."""
    charge = {
        "split": "test (450 exemples, 30 par type), lu une seule fois",
        "signatures": config.SIGNATURES_RETENUES,
        "genere_le": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "duree_classement": duree,
        "macro_stricte": {k: evaluation[k] for k in
                          ("precision", "rappel", "f1", "exactitude")},
        "predictions": predictions,
    }
    config.FICHIER_PREDICTIONS_SIGNATURES.parent.mkdir(parents=True, exist_ok=True)
    with open(config.FICHIER_PREDICTIONS_SIGNATURES, "w", encoding="utf-8", newline="") as f:
        json.dump(charge, f, ensure_ascii=False, indent=1)
        f.write("\n")
    return config.FICHIER_PREDICTIONS_SIGNATURES


def lire_predictions(chemin):
    """Relit des prédictions enregistrées. Retourne (prédictions, durée)."""
    charge = json.loads(chemin.read_text(encoding="utf-8"))
    return charge["predictions"], charge["duree_classement"]


def ecrire_matrice(matrice, types):
    """Écrit la matrice de confusion en CSV. Retourne le chemin."""
    with open(config.FICHIER_MATRICE_SIGNATURES, "w", encoding="utf-8", newline="") as f:
        redacteur = csv.writer(f, lineterminator="\n")
        redacteur.writerow(["attendu \\ prédit"] + list(types))
        for attendu in types:
            redacteur.writerow([attendu] + [matrice[attendu][p] for p in types])
    return config.FICHIER_MATRICE_SIGNATURES


# ---------------------------------------------------------------------------
# Comparaison des deux jeux de signatures
# ---------------------------------------------------------------------------

def par_syntagme(predictions):
    """Indexe des prédictions par syntagme. Retourne syntagme -> prédiction."""
    return {p["syntagme"]: p for p in predictions}


def changements(actuelles, nouvelles):
    """Exemples dont la justesse change d'une configuration à l'autre. Retourne un dict."""
    ancien = par_syntagme(actuelles)
    corriges, casses, autre_type = [], [], []
    for p in nouvelles:
        a = ancien[p["syntagme"]]
        if p["correct"] and not a["correct"]:
            corriges.append(p)
        elif a["correct"] and not p["correct"]:
            casses.append(p)
        elif not p["correct"] and p["predit"] != a["predit"]:
            autre_type.append(p)
    return {"corriges": corriges, "casses": casses, "autre_type": autre_type}


def p_test_des_signes(corriges, casses):
    """Probabilité, sous l'hypothèse d'un simple hasard, d'un déséquilibre au moins aussi
    grand entre exemples corrigés et cassés (test des signes exact, bilatéral).
    Retourne un flottant.

    Seuls les exemples dont la justesse change informent : sous l'hypothèse nulle, chacun
    penche d'un côté ou de l'autre avec une probabilité de 1/2."""
    total = corriges + casses
    extreme = max(corriges, casses)
    queue = sum(math.comb(total, k) for k in range(extreme, total + 1)) / 2 ** total
    return min(1.0, 2 * queue)


# ---------------------------------------------------------------------------
# Mise en forme
# ---------------------------------------------------------------------------

fr, pct, tableau, ecart_signe = grasp.fr, grasp.pct, grasp.tableau, classify.ecart_signe


def section_dispositif(n_test, duree):
    """1 : configuration et protocole. Retourne des lignes."""
    r = config.SIGNATURES_RETENUES
    return ["# Évaluation finale des signatures retenues", "",
            "## 1. Configuration et protocole", "",
            "- **Méthode figée** : somme · arbre · descente, inchangée.",
            f"- **Signatures** : {r['h']} hyperonymes, pondération `{r['pond']}` (poids de la "
            f"collecte normalisés par terme et par trait), traitement du terme `{r['terme']}` "
            f"(absent), TRT `{r['trt']}`, SST `{r['sst']}`. Choisies en validation croisée : "
            "`rapport_signatures_variantes.md`.",
            "- **Apprentissage** : quinze arbres réappris sur les 750 exemples "
            "d'entraînement.",
            f"- **Test** : {n_test} exemples, 30 par type, **lus une seule fois**. "
            f"Classement en {fr(duree, 2)} s. Ce rapport se reconstruit depuis "
            f"`{config.FICHIER_PREDICTIONS_SIGNATURES.relative_to(config.RACINE).as_posix()}` "
            "sans relire le test.",
            "- **Configuration actuelle** : son F1 de test est **repris tel quel** de "
            "`rapport_final.md` (`data/resultats/predictions_finales.json`), pas recalculé.",
            ""]


def section_resultats(nouvelle, actuelle, validation):
    """2 : macro et F1 par type, côte à côte. Retourne des lignes."""
    f1_n, f1_a = nouvelle["f1"], actuelle["f1"]
    lignes = ["## 2. Résultats", "",
              f"**F1 macro : {fr(f1_n)}** (précision {fr(nouvelle['precision'])}, rappel "
              f"{fr(nouvelle['rappel'])}, exactitude {pct(nouvelle['exactitude'])}, "
              f"{nouvelle['corrects']} exemples justes sur {nouvelle['total']}).", ""]
    lignes += tableau(
        ["", "F1 test", "exactitude", "F1 validation croisée (15 mesures)"],
        [["**signatures retenues (jdm, T2)**", f"**{fr(f1_n)}**", pct(nouvelle["exactitude"]),
          validation["retenue"]],
         ["signatures actuelles (binaire, T0)", fr(f1_a), pct(actuelle["exactitude"]),
          validation["actuelle"]],
         ["article", fr(classify.ARTICLE_F1), "—", "—"],
         ["méthode à seuil", fr(classify.ANCIEN_F1), "60,0 %", "—"],
         ["plus proche voisin", fr(ef.F1_VOISIN), "—", "—"]])
    lignes += ["", f"Écart entre les deux jeux de signatures : "
                   f"**{ecart_signe(f1_n - f1_a)}** de F1 sur le test ; la validation "
                   f"croisée annonçait {validation['gain']}.", ""]
    corps = []
    for rt in sorted(nouvelle["par_type"], key=lambda t: -nouvelle["par_type"][t]["f1"]):
        n, a = nouvelle["par_type"][rt], actuelle["par_type"][rt]
        article = classify.ARTICLE_PAR_TYPE[rt][2]
        corps.append([f"`{rt}`", n["predits"], fr(100 * n["precision"], 1),
                      fr(100 * n["rappel"], 1), f"**{fr(n['f1'], 2)}**", fr(a["f1"], 2),
                      ecart_signe(n["f1"] - a["f1"], 2), fr(article, 2),
                      ecart_signe(n["f1"] - article, 2)])
    corps.append(["**macro**", "", fr(100 * nouvelle["precision"], 1),
                  fr(100 * nouvelle["rappel"], 1), f"**{fr(f1_n)}**", fr(f1_a),
                  ecart_signe(f1_n - f1_a), fr(classify.ARTICLE_F1),
                  ecart_signe(f1_n - classify.ARTICLE_F1)])
    lignes += ["### 2.1 Détail par type", "",
               "Trié par F1 de la nouvelle configuration. « actuelles » : F1 de test de la "
               "configuration précédente, repris de `rapport_final.md`.", ""]
    lignes += tableau(["type", "prédits", "P (%)", "R (%)", "F1", "F1 actuelles",
                       "écart", "F1 article", "écart article"], corps)
    meilleurs = sum(1 for rt, d in nouvelle["par_type"].items()
                    if d["f1"] > actuelle["par_type"][rt]["f1"])
    au_dessus = sum(1 for rt, d in nouvelle["par_type"].items()
                    if d["f1"] > classify.ARTICLE_PAR_TYPE[rt][2])
    lignes += ["", f"Le F1 progresse pour {meilleurs} types sur {len(nouvelle['par_type'])} "
                   f"par rapport aux signatures actuelles, et dépasse celui de l'article "
                   f"pour {au_dessus} types.", ""]
    return lignes


def section_confusion(matrice, types):
    """3 : matrice de confusion. Retourne des lignes."""
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
             f"Aussi écrite dans `{config.FICHIER_MATRICE_SIGNATURES.relative_to(config.RACINE).as_posix()}`.",
             ""]
            + tableau(entete, corps)
            + ["", "Confusions les plus fréquentes : "
               + ", ".join(f"`{a}` → `{p}` ({n})" for a, p, n in couples[:6]) + ".", ""])


def section_changements(actuelles, nouvelles, tailles):
    """4 : ce qui change exemple par exemple, et la descente. Retourne des lignes."""
    diff = changements(actuelles, nouvelles)
    stats_n = ef.statistiques_descente(nouvelles, tailles)
    stats_a = ef.statistiques_descente(actuelles, tailles)
    n = len(nouvelles)
    corps = [
        ["part des prédictions faites par une racine",
         pct(stats_a["natures"].get("racine", 0) / n),
         pct(stats_n["natures"].get("racine", 0) / n)],
        ["profondeur d'arrêt moyenne (racine = 0)", fr(stats_a["profondeur_moyenne"], 2),
         fr(stats_n["profondeur_moyenne"], 2)],
        ["nœuds gagnants internes hors racine", stats_a["natures"].get("nœud interne", 0),
         stats_n["natures"].get("nœud interne", 0)],
        ["prédictions faites par une feuille", stats_a["natures"].get("feuille", 0),
         stats_n["natures"].get("feuille", 0)],
        ["poids relatif moyen du nœud gagnant", fr(stats_a["poids_relatif"], 2),
         fr(stats_n["poids_relatif"], 2)],
        ["calculs de score par exemple", fr(stats_a["calculs"], 1), fr(stats_n["calculs"], 1)]]
    lignes = ["## 4. Ce qui change", "",
              f"Sur {n} exemples : **{len(diff['corriges'])} corrigés** (faux avant, justes "
              f"maintenant), **{len(diff['casses'])} cassés** (justes avant, faux "
              f"maintenant), {len(diff['autre_type'])} restent faux mais avec un autre type. "
              f"Solde net : {ecart_signe(len(diff['corriges']) - len(diff['casses']), 0)}.",
              ""]
    lignes += tableau(["descente", "signatures actuelles", "signatures retenues"], corps)
    for titre, cle in (("Exemples corrigés", "corriges"), ("Exemples cassés", "casses")):
        lot = sorted(diff[cle], key=lambda p: p["syntagme"])[:ef.EXEMPLES_PAR_TYPE * 3]
        lignes += ["", f"**{titre}** (les {len(lot)} premiers par ordre alphabétique) : "
                   + " ; ".join(f"« {p['syntagme']} » (`{p['attendu']}`)" for p in lot)]
    return lignes + [""]


def section_lecture(nouvelle, actuelle, validation_brute, diff):
    """5 : lecture honnête. Retourne des lignes."""
    ecart = nouvelle["f1"] - actuelle["f1"]
    corriges, casses = len(diff["corriges"]), len(diff["casses"])
    p_signes = p_test_des_signes(corriges, casses)
    gain_cv, ecart_cv = validation_brute["gain"], validation_brute["ecart"]
    lignes = ["## 5. Lecture", ""]
    if ecart <= 0:
        lignes.append(f"- **Aucun gain sur le test** : {ecart_signe(ecart)} de F1. La "
                      "validation croisée annonçait un gain qui ne se retrouve pas.")
    elif ecart < ecart_cv:
        lignes.append(f"- Le gain sur le test, {ecart_signe(ecart)}, est **plus petit que "
                      f"l'écart-type** ({fr(ecart_cv)}) des différences appariées de la validation "
                      f"croisée : il n'est pas distinguable du bruit.")
    else:
        lignes.append(f"- Le gain sur le test, {ecart_signe(ecart)}, dépasse l'écart-type "
                      f"({fr(ecart_cv)}) des différences appariées de la validation croisée.")
    lignes += [f"- La validation croisée annonçait {fr(gain_cv)} de gain moyen : le test "
               f"donne {fr(ecart)}. " + (
                   "Il est dans le même sens et du même ordre de grandeur."
                   if ecart >= 0.5 * gain_cv else
                   "Il est dans le même sens mais plus petit." if ecart > 0 else
                   "Le gain ne se retrouve pas."),
               f"- **Test des signes sur les exemples dont la justesse change** : "
               f"{corriges} corrigés contre {casses} cassés, soit {corriges + casses} "
               f"exemples discordants sur {nouvelle['total']}. Probabilité d'un "
               f"déséquilibre au moins aussi grand sous un simple hasard : "
               f"**{fr(p_signes, 2)}**. "
               + ("Le gain n'est pas établi au sens statistique usuel (seuil de 0,05) : il "
                  "va dans le sens de la validation croisée sans le prouver."
                  if p_signes >= 0.05 else
                  "Le gain est établi au seuil de 0,05."),
               "- Un écart de 0,01 de F1 sur 450 exemples tient à quelques exemples ; le "
               "F1 de test de chaque configuration est lui-même une estimation, sans "
               "intervalle ici.", ""]
    return lignes


def validation_croisee():
    """F1 de validation croisée des deux configurations, relus du cache. Retourne un dict."""
    cache = vs.charger_cache()
    retenue = vs.cle_de(config.SIGNATURES_RETENUES)
    actuelle = vs.cle_de(config.REFERENCE_VARIANTES)
    moyenne, ecart = vs.moyenne_et_ecart(vs.differences(retenue, actuelle, cache))
    return {"retenue": vs.f1_moyen(retenue, cache), "actuelle": vs.f1_moyen(actuelle, cache),
            "gain": moyenne, "ecart": ecart}


def construire_rapport(nouvelles, duree):
    """Écrit reports/rapport_final_signatures.md. Retourne le dict des mesures."""
    actuelles, _ = lire_predictions(config.FICHIER_PREDICTIONS_FINALES)
    types = sorted({p["attendu"] for p in nouvelles})
    nouvelle = classify.evaluer(nouvelles, types)
    actuelle = classify.evaluer(actuelles, types)
    matrice = classify.matrice_confusion(nouvelles, types)
    ecrire_matrice(matrice, types)
    brute = validation_croisee()
    validation = {"retenue": brute["retenue"], "actuelle": brute["actuelle"],
                  "gain": f"{ecart_signe(brute['gain'])} ± {fr(brute['ecart'])}"}
    brute_pour_lecture = {"gain": brute["gain"], "ecart": brute["ecart"]}
    noeuds, _ = grasp.charger_arbres()
    tailles = classify.tailles_des_types(noeuds)

    lignes = section_dispositif(len(nouvelles), duree)
    lignes += section_resultats(nouvelle, actuelle, validation)
    lignes += section_confusion(matrice, types)
    lignes += section_changements(actuelles, nouvelles, tailles)
    lignes += section_lecture(nouvelle, actuelle, brute_pour_lecture,
                              changements(actuelles, nouvelles))
    config.FICHIER_RAPPORT_SIGNATURES.write_text("\n".join(lignes), encoding="utf-8")
    print(f"Rapport : {config.FICHIER_RAPPORT_SIGNATURES}", flush=True)
    return {"nouvelle": nouvelle, "actuelle": actuelle}


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
        predictions, duree = lire_predictions(config.FICHIER_PREDICTIONS_SIGNATURES)
        print(f"Prédictions relues : {len(predictions)}. Test non lu.", flush=True)
    else:
        vs.preparer_donnees()
        lignes_train = vs.DONNEES["lignes_train"]
        termes_train = vs.DONNEES["termes"]
        lignes_test = grasp.charger_lignes("test")
        print("Signatures retenues, arbres réappris sur 750 exemples. Lecture du test.",
              flush=True)
        signatures = signatures_du_test(termes_train, lignes_test)
        predictions, duree = apprendre_et_classer(lignes_train, lignes_test, signatures)
        types = sorted({p["attendu"] for p in predictions})
        evaluation = classify.evaluer(predictions, types)
        ecrire_predictions(predictions, evaluation, duree)
        print(f"F1 macro {fr(evaluation['f1'])}, exactitude {pct(evaluation['exactitude'])}",
              flush=True)
    mesures = construire_rapport(predictions, duree)
    print(f"Signatures actuelles (reprises) : {fr(mesures['actuelle']['f1'])}", flush=True)


if __name__ == "__main__":
    main()
