#!/usr/bin/env python3
"""Test complémentaire de la pondération par trait : dix graines, test de Wilcoxon.

ÉCLAIRAGE, PAS RÈGLE DE CHOIX. La configuration retenue par le projet reste celle de
l'étape 1 de reports/rapport_signatures_variantes.md — « jdm », les trois traits
pondérés — décidée avant toute lecture du test. Rien ici ne la révise : le §3.1 de ce
rapport garde son incohérence de décision telle quelle, et ce module ne fait que dire
avec quelle confiance on peut la lire.

Deux différences avec variantes_signatures.py :

  - DIX graines au lieu de trois, soit dix découpages complets des 750 exemples ;
  - un test apparié sur la MOYENNE PAR GRAINE, non sur les plis bruts. Les 5 plis d'une
    même graine rebattent les mêmes 750 exemples : les compter comme 15 mesures
    indépendantes surestime la précision, et c'est la réserve que le rapport des
    variantes formulait déjà. Une graine donne un découpage entier, et les dix moyennes
    par graine sont échangeables sous l'hypothèse nulle — ce que le test de Wilcoxon
    demande.

Le test de Wilcoxon est calculé par énumération exacte des 2^n configurations de signes
(n ≤ 10), sans dépendance externe.

La méthode reste figée (somme · arbre · descente) et **le split test n'est pas lu**.

Usage : python3 src/ponderation_traits.py [--rapport-seulement]
"""

import argparse
import itertools
import json
import statistics
import time

import classify
import config
import grasp
import grille
import variantes_signatures as vs


# ---------------------------------------------------------------------------
# Configurations comparées
# ---------------------------------------------------------------------------

def reference():
    """Configuration binaire de référence, à H_TOP et terme T2. Retourne une clé."""
    return vs.variante(vs.cle_de(config.REFERENCE_VARIANTES),
                       terme="T2", pond=config.PONDERATIONS_COMPAREES[0])


def configurations():
    """Les cinq configurations comparées, référence d'abord. Retourne une liste."""
    return [vs.variante(reference(), pond=pond)
            for pond in config.PONDERATIONS_COMPAREES]


# ---------------------------------------------------------------------------
# Mesures : dix graines × cinq plis
# ---------------------------------------------------------------------------

def preparer_plis():
    """Ajoute aux données les découpages des graines de ce test. Ne retourne rien."""
    for graine in config.GRAINES_PONDERATION:
        if graine not in vs.DONNEES["plis"]:
            vs.DONNEES["plis"][graine] = grille.decouper_plis(
                vs.DONNEES["lignes_train"], graine)


def charger_cache():
    """Relit les mesures déjà calculées. Retourne cle_json -> liste de mesures."""
    if not config.FICHIER_MESURES_PONDERATION.exists():
        return {}
    return json.loads(config.FICHIER_MESURES_PONDERATION.read_text(encoding="utf-8"))


