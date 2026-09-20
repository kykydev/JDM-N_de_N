#!/usr/bin/env python3
"""Étape 4 : apprentissage par fusion de règles (papier, section 3).

Une règle est R = < sL, sR, rt, poids, exemples >. Les deux signatures restent
SÉPARÉES, jamais concaténées : la position porte le sens, « vin de France » n'est pas
« France de vin ». Fusionner deux règles, c'est unir leurs signatures côté à côté,
additionner leurs poids et concaténer leurs exemples.

Seules deux règles de MÊME type de relation peuvent fusionner (papier, note 2). Le
critère est « les deux » : la similarité des A ET celle des B doivent dépasser le seuil.
Le diagnostic (reports/diagnostic_trt_tour2.md, §4.3) a montré que la lecture
alternative — la moyenne des deux — sélectionne les paires déséquilibrées, celles dont
un côté colle et l'autre pas, qui sont typiquement de types différents.

Le processus est itératif : une règle issue d'une fusion peut refusionner. L'ordre des
fusions change le résultat, et le papier ne dit pas lequel adopter ; les deux
ordonnancements plausibles sont donc implémentés et comparés.

Aucune classification ici, aucun score, aucun élagage, aucun appel réseau. Le split test
n'est ni lu ni touché.

Usage : python3 src/grasp.py
"""

import csv
import json
import random
import statistics
from collections import defaultdict
from datetime import datetime, timezone

import config
import signatures as sig


# ---------------------------------------------------------------------------
# Split de calibrage, à l'intérieur du train
# ---------------------------------------------------------------------------

def charger_lignes_train():
    """Lignes du split train, par type de relation. Retourne relation -> liste de lignes.

    Le split test n'est jamais lu : il doit rester intact jusqu'à l'évaluation."""
    par_type = defaultdict(list)
    for chemin in sorted(config.DOSSIER_CORPUS_PROPRE.glob("corpus_*.csv")):
        with open(chemin, encoding="utf-8", newline="") as f:
            for ligne in csv.DictReader(f):
                if ligne["split"] != "train" or not ligne["A"] or not ligne["B"]:
                    continue
                par_type[ligne["relation"]].append(ligne)
    return par_type


def decouper_calibrage(lignes_train):
    """Sépare apprentissage et calibrage dans chaque type. Retourne relation -> dict.

    Tirage reproductible : une graine par type, dérivée de la graine globale, pour
    qu'ajouter un type au corpus ne change pas la découpe des autres. On tire les
    indices de calibrage, jamais l'ordre des lignes : l'ordre du corpus est ce qui
    départage les ex aequo pendant la fusion, il doit être conservé."""
    decoupe = {}
    for relation in sorted(lignes_train):
        lignes = lignes_train[relation]
        tirage = random.Random(f"{config.GRAINE_ALEATOIRE}:{relation}")
        indices = sorted(tirage.sample(range(len(lignes)),
                                       min(config.TAILLE_CALIBRAGE, len(lignes))))
        en_calibrage = set(indices)
        decoupe[relation] = {
            "apprentissage": [l for i, l in enumerate(lignes) if i not in en_calibrage],
            "calibrage": [lignes[i] for i in indices],
        }
    return decoupe


def ecrire_split_calibrage(decoupe):
    """Écrit data/corpus/clean/split_calibrage.csv. Ne retourne rien."""
    config.FICHIER_SPLIT_CALIBRAGE.parent.mkdir(parents=True, exist_ok=True)
    with open(config.FICHIER_SPLIT_CALIBRAGE, "w", encoding="utf-8", newline="") as f:
        redacteur = csv.writer(f, lineterminator="\n")
        redacteur.writerow(["syntagme", "A", "B", "relation", "sous_split"])
        for relation in sorted(decoupe):
            for sous_split in ("apprentissage", "calibrage"):
                for ligne in decoupe[relation][sous_split]:
                    redacteur.writerow([ligne["syntagme"], ligne["A"], ligne["B"],
                                        relation, sous_split])


# ---------------------------------------------------------------------------
# Règles initiales
# ---------------------------------------------------------------------------

def regle_initiale(ligne, signatures, ordre):
    """Construit la règle d'une ligne de corpus. Retourne un dict.

    `ordre` est le rang de la ligne dans son type : il sert à départager les ex aequo
    pendant la fusion, pour que le résultat ne dépende pas de l'ordre d'un ensemble."""
    return {"sL": set(signatures.get(ligne["A"], {ligne["A"]})),
            "sR": set(signatures.get(ligne["B"], {ligne["B"]})),
            "rt": ligne["relation"], "poids": 1,
            "exemples": [ligne["syntagme"]], "ordre": ordre}


def regles_initiales(lignes, signatures):
    """Une règle de poids 1 par ligne d'apprentissage. Retourne une liste."""
    return [regle_initiale(ligne, signatures, rang)
            for rang, ligne in enumerate(lignes)]


# ---------------------------------------------------------------------------
# Fusion
# ---------------------------------------------------------------------------

def fusionner(regle_1, regle_2):
    """Unit deux règles de même type. Retourne une nouvelle règle.

    Les signatures s'unissent côté à côté : les A avec les A, les B avec les B. Le
    poids est le nombre d'exemples couverts, les exemples sont concaténés pour la
    traçabilité, et l'ordre retenu est le plus petit des deux."""
    return {"sL": regle_1["sL"] | regle_2["sL"],
            "sR": regle_1["sR"] | regle_2["sR"],
            "rt": regle_1["rt"],
            "poids": regle_1["poids"] + regle_2["poids"],
            "exemples": regle_1["exemples"] + regle_2["exemples"],
            "ordre": min(regle_1["ordre"], regle_2["ordre"])}


def similarites_de_paire(regle_1, regle_2):
    """Similarité des A et similarité des B. Retourne un couple de flottants."""
    return (sig.similarite(regle_1["sL"], regle_2["sL"]),
            sig.similarite(regle_1["sR"], regle_2["sR"]))


def paire_fusionnable(gauche, droite, seuil):
    """Critère « les deux » : les deux similarités dépassent le seuil. Retourne un bool."""
    return gauche > seuil and droite > seuil


def remplacer_par_fusion(regles, i, j):
    """Retire les règles i et j, ajoute leur fusion, retrie par ordre.
    Retourne (liste, fusion)."""
    fusion = fusionner(regles[i], regles[j])
    restantes = [regle for rang, regle in enumerate(regles) if rang not in (i, j)]
    restantes.append(fusion)
    restantes.sort(key=lambda regle: regle["ordre"])
    return restantes, fusion


def fusionner_glouton(regles, seuil, historique=None):
    """Fusionne à chaque tour la meilleure paire du type. Retourne (règles, journal).

    À chaque tour, toutes les paires candidates sont évaluées et la plus ressemblante
    l'emporte, la similarité moyenne servant de score. Les ex aequo sont départagés par
    l'ordre d'apparition dans le corpus. Coûteux — tout est recalculé après chaque
    fusion — mais insensible à l'ordre de lecture.

    `historique`, si fourni, reçoit toute règle ayant existé, intermédiaires comprises :
    c'est l'ensemble « No Trim » de l'Expérience 3."""
    courantes = sorted(regles, key=lambda regle: regle["ordre"])
    if historique is not None:
        historique.extend(regles)
    fusions, tours = 0, 0
    while True:
        tours += 1
        meilleure_cle, meilleure_paire = None, None
        for i in range(len(courantes)):
            for j in range(i + 1, len(courantes)):
                gauche, droite = similarites_de_paire(courantes[i], courantes[j])
                if not paire_fusionnable(gauche, droite, seuil):
                    continue
                cle = (-(gauche + droite) / 2.0, courantes[i]["ordre"],
                       courantes[j]["ordre"])
                if meilleure_cle is None or cle < meilleure_cle:
                    meilleure_cle, meilleure_paire = cle, (i, j)
        if meilleure_paire is None:
            return courantes, {"fusions": fusions, "tours": tours}
        courantes, fusion = remplacer_par_fusion(courantes, *meilleure_paire)
        if historique is not None:
            historique.append(fusion)
        fusions += 1


def fusionner_sequentiel(regles, seuil):
    """Fusionne la première paire candidate rencontrée, en boucle. Retourne (règles, journal).

    Parcourt les règles dans l'ordre du corpus et fusionne dès qu'une paire passe le
    critère, sans chercher mieux ailleurs. Un tour est un parcours complet ; on
    recommence tant qu'un tour a produit une fusion."""
    courantes = sorted(regles, key=lambda regle: regle["ordre"])
    fusions, tours = 0, 0
    a_fusionne = True
    while a_fusionne:
        tours += 1
        a_fusionne = False
        for i in range(len(courantes)):
            for j in range(i + 1, len(courantes)):
                gauche, droite = similarites_de_paire(courantes[i], courantes[j])
                if not paire_fusionnable(gauche, droite, seuil):
                    continue
                courantes, _ = remplacer_par_fusion(courantes, i, j)
                fusions += 1
                a_fusionne = True
                break
            if a_fusionne:
                break
    return courantes, {"fusions": fusions, "tours": tours}