def ecrire_cache(cache):
    """Enregistre les mesures. Ne retourne rien."""
    config.DOSSIER_SIGNATURES_VARIANTES.mkdir(parents=True, exist_ok=True)
    with open(config.FICHIER_MESURES_PONDERATION, "w", encoding="utf-8", newline="") as f:
        json.dump(cache, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")


def taches_manquantes(cles, cache):
    """Toutes les (configuration, graine, pli) pas encore mesurées. Retourne une liste."""
    return [(cle, graine, pli) for cle in cles if vs.cle_json(cle) not in cache
            for graine in config.GRAINES_PONDERATION for pli in range(config.GRILLE_PLIS)]


def mesurer(cles, cache, rapport_seulement):
    """Mesure les configurations absentes du cache, en séquentiel. Ne retourne rien.

    Une configuration n'entre au cache que quand toutes ses mesures sont là, rangées par
    (graine, pli) : les moyennes par graine supposent cet ordre."""
    a_faire = taches_manquantes(cles, cache)
    if not a_faire:
        return
    if rapport_seulement:
        raise SystemExit(f"Mesures absentes du cache ({len(a_faire)}) : lancer sans "
                         "--rapport-seulement.")
    attendues = config.GRILLE_PLIS * len(config.GRAINES_PONDERATION)
    debut = time.perf_counter()
    par_cle = {}
    print(f"  {len(a_faire)} mesures à calculer.", flush=True)
    for arguments in a_faire:
        mesure = vs.tache(arguments)
        lot = par_cle.setdefault(mesure["cle"], [])
        lot.append(mesure)
        if len(lot) == attendues:
            cache[mesure["cle"]] = sorted(lot, key=lambda m: (m["graine"], m["pli"]))
            ecrire_cache(cache)
            print(f"  {mesure['cle']:<45s} F1 "
                  f"{grasp.fr(statistics.fmean(m['f1'] for m in lot))}"
                  f"   ({grasp.fr(time.perf_counter() - debut, 0)} s écoulées)", flush=True)


# ---------------------------------------------------------------------------
# Moyennes par graine et test de Wilcoxon
# ---------------------------------------------------------------------------

def f1_par_graine(cle, cache):
    """F1 moyen de chaque graine, dans l'ordre des graines. Retourne une liste."""
    mesures = cache[vs.cle_json(cle)]
    return [statistics.fmean(m["f1"] for m in mesures if m["graine"] == graine)
            for graine in config.GRAINES_PONDERATION]


def rangs_moyens(valeurs):
    """Rangs de 1 à n, moyennés sur les ex aequo. Retourne une liste."""
    ordre = sorted(range(len(valeurs)), key=lambda i: valeurs[i])
    rangs = [0.0] * len(valeurs)
    debut = 0
    while debut < len(ordre):
        fin = debut
        while fin + 1 < len(ordre) and valeurs[ordre[fin + 1]] == valeurs[ordre[debut]]:
            fin += 1
        moyen = (debut + fin) / 2 + 1
        for position in range(debut, fin + 1):
            rangs[ordre[position]] = moyen
        debut = fin + 1
    return rangs


def wilcoxon(differences):
    """Test de Wilcoxon apparié bilatéral, loi exacte par énumération. Retourne un dict.

    Les différences nulles sont écartées, comme le veut la procédure de Wilcoxon ; les
    ex aequo reçoivent des rangs moyens. La valeur p est la probabilité, sous
    l'hypothèse nulle d'une distribution symétrique autour de zéro, d'observer une
    statistique au moins aussi extrême que celle observée."""
    non_nulles = [d for d in differences if d != 0]
    nuls = len(differences) - len(non_nulles)
    if not non_nulles:
        return {"n": 0, "nuls": nuls, "w": 0.0, "p": 1.0, "positives": 0}
    rangs = rangs_moyens([abs(d) for d in non_nulles])
    total = sum(rangs)
    w_plus = sum(rang for d, rang in zip(non_nulles, rangs) if d > 0)
    extreme = max(w_plus, total - w_plus)
    compte = sum(1 for signes in itertools.product((0, 1), repeat=len(rangs))
                 if max(s := sum(r for signe, r in zip(signes, rangs) if signe),
                        total - s) >= extreme - 1e-9)
    return {"n": len(non_nulles), "nuls": nuls, "w": w_plus,
            "p": compte / 2 ** len(rangs),
            "positives": sum(1 for d in non_nulles if d > 0)}


def comparaison(cle, base, cache):
    """Compare une configuration à une autre sur les moyennes par graine.
    Retourne un dict."""
    differences = [a - b for a, b in zip(f1_par_graine(cle, cache),
                                         f1_par_graine(base, cache))]
    moyenne, ecart = vs.moyenne_et_ecart(differences)
    return {"cle": cle, "differences": differences, "moyenne": moyenne, "ecart": ecart,
            "wilcoxon": wilcoxon(differences)}


# ---------------------------------------------------------------------------
# Reproductibilité : les graines communes aux deux études
# ---------------------------------------------------------------------------

def graines_communes():
    """Graines présentes dans les deux études. Retourne un tuple trié."""
    return tuple(sorted(set(config.GRAINES_PONDERATION)
                        & set(config.GRAINES_VARIANTES)))


def reproductibilite(cle, cache, cache_cv):
    """Compare, graine à graine et pli à pli, les F1 recalculés ici à ceux du cache de
    l'étude des variantes. Retourne un dict ou None si la configuration y manque."""
    if vs.cle_json(cle) not in cache_cv:
        return None
    communes = graines_communes()
    ici = {(m["graine"], m["pli"]): m["f1"] for m in cache[vs.cle_json(cle)]
           if m["graine"] in communes}
    ailleurs = {(m["graine"], m["pli"]): m["f1"] for m in cache_cv[vs.cle_json(cle)]
                if m["graine"] in communes}
    partages = sorted(set(ici) & set(ailleurs))
    ecarts = [abs(ici[k] - ailleurs[k]) for k in partages]
    return {"cle": cle, "compares": len(partages),
            "identiques": sum(1 for e in ecarts if e == 0),
            "ecart_max": max(ecarts) if ecarts else 0.0,
            "f1_ici": statistics.fmean(ici[k] for k in partages) if partages else 0.0,
            "f1_ailleurs": (statistics.fmean(ailleurs[k] for k in partages)
                            if partages else 0.0)}


# ---------------------------------------------------------------------------
# Rapport
# ---------------------------------------------------------------------------

fr, pct, tableau = grasp.fr, grasp.pct, grasp.tableau


def valeur_p(p):
    """Valeur p en typographie française, avec un plancher. Retourne une chaîne."""
    return "< 0,001" if p < 0.001 else fr(p, 3)


def section_protocole():
    """Protocole et portée du test. Retourne des lignes."""
    graines = config.GRAINES_PONDERATION
    return ["# Pondération par trait : test complémentaire sur dix graines", "",
            "**Ce rapport est un éclairage, pas une règle de choix.** La configuration "
            "retenue par le projet reste `H 20 · jdm · T2 · TRT tous · SST toutes`, "
            "décidée à l'étape 1 de `rapport_signatures_variantes.md` **avant toute "
            "lecture du test**. Rien ici ne la révise, et l'incohérence de décision "
            "relevée au §3.1 de ce rapport y reste telle quelle : ce qui suit dit "
            "seulement avec quelle confiance on peut la lire.", "",
            "## 1. Protocole", "",
            f"- **{len(graines)} graines** ({graines[0]}–{graines[-1]}) × "
            f"{config.GRILLE_PLIS} plis stratifiés par type, sur les 750 exemples "
            "d'entraînement. **Le test n'est pas lu.**",
            "- **Méthode figée** : somme · arbre · descente, inchangée.",
            "- **L'unité d'analyse est la graine, pas le pli.** Les 5 plis d'une même "
            "graine rebattent les mêmes 750 exemples : les traiter comme autant de "
            "mesures indépendantes surestime la précision, et c'était la réserve "
            "explicite de `rapport_signatures_variantes.md`. On moyenne donc les 5 plis "
            f"d'une graine, ce qui donne {len(graines)} mesures échangeables.",
            "- **Test de Wilcoxon apparié bilatéral**, loi exacte par énumération des "
            "2^n configurations de signes. Différences nulles écartées, rangs moyens sur "
            "les ex aequo. Aucune dépendance externe.",
            "- **Les cinq configurations** se comparent à la même référence binaire "
            f"`{vs.libelle(reference())}`, sur les mêmes découpages.",
            "- **Ce que le test ne fait pas** : il ne corrige pas la multiplicité (quatre "
            "comparaisons à la même référence), et il porte sur les mêmes 750 exemples "
            "que l'étude d'origine. Il réduit l'optimisme du compte en plis, il ne "
            "l'annule pas.", ""]


def section_reproductibilite(reproductions, cache):
    """Ce qui a été recalculé ici, et ce qui vient d'ailleurs. Retourne des lignes."""
    communes = graines_communes()
    corps = []
    for reproduction in reproductions:
        if reproduction is None:
            continue
        corps.append([f"`{reproduction['cle'][1]}`", reproduction["compares"],
                      reproduction["identiques"],
                      fr(reproduction["f1_ailleurs"]), fr(reproduction["f1_ici"]),
                      "0" if reproduction["ecart_max"] == 0
                      else f"{reproduction['ecart_max']:.2e}"])
    tous_identiques = all(r["identiques"] == r["compares"]
                          for r in reproductions if r is not None)
    lignes = ["## 2. Reproductibilité", "",
              "Les mesures de ce rapport ont **toutes** été calculées sur la machine qui "
              "l'écrit (Windows 11, CPython 3.14, `py -3`, en séquentiel). Les mesures de "
              "`mesures_cv.json`, elles, **ne pouvaient pas l'être** : jusqu'au commit "
              "`fd1b94c`, `variantes_signatures.executer()` exigeait "
              "`multiprocessing.get_context(\"fork\")`, absent de Windows — toute "
              "configuration non présente au cache y levait `ValueError`. Les 28 "
              "configurations d'origine ont donc été produites sur une plateforme POSIX "
              "(Linux ou macOS), que le dépôt ne permet pas d'identifier plus "
              "précisément : ni journal d'exécution, ni empreinte d'environnement n'y "
              "sont conservés. Seules les 3 pondérations partielles, ajoutées au commit "
              "`fd1b94c`, l'ont été ici, après l'ajout d'un repli séquentiel.", "",
              f"Le recoupement porte sur les {len(communes)} graines communes aux deux "
              f"études ({', '.join(str(g) for g in communes)}), soit "
              f"{len(communes) * config.GRILLE_PLIS} plis par configuration, comparés "
              "pli à pli.", ""]
    lignes += tableau(["pondération", "plis comparés", "identiques", "F1 ailleurs",
                       "F1 ici", "écart max"], corps)
    if tous_identiques:
        lignes += ["", "**Tous les F1 sont identiques au bit près.** La référence binaire "
                   f"redonne exactement {fr(statistics.fmean(f1_par_graine(reference(), cache)[:len(communes)]))} "
                   "sur ces trois graines, la valeur du rapport des variantes. Le calcul "
                   "ne dépend donc ni de la plateforme, ni du nombre de processus : les "
                   "découpages sont tirés d'un générateur à graine fixe et les parcours "
                   "sont ordonnés. Ce qui venait d'ailleurs est vérifié ici."]
    else:
        lignes += ["", "**Les F1 ne se reproduisent pas tous à l'identique.** Le tableau "
                   "donne l'écart maximal observé ; toute différence non nulle signale "
                   "une dépendance à la plateforme qu'il faudrait élucider avant de lire "
                   "le reste."]
    return lignes + [""]


def section_configurations(resultats, cache):
    """F1 des cinq configurations sur dix graines. Retourne des lignes."""
    corps = []
    for resultat in resultats:
        cle = resultat["cle"]
        moyenne, ecart = vs.moyenne_et_ecart(f1_par_graine(cle, cache))
        if cle == reference():
            difference = "—"
        else:
            difference = (f"{classify.ecart_signe(resultat['moyenne'])} ± "
                          f"{fr(resultat['ecart'])}")
        corps.append([vs.NOMS_TRAITS[cle[1]], f"{fr(moyenne)} ± {fr(ecart)}", difference])
    return ["## 3. Les cinq configurations sur dix graines", "",
            "F1 macro moyen des moyennes par graine, et son écart-type **entre graines** "
            "— pas entre plis : il est donc plus petit que celui du rapport des "
            "variantes, et ce n'est pas une amélioration, seulement une autre quantité.",
            ""] + tableau(["trait pondéré", "F1 moyen ± é.-t. entre graines",
                           "différence à la référence ± é.-t."], corps) + [""]


def section_wilcoxon(resultats):
    """Résultat du test apparié. Retourne des lignes."""
    corps = []
    for resultat in resultats:
        if resultat["cle"] == reference():
            continue
        test = resultat["wilcoxon"]
        corps.append([vs.NOMS_TRAITS[resultat["cle"][1]],
                      classify.ecart_signe(resultat["moyenne"]),
                      f"{test['positives']}/{test['n']}", fr(test["w"], 1),
                      valeur_p(test["p"]),
                      "**oui**" if test["p"] < 0.05 else "non"])
    return ["## 4. Test de Wilcoxon apparié", "",
            "Chaque pondération contre la référence binaire, sur les dix moyennes par "
            "graine. « graines favorables » = graines où la pondération fait mieux. "
            "« W+ » = somme des rangs des différences positives. Seuil usuel de 0,05, "
            "sans correction de multiplicité.", ""] + tableau(
                ["trait pondéré", "différence moyenne", "graines favorables", "W+",
                 "p (bilatéral, exact)", "significatif"], corps) + [""]


def section_lecture(resultats, cache):
    """Lecture honnête du test. Retourne des lignes."""
    par_pond = {r["cle"][1]: r for r in resultats}
    partiels = [par_pond[pond] for pond in config.VARIANTES_PONDERATIONS_PAR_TRAIT]
    tout = par_pond["jdm"]
    meilleurs = [r for r in partiels if r["wilcoxon"]["p"] < 0.05 and r["moyenne"] > 0]
    pires = [r for r in partiels if r["wilcoxon"]["p"] < 0.05 and r["moyenne"] < 0]
    somme = sum(r["moyenne"] for r in partiels)
    seuil_corrige = 0.05 / len(partiels)
    lignes = ["## 5. Lecture", ""]
    if tout["wilcoxon"]["p"] < 0.05:
        lignes.append(f"- **Le gain des trois traits ensemble tient** : "
                      f"{classify.ecart_signe(tout['moyenne'])} de F1, "
                      f"p = {valeur_p(tout['wilcoxon']['p'])}, "
                      f"{tout['wilcoxon']['positives']} graines favorables sur "
                      f"{tout['wilcoxon']['n']}. Le test en plis bruts l'avait donné pour "
                      "acquis de justesse (1,06 écart-type) ; sur dix découpages entiers, "
                      "il passe un test apparié en règle.")
    else:
        lignes.append(f"- **Le gain des trois traits ensemble ne passe pas le test** : "
                      f"{classify.ecart_signe(tout['moyenne'])} de F1, "
                      f"p = {valeur_p(tout['wilcoxon']['p'])}, "
                      f"{tout['wilcoxon']['positives']} graines favorables sur "
                      f"{tout['wilcoxon']['n']}. La règle « moyenne > écart-type » de "
                      "l'étude d'origine était plus indulgente qu'un test apparié : elle "
                      "retenait ce gain, Wilcoxon ne le confirme pas.")
    detail = ", ".join(f"{vs.NOMS_TRAITS[r['cle'][1]]} {classify.ecart_signe(r['moyenne'])} "
                       f"(p = {valeur_p(r['wilcoxon']['p'])})" for r in partiels)
    if not meilleurs:
        lignes.append(f"- **Aucun trait pondéré n'améliore le F1 seul** : {detail}. Le "
                      "constat du §3.1 du rapport des variantes se confirme sur dix "
                      "graines et avec un test en règle.")
    else:
        gagnants = ", ".join(f"{vs.NOMS_TRAITS[r['cle'][1]]} "
                             f"{classify.ecart_signe(r['moyenne'])} "
                             f"(p = {valeur_p(r['wilcoxon']['p'])})" for r in meilleurs)
        survivants = [r for r in meilleurs if r["wilcoxon"]["p"] < seuil_corrige]
        lignes.append(
            f"- **Un trait pondéré améliore le F1 seul, mais de très peu** : {gagnants}. "
            f"Le détail des trois : {detail}. "
            + ("Ce gain ne survit pas à une correction de multiplicité : avec quatre "
               f"comparaisons, le seuil de Bonferroni est {fr(seuil_corrige, 4)}. "
               if not survivants else
               "Ce gain survit à une correction de Bonferroni sur quatre comparaisons. ")
            + "Et un tel écart, de l'ordre du millième de F1, ne pèse rien devant celui "
            "des trois traits ensemble.")
    if pires:
        lignes.append("- **Pondérer un seul trait peut nuire** : "
                      + ", ".join(f"{vs.NOMS_TRAITS[r['cle'][1]]} "
                                  f"{classify.ecart_signe(r['moyenne'])} "
                                  f"(p = {valeur_p(r['wilcoxon']['p'])}, "
                                  f"{r['wilcoxon']['positives']} graines favorables sur "
                                  f"{r['wilcoxon']['n']})" for r in pires)
                      + ". C'est le résultat le plus net du tableau, et il va contre "
                      "l'idée qu'on pourrait alléger la pondération en ne gardant que le "
                      "trait le plus fourni. TRT pèse à lui seul une trentaine des "
                      "cinquante symboles d'une signature (§4 du rapport des variantes : "
                      "le retirer fait tomber la taille médiane de 51 à 22) ; le pondérer "
                      "pendant que H et SST restent à 1 ne fait que déséquilibrer la "
                      "norme du vecteur en sa faveur.")
    lignes.append(f"- **Le tout reste différent de la somme de ses parties** : les trois "
                  f"gains séparés valent {classify.ecart_signe(somme)} au total, contre "
                  f"{classify.ecart_signe(tout['moyenne'])} pour les trois ensemble. "
                  "Pondérer un seul trait change la part qu'il occupe dans la norme du "
                  "vecteur face à deux traits restés à 1 ; les trois ensemble, le poids "
                  "d'un symbole veut dire la même chose des deux côtés du cosinus. C'est "
                  "une conjonction, pas l'addition de trois effets.")
    lignes.append("- **Ce que ce test ne dit pas.** Il ne corrige pas la multiplicité des "
                  "quatre comparaisons ; il réutilise les mêmes 750 exemples que l'étude "
                  "d'origine, donc il ne constitue pas une réplication indépendante ; et "
                  "il ne porte que sur l'entraînement. Le F1 de test de la configuration "
                  "retenue est dans `rapport_final_signatures.md`, lu une seule fois, et "
                  "son propre test des signes y donnait p = 0,27.")
    lignes.append("- **Aucune décision n'en découle.** La configuration retenue a été "
                  "choisie avant la lecture du test ; la changer maintenant, à la lumière "
                  "d'une analyse faite après, reviendrait à ajuster le choix sur un test "
                  "déjà dépensé.")
    return lignes + [""]


def section_sorties():
    """Fichiers écrits. Retourne des lignes."""
    chemin = config.FICHIER_MESURES_PONDERATION.relative_to(config.RACINE).as_posix()
    return ["## 6. Sorties", "",
            f"- `{chemin}` : les "
            f"{config.GRILLE_PLIS * len(config.GRAINES_PONDERATION)} mesures de chacune "
            "des cinq configurations, qui permettent de reconstruire ce rapport sans rien "
            "recalculer (`--rapport-seulement`).",
            "- `data/signatures/` n'est pas touché, et le test n'est pas lu.", ""]


def construire_rapport(resultats, reproductions, cache):
    """Écrit reports/rapport_ponderation.md. Ne retourne rien."""
    lignes = section_protocole()
    lignes += section_reproductibilite(reproductions, cache)
    lignes += section_configurations(resultats, cache)
    lignes += section_wilcoxon(resultats)
    lignes += section_lecture(resultats, cache)
    lignes += section_sorties()
    config.FICHIER_RAPPORT_PONDERATION.write_text("\n".join(lignes), encoding="utf-8")
    print(f"Rapport : {config.FICHIER_RAPPORT_PONDERATION}", flush=True)


# ---------------------------------------------------------------------------
# Enchaînement
# ---------------------------------------------------------------------------

def main():
    analyseur = argparse.ArgumentParser(
        description="Pondération par trait sur dix graines, test de Wilcoxon. Sans test.")
    analyseur.add_argument("--rapport-seulement", action="store_true",
                           dest="rapport_seulement",
                           help="reconstruit le rapport depuis le cache, sans calcul")
    options = analyseur.parse_args()

    vs.preparer_donnees()
    preparer_plis()
    cles = configurations()
    print(f"Entraînement : {sum(len(l) for l in vs.DONNEES['lignes_train'].values())} "
          f"exemples. {len(cles)} configurations × {len(config.GRAINES_PONDERATION)} "
          f"graines × {config.GRILLE_PLIS} plis. Test non lu.", flush=True)
    cache = charger_cache()
    debut = time.perf_counter()
    mesurer(cles, cache, options.rapport_seulement)
    resultats = [comparaison(cle, reference(), cache) for cle in cles]
    cache_cv = vs.charger_cache()
    reproductions = [reproductibilite(cle, cache, cache_cv) for cle in cles]
    print(f"Mesures prêtes ({grasp.fr(time.perf_counter() - debut, 0)} s).", flush=True)
    construire_rapport(resultats, reproductions, cache)


if __name__ == "__main__":
    main()