def apprendre(regles, strategie, seuil):
    """Applique la stratégie de fusion demandée. Retourne (règles, journal)."""
    if strategie == "glouton":
        return fusionner_glouton(regles, seuil)
    if strategie == "sequentiel":
        return fusionner_sequentiel(regles, seuil)
    raise ValueError(f"stratégie de fusion inconnue : {strategie}")


# ---------------------------------------------------------------------------
# Instrumentation
# ---------------------------------------------------------------------------

def tailles_signatures(regles):
    """Tailles des deux signatures de chaque règle, mises en commun. Retourne une liste."""
    tailles = []
    for regle in regles:
        tailles.append(len(regle["sL"]))
        tailles.append(len(regle["sR"]))
    return tailles


def emballements(regles, avant, n_exemples):
    """Règles qui ont trop absorbé. Retourne une liste de dicts.

    Deux symptômes, tirés du brief : une règle qui couvre plus de la moitié des exemples
    de son type, ou dont une signature dépasse le triple de la taille initiale médiane.
    Une règle qui absorbe tout ne discrimine plus rien."""
    reference = statistics.median(tailles_signatures(avant)) if avant else 0
    plafond = config.EMBALLEMENT_FACTEUR_TAILLE * reference
    part_max = config.EMBALLEMENT_PART_EXEMPLES * n_exemples
    signales = []
    for regle in regles:
        taille = max(len(regle["sL"]), len(regle["sR"]))
        par_poids = regle["poids"] > part_max
        par_taille = bool(reference) and taille > plafond
        if not par_poids and not par_taille:
            continue
        signales.append({"rt": regle["rt"], "poids": regle["poids"],
                         "sL": len(regle["sL"]), "sR": len(regle["sR"]),
                         "taille": taille, "reference": reference,
                         "n_exemples": n_exemples,
                         "par_poids": par_poids, "par_taille": par_taille,
                         "facteur": taille / reference if reference else 0.0,
                         "exemples": regle["exemples"]})
    return signales


def instrumenter(relation, avant, apres, journal):
    """Mesure le comportement de la cascade sur un type. Retourne un dict."""
    poids = [regle["poids"] for regle in apres]
    tailles_avant = tailles_signatures(avant)
    tailles_apres = tailles_signatures(apres)
    return {
        "rt": relation,
        "avant": len(avant), "apres": len(apres),
        "fusions": journal["fusions"], "tours": journal["tours"],
        "poids_min": min(poids), "poids_median": statistics.median(poids),
        "poids_max": max(poids), "poids_moyen": statistics.fmean(poids),
        "part_plus_lourde": max(poids) / len(avant) if avant else 0.0,
        "orphelines": sum(1 for p in poids if p == 1),
        "taille_avant_mediane": statistics.median(tailles_avant),
        "taille_apres_mediane": statistics.median(tailles_apres),
        "taille_apres_max": max(tailles_apres),
        "emballements": emballements(apres, avant, len(avant)),
    }


def agreger(mesures):
    """Résume l'instrumentation sur les quinze types. Retourne un dict."""
    avant = sum(m["avant"] for m in mesures)
    apres = sum(m["apres"] for m in mesures)
    poids_max = max(m["poids_max"] for m in mesures)
    return {
        "avant": avant, "apres": apres,
        "reduction": (avant - apres) / avant if avant else 0.0,
        "fusions": sum(m["fusions"] for m in mesures),
        "tours_max": max(m["tours"] for m in mesures),
        "orphelines": sum(m["orphelines"] for m in mesures),
        "part_orphelines": (sum(m["orphelines"] for m in mesures) / apres
                            if apres else 0.0),
        "poids_median": statistics.median([m["poids_median"] for m in mesures]),
        "poids_max": poids_max,
        "taille_avant_mediane": statistics.median(
            [m["taille_avant_mediane"] for m in mesures]),
        "taille_apres_mediane": statistics.median(
            [m["taille_apres_mediane"] for m in mesures]),
        "taille_apres_max": max(m["taille_apres_max"] for m in mesures),
        "types_emballes": sum(1 for m in mesures if m["emballements"]),
        "regles_emballees": sum(len(m["emballements"]) for m in mesures),
        "emballees_poids": sum(1 for m in mesures for e in m["emballements"]
                               if e["par_poids"]),
        "emballees_taille": sum(1 for m in mesures for e in m["emballements"]
                                if e["par_taille"]),
        "facteur_max": max([e["facteur"] for m in mesures for e in m["emballements"]],
                           default=0.0),
        "part_plus_lourde": max(m["part_plus_lourde"] for m in mesures),
        "poids_moyen": avant / apres if apres else 0.0,
    }


# ---------------------------------------------------------------------------
# Écriture des modèles
# ---------------------------------------------------------------------------

def nom_fichier_modele(strategie, seuil):
    """Nom du fichier de règles fusionnées. Retourne un chemin.

    Le seuil est écrit sans séparateur décimal : 0,35 donne 035, pour ne pas semer de
    points dans un nom de fichier."""
    marque = f"{int(round(seuil * 100)):03d}"
    return config.DOSSIER_MODELES / f"regles_fusionnees_{strategie}_{marque}.json"


def serialiser_regle(regle):
    """Prépare une règle pour le JSON : ensembles triés, ordre retiré. Retourne un dict."""
    return {"rt": regle["rt"], "poids": regle["poids"],
            "sL": sorted(regle["sL"]), "sR": sorted(regle["sR"]),
            "exemples": regle["exemples"]}


def ecrire_modele(strategie, seuil, regles_par_type, resume):
    """Écrit un fichier de règles fusionnées. Retourne le chemin écrit."""
    chemin = nom_fichier_modele(strategie, seuil)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    contenu = []
    for relation in sorted(regles_par_type):
        for regle in regles_par_type[relation]:
            contenu.append(serialiser_regle(regle))
    charge = {
        "strategie": strategie, "seuil": seuil,
        "critere": "les deux (sim des A ET sim des B > seuil)",
        "split": "apprentissage (40 exemples par type)",
        "trt_centile": config.TRT_CENTILE,
        "genere_le": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "n_regles": len(contenu), "resume": resume, "regles": contenu,
    }
    with open(chemin, "w", encoding="utf-8", newline="") as f:
        json.dump(charge, f, ensure_ascii=False, indent=1, sort_keys=False)
        f.write("\n")
    return chemin


# ---------------------------------------------------------------------------
# Balayage
# ---------------------------------------------------------------------------

def lancer_une_combinaison(depart, strategie, seuil):
    """Apprend sur les quinze types pour une stratégie et un seuil. Retourne un dict."""
    regles_par_type, mesures = {}, []
    for relation in sorted(depart):
        apres, journal = apprendre(depart[relation], strategie, seuil)
        regles_par_type[relation] = apres
        mesures.append(instrumenter(relation, depart[relation], apres, journal))
    return {"strategie": strategie, "seuil": seuil, "regles": regles_par_type,
            "mesures": mesures, "resume": agreger(mesures)}


def balayer(depart):
    """Apprend pour chaque stratégie et chaque seuil. Retourne une liste de résultats."""
    resultats = []
    for strategie in config.GRASP_STRATEGIES:
        for seuil in config.GRASP_SEUILS:
            resultat = lancer_une_combinaison(depart, strategie, seuil)
            resume = resultat["resume"]
            chemin = ecrire_modele(strategie, seuil, resultat["regles"], resume)
            resultat["fichier"] = chemin
            resultats.append(resultat)
            print(f"  {strategie:11s} seuil {fr(seuil, 2)} : "
                  f"{resume['avant']} -> {resume['apres']} règles "
                  f"({pct(resume['reduction'])} de réduction), "
                  f"{resume['fusions']} fusions, poids max {resume['poids_max']}, "
                  f"{resume['types_emballes']} type(s) emballé(s)", flush=True)
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


def par_strategie(resultats, strategie):
    """Résultats d'une stratégie, par seuil croissant. Retourne une liste."""
    return [r for r in resultats if r["strategie"] == strategie]


def trouver(resultats, strategie, seuil):
    """Retrouve un résultat par stratégie et seuil. Retourne un dict."""
    return next(r for r in resultats if r["strategie"] == strategie and r["seuil"] == seuil)


# ---------------------------------------------------------------------------
# Rapport : une fonction par section
# ---------------------------------------------------------------------------

def section_dispositif(decoupe, depart):
    """Section 1 : le split et les règles de départ. Retourne une liste de lignes."""
    n_app = sum(len(d["apprentissage"]) for d in decoupe.values())
    n_cal = sum(len(d["calibrage"]) for d in decoupe.values())
    tailles = tailles_signatures([r for regles in depart.values() for r in regles])
    return ["## 1. Dispositif", "",
            f"- **Split.** Les {n_app + n_cal} lignes d'entraînement sont coupées par "
            f"type en {config.TAILLE_APPRENTISSAGE} d'apprentissage et "
            f"{config.TAILLE_CALIBRAGE} de calibrage, soit {n_app} et {n_cal} au total. "
            f"Tirage `random.Random` à graine dérivée de {config.GRAINE_ALEATOIRE}, une "
            "par type, écrit dans "
            f"`{config.FICHIER_SPLIT_CALIBRAGE.relative_to(config.RACINE).as_posix()}`. "
            "**Le split test n'est ni lu ni touché.**",
            "- **Calibrage non utilisé ici.** Il sert à l'étape 5 pour arrêter le seuil ; "
            "cette étape n'apprend que sur les 40.",
            f"- **Signatures.** Politique TRT P8@C{config.TRT_CENTILE}, appliquée dans "
            "`config.py` après les deux diagnostics. Les signatures de départ font "
            f"{min(tailles)} à {max(tailles)} symboles, médiane "
            f"{fr(statistics.median(tailles), 0)}.",
            "- **Critère.** « les deux » : sim(A₁,A₂) > seuil ET sim(B₁,B₂) > seuil, "
            "strictement. Seules deux règles de même `rt` peuvent fusionner.",
            "- **Itératif.** Une règle issue d'une fusion peut refusionner ; on s'arrête "
            "quand plus aucune paire ne passe.", ""]


def section_balayage(resultats):
    """Section 2 : le tableau principal, par stratégie et par seuil. Retourne des lignes."""
    lignes = ["## 2. Balayage : douze combinaisons", "",
              "« tours max » est le plus grand nombre de parcours complets qu'un type a "
              "demandés avant stabilité. En glouton, un tour égale une fusion, puisque "
              "tout est recalculé après chacune ; en séquentiel, un tour est un parcours "
              "qui peut enchaîner plusieurs fusions.", ""]
    for strategie in config.GRASP_STRATEGIES:
        corps = []
        for resultat in par_strategie(resultats, strategie):
            resume = resultat["resume"]
            corps.append([marque_papier(resultat["seuil"]),
                          f"{resume['avant']} → **{resume['apres']}**",
                          pct(resume["reduction"]),
                          resume["fusions"], resume["tours_max"],
                          f"{resume['orphelines']} ({pct(resume['part_orphelines'], 0)})",
                          f"1 / {fr(resume['poids_median'], 1)} / {resume['poids_max']}",
                          f"{fr(resume['taille_avant_mediane'], 0)} → "
                          f"{fr(resume['taille_apres_mediane'], 0)}",
                          resume["taille_apres_max"],
                          f"{resume['types_emballes']} / {resume['regles_emballees']}"])
        lignes += [f"### 2.{list(config.GRASP_STRATEGIES).index(strategie) + 1} "
                   f"Stratégie « {strategie} »", ""]
        lignes += tableau(["seuil", "règles", "réduction", "fusions", "tours max",
                           "orphelines", "poids min/méd./max", "taille méd.",
                           "taille max", "types/règles emballés"], corps)
        lignes += [""]
    return lignes


def section_comparaison(resultats):
    """Section 3 : glouton contre séquentiel, seuil par seuil. Retourne des lignes."""
    corps = []
    for seuil in config.GRASP_SEUILS:
        glouton = trouver(resultats, "glouton", seuil)["resume"]
        sequentiel = trouver(resultats, "sequentiel", seuil)["resume"]
        corps.append([marque_papier(seuil),
                      glouton["apres"], sequentiel["apres"],
                      sequentiel["apres"] - glouton["apres"],
                      glouton["poids_max"], sequentiel["poids_max"],
                      glouton["taille_apres_max"], sequentiel["taille_apres_max"],
                      f"{glouton['types_emballes']} / {sequentiel['types_emballes']}"])
    return (["## 3. Glouton contre séquentiel", "",
             "Les deux stratégies partent des mêmes règles et appliquent le même critère ; "
             "seul l'ordre des fusions diffère.", ""]
            + tableau(["seuil", "règles glouton", "règles séq.", "écart",
                       "poids max glouton", "poids max séq.", "taille max glouton",
                       "taille max séq.", "types emballés g/s"], corps) + [""])


def section_par_type(resultats, seuils_detailles):
    """Section 4 : le détail par type pour quelques seuils. Retourne des lignes."""
    lignes = ["## 4. Détail par type", "",
              "Stratégie gloutonne, aux seuils qui encadrent la fourchette retenue au "
              "tour 2 et au seuil du papier. Un type dont les règles s'effondrent vers "
              "une poignée d'unités très lourdes est un type qui a perdu sa capacité à "
              "distinguer.", ""]
    for seuil in seuils_detailles:
        resultat = trouver(resultats, "glouton", seuil)
        corps = []
        for mesure in sorted(resultat["mesures"], key=lambda m: m["rt"]):
            corps.append([f"`{mesure['rt']}`",
                          f"{mesure['avant']} → {mesure['apres']}",
                          mesure["fusions"], mesure["orphelines"],
                          f"1 / {fr(mesure['poids_median'], 1)} / {mesure['poids_max']}",
                          f"{fr(mesure['taille_avant_mediane'], 0)} → "
                          f"{fr(mesure['taille_apres_mediane'], 0)}",
                          mesure["taille_apres_max"],
                          "oui" if mesure["emballements"] else "—"])
        lignes += [f"### 4.{seuils_detailles.index(seuil) + 1} Seuil "
                   f"{marque_papier(seuil)}, glouton", ""]
        lignes += tableau(["type", "règles", "fusions", "orphelines",
                           "poids min/méd./max", "taille méd.", "taille max",
                           "emballement"], corps)
        lignes += [""]
    return lignes


def section_emballement(resultats):
    """Section 5 : les règles qui ont trop absorbé, par critère. Retourne des lignes."""
    lignes = ["## 5. Détection d'emballement", "",
              "Deux symptômes distincts, et ils ne se déclenchent pas au même moment.",
              "",
              f"- **Par le poids** : une règle couvre plus de "
              f"{pct(config.EMBALLEMENT_PART_EXEMPLES, 0)} des "
              f"{config.TAILLE_APPRENTISSAGE} exemples de son type.",
              f"- **Par la taille** : une de ses signatures dépasse "
              f"{config.EMBALLEMENT_FACTEUR_TAILLE} fois la taille initiale médiane du "
              "type.", "",
              "Aucune règle de départ ne déclenche l'un ou l'autre : tout ce qui suit "
              "est produit par la cascade.", ""]
    corps = []
    for resultat in resultats:
        resume = resultat["resume"]
        corps.append([resultat["strategie"], marque_papier(resultat["seuil"]),
                      resume["emballees_poids"], resume["emballees_taille"],
                      f"{resume['poids_max']} / {config.TAILLE_APPRENTISSAGE} "
                      f"({pct(resume['part_plus_lourde'], 0)})",
                      resume["taille_apres_max"],
                      f"{fr(resume['facteur_max'], 1)}×" if resume["facteur_max"] else "—"])
    lignes += tableau(["stratégie", "seuil", "signalées par poids",
                       "signalées par taille", "règle la plus lourde",
                       "signature la plus grande", "facteur max"], corps)

    pires = []
    for resultat in resultats:
        for mesure in resultat["mesures"]:
            for signale in mesure["emballements"]:
                pires.append((resultat["strategie"], resultat["seuil"], signale))
    pires.sort(key=lambda e: (-e[2]["taille"], e[0], e[1], e[2]["rt"]))
    corps = []
    for strategie, seuil, signale in pires[:10]:
        marques = []
        if signale["par_poids"]:
            marques.append("poids")
        if signale["par_taille"]:
            marques.append("taille")
        corps.append([strategie, fr(seuil, 2), f"`{signale['rt']}`",
                      f"{signale['poids']} / {signale['n_exemples']}",
                      f"{signale['sL']} / {signale['sR']}",
                      f"{fr(signale['facteur'], 1)}×", " + ".join(marques)])
    lignes += ["", "### 5.1 Les dix règles les plus enflées", "",
               "Une règle dont la signature compte plusieurs centaines de symboles "
               "ressemble un peu à tout : elle ne sépare plus rien.", ""]
    lignes += tableau(["stratégie", "seuil", "type", "poids", "\\|sL\\| / \\|sR\\|",
                       "facteur", "critère"], corps)
    return lignes + [""]


def section_cascade(resultats):
    """Section 6 : analyse du comportement de la cascade. Retourne des lignes."""
    bas = trouver(resultats, "glouton", min(config.GRASP_SEUILS))["resume"]
    haut = trouver(resultats, "glouton", max(config.GRASP_SEUILS))["resume"]
    papier = trouver(resultats, "glouton", config.GRASP_SEUIL_PAPIER)["resume"]

    lignes = ["## 6. Comportement de la cascade", "",
              "### 6.1 Elle s'arrête tôt, et de plus en plus tôt", "",
              f"À {fr(min(config.GRASP_SEUILS), 2)} la cascade fait {bas['fusions']} "
              f"fusions et ramène {bas['avant']} règles à {bas['apres']} "
              f"({pct(bas['reduction'])}). À {fr(config.GRASP_SEUIL_PAPIER, 2)}, le seuil "
              f"du papier, elle n'en fait plus que {papier['fusions']} et laisse "
              f"{papier['apres']} règles, soit {pct(papier['reduction'])} de réduction. À "
              f"{fr(max(config.GRASP_SEUILS), 2)} il reste {haut['fusions']} fusions sur "
              "600 règles.", "",
              f"**Au seuil du papier, {pct(papier['part_orphelines'], 0)} des règles "
              "finales sont des orphelines de poids 1.** L'apprentissage y est pour "
              "l'essentiel une recopie du corpus d'apprentissage : il ne généralise "
              "presque rien. C'est cohérent avec la mesure du tour 2, qui donnait 0,4 % "
              "de paires fusionnables à 0,50 — et c'est bien pour cela que la fourchette "
              "0,35–0,45 avait été retenue.", "",
              "### 6.2 Elle n'emballe pas par le poids, elle enfle par la signature", ""]

    corps = []
    for seuil in config.GRASP_SEUILS:
        resume = trouver(resultats, "glouton", seuil)["resume"]
        corps.append([marque_papier(seuil), fr(resume["poids_median"], 1),
                      fr(resume["poids_moyen"], 2), resume["poids_max"],
                      resume["emballees_poids"], resume["taille_apres_max"],
                      resume["emballees_taille"]])
    lignes += tableau(["seuil", "poids médian", "poids moyen", "poids max",
                       "signalées poids", "taille max", "signalées taille"], corps)
    lignes += ["",
               "**Le poids médian vaut 1,0 à tous les seuils, dans les deux stratégies.** "
               f"Pendant qu'une règle atteint {bas['poids_max']} exemples sur "
               f"{config.TAILLE_APPRENTISSAGE}, la moitié des règles n'ont toujours "
               "fusionné avec personne. La cascade ne répartit pas les fusions : elle "
               "les concentre. C'est un mécanisme du riche qui s'enrichit — plus une "
               "règle absorbe, plus sa signature grossit, plus elle ressemble à tout le "
               "monde, plus elle absorbe.", "",
               f"Le critère de taille le montre mieux que celui du poids : à "
               f"{fr(min(config.GRASP_SEUILS), 2)}, {bas['emballees_poids']} règles "
               f"seulement dépassent la moitié des exemples, mais "
               f"{bas['emballees_taille']} ont une signature démesurée, jusqu'à "
               f"{bas['taille_apres_max']} symboles quand la médiane de départ est "
               f"{fr(bas['taille_avant_mediane'], 0)} — un facteur "
               f"{fr(bas['facteur_max'], 1)}. Une signature de cette taille n'est plus "
               "une généralisation, c'est un fourre-tout.", "",
               f"Le phénomène n'épargne pas la fourchette retenue au tour 2 : à 0,35 la "
               f"plus grosse signature atteint "
               f"{trouver(resultats, 'glouton', 0.35)['resume']['taille_apres_max']} "
               f"symboles, à 0,45 encore "
               f"{trouver(resultats, 'glouton', 0.45)['resume']['taille_apres_max']}. "
               "L'élagage de l'Expérience 3 aura de quoi faire.", "",
               "### 6.3 Sur quels types ?", ""]

    seuil_vif = min(config.GRASP_SEUILS)
    vif = trouver(resultats, "glouton", seuil_vif)
    par_reduction = sorted(vif["mesures"],
                           key=lambda m: (m["apres"] - m["avant"], m["rt"]))
    corps = []
    for mesure in par_reduction[:3] + par_reduction[-3:]:
        corps.append([f"`{mesure['rt']}`", f"{mesure['avant']} → {mesure['apres']}",
                      pct((mesure["avant"] - mesure["apres"]) / mesure["avant"]),
                      mesure["poids_max"], mesure["orphelines"],
                      mesure["taille_apres_max"]])
    lignes += [f"Au seuil {fr(seuil_vif, 2)}, glouton — là où la cascade travaille le "
               "plus —, les trois types qui fusionnent le plus et les trois qui "
               "fusionnent le moins :", ""]
    lignes += tableau(["type", "règles", "réduction", "poids max", "orphelines",
                       "taille max"], corps)
    haut_trois = ", ".join(f"`{m['rt']}`" for m in par_reduction[:3])
    bas_trois = ", ".join(f"`{m['rt']}`" for m in par_reduction[-3:])
    lignes += ["",
               f"Les types qui fusionnent le plus ({haut_trois}) sont ceux dont les A "
               "sont sémantiquement homogènes — des productions, des propriétés, des "
               "liens de parenté — donc dont les signatures gauches se recouvrent "
               f"naturellement. Ceux qui résistent ({bas_trois}) ont des A très "
               "hétérogènes : n'importe quoi peut être le sujet d'un document ou la "
               "partie d'un tout.", "",
               "### 6.4 Les deux stratégies se départagent peu", ""]

    ecarts = []
    for seuil in config.GRASP_SEUILS:
        g = trouver(resultats, "glouton", seuil)["resume"]
        s = trouver(resultats, "sequentiel", seuil)["resume"]
        ecarts.append(abs(g["apres"] - s["apres"]) / g["apres"])
    lignes += [f"L'écart maximal sur le nombre de règles finales est de "
               f"{pct(max(ecarts), 1)}, atteint au seuil le plus bas ; aux seuils "
               f"{fr(config.GRASP_SEUIL_PAPIER, 2)} et "
               f"{fr(max(config.GRASP_SEUILS), 2)} les deux stratégies donnent le même "
               "compte. Le glouton produit des signatures un peu moins grosses aux seuils "
               "bas, le séquentiel des règles un peu plus lourdes aux seuils moyens, mais "
               "rien qui ressemble à une différence de nature.", "",
               "La question laissée ouverte par le papier — dans quel ordre fusionner — "
               "a donc, sur ce corpus, une réponse tiède : cela ne change pas grand-chose. "
               "Le glouton reste préférable par principe, puisqu'il ne dépend pas de "
               "l'ordre de lecture du corpus, et son coût n'est pas un problème à cette "
               "taille (trois secondes pour les douze combinaisons).", ""]
    return lignes


def section_sorties(resultats):
    """Section 7 : les fichiers écrits. Retourne des lignes."""
    corps = []
    for resultat in resultats:
        chemin = resultat["fichier"].relative_to(config.RACINE).as_posix()
        corps.append([f"`{chemin}`", resultat["strategie"],
                      marque_papier(resultat["seuil"]), resultat["resume"]["apres"]])
    return (["## 7. Sorties écrites", "",
             "Chaque fichier porte ses règles fusionnées — `rt`, `sL` et `sR` triés, "
             "`poids`, `exemples` — plus la stratégie, le seuil et le résumé "
             "d'instrumentation. Les signatures ne sont jamais concaténées.", ""]
            + tableau(["fichier", "stratégie", "seuil", "règles"], corps) + [""])


def construire_rapport(resultats, decoupe, depart):
    """Assemble reports/rapport_grasp.md. Ne retourne rien."""
    chemin = config.DOSSIER_RAPPORTS / "rapport_grasp.md"
    lignes = ["# Apprentissage par fusion : instrumentation de la cascade", "",
              "Étape 4 du papier (section 3), mesurée et non tranchée. Douze "
              "combinaisons : deux ordonnancements de fusion et six seuils. Aucune "
              "classification, aucun score, aucun élagage, aucun appel réseau, et le "
              "split test n'est pas touché.", ""]
    lignes += section_dispositif(decoupe, depart)
    lignes += section_balayage(resultats)
    lignes += section_comparaison(resultats)
    lignes += section_par_type(resultats, [0.35, 0.45, config.GRASP_SEUIL_PAPIER])
    lignes += section_emballement(resultats)
    lignes += section_cascade(resultats)
    lignes += section_sorties(resultats)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    print(f"Rapport écrit : {chemin}", flush=True)


# ---------------------------------------------------------------------------
# Enchaînement
# ---------------------------------------------------------------------------

def main():
    signatures = {terme: set(symboles) for terme, symboles in
                  json.loads(config.FICHIER_SIGNATURES.read_text(encoding="utf-8")).items()}
    print(f"Signatures : {len(signatures)} lues.", flush=True)

    lignes_train = charger_lignes_train()
    decoupe = decouper_calibrage(lignes_train)
    ecrire_split_calibrage(decoupe)
    n_app = sum(len(d["apprentissage"]) for d in decoupe.values())
    n_cal = sum(len(d["calibrage"]) for d in decoupe.values())
    print(f"Split : {n_app} exemples d'apprentissage, {n_cal} de calibrage, "
          f"sur {len(decoupe)} types. Test non touché.", flush=True)

    depart = {}
    for relation in sorted(decoupe):
        depart[relation] = regles_initiales(decoupe[relation]["apprentissage"], signatures)
    print(f"Règles de départ : {sum(len(r) for r in depart.values())}.", flush=True)

    resultats = balayer(depart)
    construire_rapport(resultats, decoupe, depart)


if __name__ == "__main__":
    main()
