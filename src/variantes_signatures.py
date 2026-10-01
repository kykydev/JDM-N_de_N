#!/usr/bin/env python3
"""Variantes de construction des signatures, en validation croisée sur l'entraînement.

La méthode reste figée : somme · arbre · descente. Ce qui varie, c'est la signature :

  0. le traitement du symbole du terme lui-même (T0 sans préfixe, T1 sous la forme
     H:<terme>, T2 absent) ;
  1. le nombre d'hyperonymes × la pondération des symboles (binaire, idf, jdm, jdm×idf) ;
  2. la sélection TRT et SST, un paramètre à la fois ;
  3. le seuil de fréquence documentaire minimale (df ≥ 2).

Une signature devient un dict symbole -> poids réel. Les feuilles portent ces poids, un
nœud fusionné est la SOMME des vecteurs de ses enfants, le cosinus se calcule sur les
vecteurs (grasp.similarite_signatures, déjà écrite pour les comptes). L'exemple à classer
utilise les mêmes poids.

Protocole : 5 plis stratifiés par type, répétés avec les graines de
config.GRAINES_VARIANTES, soit 15 mesures de F1 par configuration, sur les MÊMES plis.
Toute statistique tirée des données (fréquences documentaires, centiles, types trop
fréquents) l'est sur les TERMES D'ENTRAÎNEMENT DU PLI seulement. Les différences à la
référence sont appariées pli par pli : une configuration ne bat la référence que si la
différence moyenne dépasse son écart-type.

Tout part de data/collecte/ : aucun appel réseau, data/signatures/ n'est pas touché, les
signatures variantes n'existent qu'en mémoire. **Le split test n'est pas lu.**

Usage : python3 src/variantes_signatures.py [--rapport-seulement] [--processus N]
"""

import argparse
import json
import math
import multiprocessing
import os
import statistics
import time
from collections import Counter

import classify
import config
import grasp
import grille
import signatures as sig


# Ordre des champs d'une configuration, dans la clé qui l'identifie.
CHAMPS = ("h", "pond", "terme", "trt", "sst", "df_min")

# Pondérations qui font intervenir la fréquence documentaire.
FAMILLE_IDF = ("idf", "jdm×idf")
FAMILLE_JDM = ("jdm", "jdm×idf")

# Préfixes que chaque pondération partielle pondère ; les autres symboles restent à 1.
TRAITS_JDM = {"jdm_H": (config.PREFIXE_H,), "jdm_TRT": (config.PREFIXE_TRT,),
              "jdm_SST": (config.PREFIXE_SST,)}

# Données lues une fois avant de lancer les processus, héritées par les processus fils.
DONNEES = {}


# ---------------------------------------------------------------------------
# Configurations
# ---------------------------------------------------------------------------

def cle_de(reglages):
    """Clé d'une configuration, tuple ordonné selon CHAMPS. Retourne un tuple."""
    return tuple(reglages[champ] for champ in CHAMPS)


def reglages_de(cle):
    """Réglages d'une configuration, dict champ -> valeur. Retourne un dict."""
    return dict(zip(CHAMPS, cle))


def variante(cle, **changements):
    """Copie d'une configuration avec quelques champs changés. Retourne une clé."""
    reglages = reglages_de(cle)
    reglages.update(changements)
    return cle_de(reglages)


def cle_json(cle):
    """Forme texte d'une clé, pour le cache disque. Retourne une chaîne."""
    return "|".join(str(champ) for champ in cle)


def libelle(cle):
    """Description lisible d'une configuration. Retourne une chaîne."""
    h, pond, terme, trt, sst, df_min = cle
    return (f"H {h} · {pond} · {terme} · TRT {trt} · SST {sst}"
            + (f" · df ≥ {df_min}" if df_min > 1 else ""))


# ---------------------------------------------------------------------------
# Données de base, indépendantes de la configuration et du pli
# ---------------------------------------------------------------------------

def termes_des_lignes(lignes_par_type):
    """Tous les A et B d'un ensemble de lignes. Retourne un ensemble."""
    termes = set()
    for lignes in lignes_par_type.values():
        for ligne in lignes:
            termes.add(ligne["A"])
            termes.add(ligne["B"])
    return termes


def base_du_terme(enregistrement):
    """Ce que la collecte sait d'un terme, avant tout réglage. Retourne un dict ou None.

    None pour un terme absent de JDM : sa signature se réduit à lui-même. Les
    hyperonymes sont déjà filtrés (poids > 0), débarrassés des doublons de casse et
    triés par poids décroissant, comme dans signatures.symboles_h, mais SANS coupure."""
    if enregistrement is None or not enregistrement.get("existe"):
        return None
    bruts = enregistrement.get("H") or []
    retenus = [c for c in bruts if c["poids"] > 0
               and not (config.H_EXCLURE_PREFIXES_LANGUE and c["lang_prefix"])]
    fusionnes = sig.fusionner_doublons_casse(retenus)
    fusionnes.sort(key=lambda c: (-c["poids"], c["nom"]))
    annotations = {}
    for annotation in enregistrement.get("SST") or []:
        if annotation["poids"] > 0:
            ancien = annotations.get(annotation["tag"], (0, False))[0]
            annotations[annotation["tag"]] = (max(ancien, annotation["poids"]),
                                              annotation["morpho"])
    return {"H": [(c["nom"], c["poids"]) for c in fusionnes],
            "H_bruts": len(bruts), "H_positifs": len(retenus),
            "TRT": sig.effectifs_trt(enregistrement), "SST": annotations}


def preparer_donnees():
    """Lit le train et la collecte, prépare les plis. Ne retourne rien.

    Seules les lignes du split train sont retenues ; les termes du test ne sont jamais
    construits."""
    lignes_train = grasp.charger_lignes("train")
    collecte = sig.charger_collecte()
    termes = termes_des_lignes(lignes_train)
    DONNEES["lignes_train"] = lignes_train
    DONNEES["types"] = sorted(lignes_train)
    DONNEES["termes"] = termes
    DONNEES["bases"] = {terme: base_du_terme(collecte.get(terme)) for terme in sorted(termes)}
    DONNEES["plis"] = {graine: grille.decouper_plis(lignes_train, graine)
                       for graine in config.GRAINES_VARIANTES}


# ---------------------------------------------------------------------------
# Signature d'un terme, poids issus de la collecte
# ---------------------------------------------------------------------------

def poids_h(base, h):
    """Hyperonymes retenus et leur poids normalisé par le maximum du terme.
    Retourne symbole -> poids."""
    liste = base["H"] if h == "tous" else base["H"][:h]
    if not liste:
        return {}
    maximum = liste[0][1]
    return {config.PREFIXE_H + nom: poids / maximum for nom, poids in liste}


def statistiques_trt(termes_train):
    """Types trop fréquents et seuils de centile, sur les termes d'entraînement du pli.
    Retourne un dict {frequents, seuils}."""
    effectifs = {terme: (DONNEES["bases"][terme] or {"TRT": {}})["TRT"]
                 for terme in sorted(termes_train)}
    presence = Counter(type_relation for e in effectifs.values() for type_relation in e)
    frequents = {t for t, n in presence.items()
                 if n / len(effectifs) > config.SEUIL_TRT_FREQUENT}
    return {"frequents": frequents,
            "seuils": sig.seuils_par_type(effectifs, config.TRT_CENTILE)}


def types_trt_retenus(effectifs, trt, statistiques):
    """Applique la sélection TRT aux effectifs d'un terme. Retourne type -> effectif."""
    if trt == "aucun":
        return {}
    if trt == "tous":
        return dict(effectifs)
    if trt == "sans_frequents":
        return {t: n for t, n in effectifs.items() if t not in statistiques["frequents"]}
    if trt == "centile":
        return {t: n for t, n in effectifs.items()
                if n > statistiques["seuils"].get(t, 0)}
    raise ValueError(f"sélection TRT inconnue : {trt}")


def poids_trt(effectifs):
    """Poids log(1 + effectif) / log(1 + effectif maximal du terme). Retourne symbole -> poids."""
    if not effectifs:
        return {}
    maximum = math.log(1 + max(effectifs.values()))
    return {config.PREFIXE_TRT + t: math.log(1 + n) / maximum for t, n in effectifs.items()}


def poids_sst(annotations, sst):
    """Annotations SST retenues, poids normalisé par le maximum du terme.
    Retourne symbole -> poids."""
    if sst == "aucune":
        return {}
    retenues = {tag: poids for tag, (poids, morpho) in annotations.items()
                if not (sst == "sans_morpho" and morpho)}
    if not retenues:
        return {}
    maximum = max(retenues.values())
    return {config.PREFIXE_SST + tag: poids / maximum for tag, poids in retenues.items()}


def symbole_du_terme(terme, traitement):
    """Le terme lui-même, avec le poids 1. Retourne symbole -> poids.

    T0 sans préfixe (actuel), T1 sous la forme H:<terme>, T2 absent."""
    if traitement == "T0":
        return {terme: 1.0}
    if traitement == "T1":
        return {config.PREFIXE_H + terme: 1.0}
    if traitement == "T2":
        return {}
    raise ValueError(f"traitement du terme inconnu : {traitement}")


def signature_jdm(terme, base, cle, statistiques):
    """Signature d'un terme avec les poids de la collecte. Retourne symbole -> poids.

    Ces poids ne servent qu'aux pondérations « jdm » ; les autres n'en gardent que les
    symboles. Le symbole du terme est posé en dernier : il vaut 1, et l'emporte si un
    hyperonyme porte le même nom."""
    h, _, traitement, trt, sst, _ = cle
    signature = {}
    if base is not None:
        signature.update(poids_h(base, h))
        signature.update(poids_trt(types_trt_retenus(base["TRT"], trt, statistiques)))
        signature.update(poids_sst(base["SST"], sst))
    signature.update(symbole_du_terme(terme, traitement))
    return signature


# ---------------------------------------------------------------------------
# Pondération d'un pli
# ---------------------------------------------------------------------------

def frequences_documentaires(brutes, termes_train):
    """Nombre de termes d'entraînement portant chaque symbole. Retourne symbole -> df."""
    return Counter(symbole for terme in termes_train for symbole in brutes[terme])


def porte_les_poids(symbole, pond):
    """Dit si ce symbole reçoit le poids de la collecte sous cette pondération.
    Retourne un booléen.

    Les pondérations partielles ne pondèrent qu'un trait, reconnu à son préfixe. Le
    symbole du terme lui-même n'en porte aucun : il reste à 1, comme en binaire."""
    if pond in FAMILLE_JDM:
        return True
    prefixes = TRAITS_JDM.get(pond)
    return prefixes is not None and symbole.startswith(prefixes)


def poids_final(symbole, poids_collecte, pond, df, n_termes):
    """Poids d'un symbole selon la pondération. Retourne un flottant.

    Un symbole absent des statistiques reçoit le poids d'un symbole de df = 1."""
    facteur_jdm = poids_collecte if porte_les_poids(symbole, pond) else 1.0
    facteur_idf = math.log(n_termes / df.get(symbole, 1)) if pond in FAMILLE_IDF else 1.0
    return facteur_jdm * facteur_idf


def signatures_ponderees(termes, termes_train, cle):
    """Signatures de tous les termes d'un pli pour une configuration.
    Retourne terme -> (symbole -> poids).

    Les statistiques (df, centiles, types fréquents) ne portent que sur `termes_train`,
    qui n'a pas besoin d'être contenu dans `termes`. Les poids nuls sont retirés : un
    symbole présent partout ne discrimine rien."""
    _, pond, _, trt, _, df_min = cle
    statistiques = statistiques_trt(termes_train) if trt in ("sans_frequents", "centile") else None
    a_besoin_de_df = pond in FAMILLE_IDF or df_min > 1
    cibles = termes | termes_train if a_besoin_de_df else termes
    brutes = {terme: signature_jdm(terme, DONNEES["bases"][terme], cle, statistiques)
              for terme in cibles}
    df = frequences_documentaires(brutes, termes_train) if a_besoin_de_df else Counter()
    signatures = {}
    for terme in termes:
        signature = {}
        for symbole, poids in brutes[terme].items():
            if df_min > 1 and df.get(symbole, 0) < df_min:
                continue
            valeur = poids_final(symbole, poids, pond, df, len(termes_train))
            if valeur > 0:
                signature[symbole] = valeur
        signatures[terme] = signature
    return signatures


# ---------------------------------------------------------------------------
# Signatures retenues, hors validation croisée (utilisées par predire.py)
# ---------------------------------------------------------------------------

def completer_bases(termes, collecte):
    """Ajoute à DONNEES["bases"] les termes qui n'y sont pas. Ne retourne rien."""
    for terme in termes - set(DONNEES["bases"]):
        DONNEES["bases"][terme] = base_du_terme(collecte.get(terme))


def signatures_du_corpus(cle):
    """Signatures de tous les termes du corpus pour une configuration, en mémoire.
    Retourne terme -> (symbole -> poids).

    Les statistiques éventuelles (idf, centiles) ne portent que sur les termes
    d'entraînement. Suppose preparer_donnees() déjà appelée."""
    corpus, _ = sig.charger_corpus()
    termes = sig.termes_du_corpus(corpus) | DONNEES["termes"]
    completer_bases(termes, sig.charger_collecte())
    return signatures_ponderees(termes, DONNEES["termes"], cle)


def signature_d_un_terme(terme, enregistrement, cle):
    """Signature d'un terme quelconque, d'après son enregistrement de collecte.
    Retourne symbole -> poids.

    Sert aux termes absents du corpus, interrogés à la volée. Un terme absent de JDM
    reçoit la signature réduite à son symbole, donc vide si le terme n'y figure pas."""
    DONNEES["bases"][terme] = base_du_terme(enregistrement)
    return signatures_ponderees({terme}, DONNEES["termes"], cle)[terme]


def arbres_retenus(signatures):
    """Apprend les quinze arbres sur les 750 exemples d'entraînement avec ces signatures.
    Retourne (nœuds, racines)."""
    noeuds, racines, _ = grasp.construire_foret(
        feuilles_ponderees(DONNEES["lignes_train"], signatures), "somme")
    return noeuds, racines


# ---------------------------------------------------------------------------
# Un pli, une configuration
# ---------------------------------------------------------------------------

def feuilles_ponderees(lignes_par_type, signatures):
    """Une feuille par exemple d'entraînement. Retourne relation -> liste de dicts."""
    return {relation: [{"syntagme": ligne["syntagme"], "sL": signatures[ligne["A"]],
                        "sR": signatures[ligne["B"]]} for ligne in lignes]
            for relation, lignes in sorted(lignes_par_type.items())}


def predire_validation(validation, signatures, noeuds, racines):
    """Classe les exemples de validation par descente. Retourne une liste de dicts."""
    predictions = []
    for ligne in validation:
        resultat = classify.classer_par_descente(signatures[ligne["A"]],
                                                 signatures[ligne["B"]], noeuds, racines)
        gagnante = resultat["gagnante"]
        arret = noeuds[gagnante["arret"]]
        predictions.append({"attendu": ligne["rt"], "predit": gagnante["rt"],
                            "correct": gagnante["rt"] == ligne["rt"],
                            "racine": arret["profondeur"] == 0,
                            "interne": not grasp.est_feuille(arret),
                            "profondeur": arret["profondeur"]})
    return predictions


def tache(arguments):
    """Évalue une configuration sur un pli. Retourne un dict de mesures."""
    cle, graine, pli = arguments
    debut = time.perf_counter()
    apprentissage, validation = grille.separer(DONNEES["lignes_train"],
                                               DONNEES["plis"][graine], pli)
    termes_train = termes_des_lignes(apprentissage)
    termes = termes_train | {l["A"] for l in validation} | {l["B"] for l in validation}
    signatures = signatures_ponderees(termes, termes_train, cle)
    noeuds, racines, _ = grasp.construire_foret(
        feuilles_ponderees(apprentissage, signatures), "somme")
    predictions = predire_validation(validation, signatures, noeuds, racines)
    evaluation = classify.evaluer(predictions, DONNEES["types"])
    return {"cle": cle_json(cle), "graine": graine, "pli": pli,
            "f1": evaluation["f1"],
            "f1_types": {t: d["f1"] for t, d in evaluation["par_type"].items()},
            "racine": sum(p["racine"] for p in predictions) / len(predictions),
            "internes": sum(p["interne"] for p in predictions),
            "profondeur": statistics.fmean(p["profondeur"] for p in predictions),
            "taille_mediane": statistics.median(len(signatures[t]) for t in termes_train),
            "duree": time.perf_counter() - debut}


# ---------------------------------------------------------------------------
# Exécution parallèle et cache disque
# ---------------------------------------------------------------------------

def charger_cache():
    """Relit les mesures déjà calculées. Retourne cle_json -> liste de mesures."""
    if not config.FICHIER_MESURES_VARIANTES.exists():
        return {}
    return json.loads(config.FICHIER_MESURES_VARIANTES.read_text(encoding="utf-8"))


def ecrire_cache(cache):
    """Enregistre les mesures. Ne retourne rien."""
    config.DOSSIER_SIGNATURES_VARIANTES.mkdir(parents=True, exist_ok=True)
    with open(config.FICHIER_MESURES_VARIANTES, "w", encoding="utf-8", newline="") as f:
        json.dump(cache, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")


def nombre_de_processus(demande):
    """Nombre de processus à lancer. Retourne un entier."""
    if demande:
        return demande
    if config.PROCESSUS_VARIANTES:
        return config.PROCESSUS_VARIANTES
    return max(1, min(os.cpu_count() or 1, config.PROCESSUS_MAXIMUM))


def taches_manquantes(cles, cache):
    """Toutes les (configuration, graine, pli) pas encore mesurées. Retourne une liste."""
    return [(cle, graine, pli) for cle in cles if cle_json(cle) not in cache
            for graine in config.GRAINES_VARIANTES for pli in range(config.GRILLE_PLIS)]


def contexte_parallele():
    """Contexte multiprocessing utilisable, ou None s'il faut calculer en séquentiel.

    Les processus fils héritent DONNEES par « fork ». Là où fork n'existe pas (Windows),
    « spawn » les ferait repartir d'un module vide : on calcule dans ce processus."""
    try:
        return multiprocessing.get_context("fork")
    except ValueError:
        return None


def mesures_calculees(a_faire, processus):
    """Itère les mesures des tâches, en parallèle si la plateforme le permet."""
    contexte = contexte_parallele() if processus > 1 else None
    if contexte is None:
        yield from map(tache, a_faire)
        return
    with contexte.Pool(processus) as groupe:
        yield from groupe.imap_unordered(tache, a_faire)


def executer(cles, cache, processus):
    """Mesure les configurations absentes du cache, en parallèle. Ne retourne rien.

    Une configuration n'entre au cache que quand ses 15 mesures sont là, rangées par
    (graine, pli) : les différences appariées supposent cet ordre."""
    a_faire = taches_manquantes(cles, cache)
    if not a_faire:
        return
    if processus == 0:
        raise SystemExit(f"Mesures absentes du cache ({len(a_faire)}) : lancer sans "
                         "--rapport-seulement.")
    if processus > 1 and contexte_parallele() is None:
        print(f"  fork indisponible : {len(a_faire)} mesures en séquentiel.", flush=True)
    par_cle = {}
    debut = time.perf_counter()
    attendues = config.GRILLE_PLIS * len(config.GRAINES_VARIANTES)
    for mesure in mesures_calculees(a_faire, processus):
        lot = par_cle.setdefault(mesure["cle"], [])
        lot.append(mesure)
        if len(lot) == attendues:
            cache[mesure["cle"]] = sorted(lot, key=lambda m: (m["graine"], m["pli"]))
            ecrire_cache(cache)
            print(f"  {mesure['cle']:<45s} F1 "
                  f"{grasp.fr(statistics.fmean(m['f1'] for m in lot))}"
                  f"   ({grasp.fr(time.perf_counter() - debut, 0)} s écoulées)",
                  flush=True)


def mesures_de(cle, cache):
    """Les 15 mesures d'une configuration, ordre (graine, pli). Retourne une liste."""
    return cache[cle_json(cle)]


# ---------------------------------------------------------------------------
# Statistiques appariées et règle de choix
# ---------------------------------------------------------------------------

def liste_f1(cle, cache):
    """Les 15 F1 d'une configuration. Retourne une liste."""
    return [m["f1"] for m in mesures_de(cle, cache)]


def moyenne_et_ecart(valeurs):
    """Moyenne et écart-type de l'échantillon (n − 1). Retourne un couple."""
    return statistics.fmean(valeurs), statistics.stdev(valeurs)


def differences(cle, reference, cache):
    """Différences de F1 pli par pli entre une configuration et une autre.
    Retourne une liste."""
    return [a - b for a, b in zip(liste_f1(cle, cache), liste_f1(reference, cache))]


def bat_la_reference(cle, reference, cache):
    """Dit si la différence moyenne dépasse son écart-type. Retourne un booléen."""
    moyenne, ecart = moyenne_et_ecart(differences(cle, reference, cache))
    return moyenne > ecart


def indistinguable(cle, meilleur, cache):
    """Dit si une configuration reste à un écart-type de la meilleure, en différences
    appariées. Retourne un booléen."""
    moyenne, ecart = moyenne_et_ecart(differences(meilleur, cle, cache))
    return moyenne <= ecart


def retenir(candidats, cache, rang):
    """Applique la règle de choix : la plus simple parmi celles qui ne se distinguent pas
    de la meilleure. Retourne (retenue, meilleure, indistinguables).

    `rang` donne à chaque configuration son rang de complexité, le plus petit étant le
    plus simple ; à rang égal, le meilleur F1 moyen."""
    f1 = {cle: statistics.fmean(liste_f1(cle, cache)) for cle in candidats}
    meilleure = max(candidats, key=lambda cle: (f1[cle], -candidats.index(cle)))
    proches = [cle for cle in candidats
               if cle == meilleure or indistinguable(cle, meilleure, cache)]
    retenue = min(proches, key=lambda cle: (rang(cle), -f1[cle]))
    return retenue, meilleure, proches


def rang_terme(cle):
    """Complexité du traitement du terme, dans l'ordre de config.VARIANTES_TERME."""
    return config.VARIANTES_TERME.index(cle[2])


def rang_h_pond(cle):
    """Complexité du couple (nombre d'hyperonymes, pondération). Retourne un couple."""
    return (config.VARIANTES_H.index(cle[0]), config.VARIANTES_PONDERATIONS.index(cle[1]))


def rang_selection(cle):
    """Complexité de la sélection TRT et SST : 0 pour le réglage actuel. Retourne un entier."""
    return config.VARIANTES_TRT.index(cle[3]) + config.VARIANTES_SST.index(cle[4])


def rang_df(cle):
    """Complexité du filtre de fréquence : sans filtre d'abord. Retourne un entier."""
    return config.VARIANTES_DF_MIN.index(cle[5])


# ---------------------------------------------------------------------------
# Les étapes
# ---------------------------------------------------------------------------

def etape_0(cache, processus):
    """Compare les trois traitements du terme. Retourne un dict de l'étape."""
    reference = cle_de(config.REFERENCE_VARIANTES)
    candidats = [variante(reference, terme=t) for t in ("T0", "T1", "T2")]
    executer(candidats, cache, processus)
    retenue, meilleure, proches = retenir(candidats, cache, rang_terme)
    return {"reference": reference, "candidats": candidats, "retenue": retenue,
            "meilleure": meilleure, "proches": proches}


def etape_1(cache, processus, terme):
    """Grille nombre d'hyperonymes × pondération. Retourne un dict de l'étape."""
    reference = variante(cle_de(config.REFERENCE_VARIANTES), terme=terme)
    candidats = [variante(reference, h=h, pond=pond)
                 for h in config.VARIANTES_H for pond in config.VARIANTES_PONDERATIONS]
    executer(candidats, cache, processus)
    retenue, meilleure, proches = retenir(candidats, cache, rang_h_pond)
    return {"reference": reference, "candidats": candidats, "retenue": retenue,
            "meilleure": meilleure, "proches": proches}


def etape_1_traits(cache, processus, reference):
    """Décompose le gain de la pondération trait par trait. Retourne un dict de l'étape.

    Lecture seule : ces configurations ne concourent pas au choix, qui reste celui de
    l'étape 1. On mesure, contre la même référence binaire et sur les mêmes plis, ce que
    chaque trait pondéré apporte seul, puis les trois ensemble."""
    candidats = [reference]
    candidats += [variante(reference, pond=pond)
                  for pond in config.VARIANTES_PONDERATIONS_PAR_TRAIT]
    candidats.append(variante(reference, pond="jdm"))
    executer(candidats, cache, processus)
    return {"reference": reference, "candidats": candidats}


def etape_2(cache, processus, point_de_depart):
    """Fait varier TRT puis SST, un paramètre à la fois. Retourne un dict de l'étape."""
    reference = point_de_depart
    candidats = [reference]
    candidats += [variante(reference, trt=t) for t in config.VARIANTES_TRT[1:]]
    candidats += [variante(reference, sst=s) for s in config.VARIANTES_SST[1:]]
    executer(candidats, cache, processus)
    retenue, meilleure, proches = retenir(candidats, cache, rang_selection)
    return {"reference": reference, "candidats": candidats, "retenue": retenue,
            "meilleure": meilleure, "proches": proches}


def base_de_l_etape_3(retenue_2, etape_1_, cache):
    """Configuration sur laquelle porte le test de fréquence minimale. Retourne un dict.

    Le test ne concerne que les pondérations idf. Si la configuration retenue en est une,
    c'est elle ; sinon on teste la meilleure configuration idf de l'étape 1, et le résultat
    est un test complémentaire qui ne change pas la configuration finale."""
    if retenue_2[1] in FAMILLE_IDF:
        return {"cle": retenue_2, "sur_retenue": True}
    idf = [cle for cle in etape_1_["candidats"] if cle[1] in FAMILLE_IDF]
    meilleure = max(idf, key=lambda cle: statistics.fmean(liste_f1(cle, cache)))
    return {"cle": variante(meilleure, trt=retenue_2[3], sst=retenue_2[4]),
            "sur_retenue": False}


def etape_3(cache, processus, base):
    """Compare aucun seuil et df ≥ 2. Retourne un dict de l'étape."""
    reference = variante(base["cle"], df_min=config.VARIANTES_DF_MIN[0])
    candidats = [variante(reference, df_min=d) for d in config.VARIANTES_DF_MIN]
    executer(candidats, cache, processus)
    retenue, meilleure, proches = retenir(candidats, cache, rang_df)
    return {"reference": reference, "candidats": candidats, "retenue": retenue,
            "meilleure": meilleure, "proches": proches,
            "sur_retenue": base["sur_retenue"]}


def enchainer(cache, processus):
    """Exécute les quatre étapes en enchaînant leurs choix. Retourne un dict des étapes."""
    etapes = {}
    print("Étape 0 — traitement du terme", flush=True)
    etapes[0] = etape_0(cache, processus)
    print("Étape 1 — hyperonymes × pondération", flush=True)
    etapes[1] = etape_1(cache, processus, etapes[0]["retenue"][2])
    print("Étape 1 bis — pondération trait par trait", flush=True)
    etapes["traits"] = etape_1_traits(cache, processus, etapes[1]["reference"])
    print("Étape 2 — sélection TRT et SST", flush=True)
    etapes[2] = etape_2(cache, processus, etapes[1]["retenue"])
    print("Étape 3 — fréquence minimale", flush=True)
    etapes[3] = etape_3(cache, processus,
                        base_de_l_etape_3(etapes[2]["retenue"], etapes[1], cache))
    etapes["finale"] = (etapes[3]["retenue"] if etapes[3]["sur_retenue"]
                        else etapes[2]["retenue"])
    return etapes


# ---------------------------------------------------------------------------
# Diagnostic de l'étape 0 : le symbole du terme
# ---------------------------------------------------------------------------

def diagnostic_terme():
    """Le symbole non préfixé d'un terme apparaît-il chez un AUTRE terme ? Retourne un dict.

    Compte sur les signatures actuelles (lues, jamais écrites), restreintes aux termes
    d'entraînement. Compte aussi ce que T1 rendrait possible : des termes dont le symbole
    H:<terme> figure parmi les hyperonymes d'un autre."""
    brut = json.loads(config.FICHIER_SIGNATURES.read_text(encoding="utf-8"))
    termes = sorted(DONNEES["termes"])
    signatures = {terme: set(brut[terme]) for terme in termes if terme in brut}
    porteurs = Counter()
    for terme, symboles in signatures.items():
        for symbole in symboles:
            porteurs[symbole] += 1
    sans_prefixe = sum(porteurs[terme] - (1 if terme in signatures[terme] else 0)
                       for terme in signatures)
    en_h = {terme: porteurs.get(config.PREFIXE_H + terme, 0) for terme in signatures}
    return {"termes": len(signatures), "sans_prefixe": sans_prefixe,
            "termes_h": sum(1 for n in en_h.values() if n),
            "occurrences_h": sum(en_h.values()),
            "maximum_h": max(en_h.items(), key=lambda c: (c[1], c[0])),
            "signatures": signatures}


def coherence_reference(diagnostic):
    """Compare la reconstruction de la référence aux signatures du fichier.
    Retourne (termes identiques, termes comparés)."""
    reference = cle_de(config.REFERENCE_VARIANTES)
    termes = sorted(diagnostic["signatures"])
    reconstruites = signatures_ponderees(termes, set(termes), reference)
    identiques = sum(1 for terme in termes
                     if set(reconstruites[terme]) == diagnostic["signatures"][terme])
    return identiques, len(termes)


def distribution_hyperonymes():
    """Nombre d'hyperonymes par terme : min, quartiles, médiane, max. Retourne un dict."""
    bases = [b for b in DONNEES["bases"].values() if b is not None]
    resultat = {}
    for nom, valeurs in (("bruts", [b["H_bruts"] for b in bases]),
                         ("de poids > 0", [b["H_positifs"] for b in bases]),
                         ("après fusion des doublons", [len(b["H"]) for b in bases])):
        resultat[nom] = {"min": min(valeurs), "q1": sig.centile(valeurs, 0.25),
                         "mediane": statistics.median(valeurs),
                         "q3": sig.centile(valeurs, 0.75), "max": max(valeurs)}
    fusionnes = [len(b["H"]) for b in bases]
    resultat["au_dela"] = {h: sum(1 for n in fusionnes if n > h)
                           for h in config.VARIANTES_H if h != "tous"}
    resultat["termes"] = len(bases)
    resultat["absents"] = len(DONNEES["bases"]) - len(bases)
    return resultat


# ---------------------------------------------------------------------------
# Mise en forme
# ---------------------------------------------------------------------------

fr, pct, tableau = grasp.fr, grasp.pct, grasp.tableau


def f1_moyen(cle, cache):
    """F1 moyen ± écart-type sur les 15 mesures. Retourne une chaîne."""
    moyenne, ecart = moyenne_et_ecart(liste_f1(cle, cache))
    return f"{fr(moyenne)} ± {fr(ecart)}"


def diff_texte(cle, reference, cache):
    """Différence appariée moyenne ± écart-type, avec son verdict. Retourne une chaîne."""
    if cle == reference:
        return "—"
    moyenne, ecart = moyenne_et_ecart(differences(cle, reference, cache))
    signe = "+" if moyenne > 0 else ("−" if moyenne < 0 else "")
    verdict = " **bat**" if moyenne > ecart else ""
    return f"{signe}{fr(abs(moyenne))} ± {fr(ecart)}{verdict}"


def taille_et_duree(cle, cache):
    """Taille médiane des signatures et durée cumulée. Retourne un couple de chaînes."""
    mesures = mesures_de(cle, cache)
    taille = statistics.fmean(m["taille_mediane"] for m in mesures)
    return fr(taille, 0), f"{fr(sum(m['duree'] for m in mesures), 0)} s"


def ligne_de_tableau(etiquettes, cle, reference, cache, retenue):
    """Une ligne de tableau d'étape. Retourne une liste de cellules."""
    taille, duree = taille_et_duree(cle, cache)
    marque = " ← **retenue**" if cle == retenue else ""
    return (etiquettes + [f1_moyen(cle, cache) + marque,
                          diff_texte(cle, reference, cache), taille, duree])


def phrase_de_choix(etape, decrire):
    """Annonce la configuration retenue et pourquoi. Retourne une chaîne."""
    n_proches = len(etape["proches"])
    meilleure = etape["meilleure"]
    if n_proches == 1:
        pourquoi = ("Aucune autre configuration ne reste à un écart-type de la meilleure : "
                    "elle est retenue sur son seul score.")
    else:
        pourquoi = (f"{n_proches} configurations ne se distinguent pas de la meilleure "
                    "(différence appariée moyenne ≤ son écart-type) ; on retient la plus "
                    "simple d'entre elles.")
    return (f"**Retenue : {decrire(etape['retenue'])}.** Meilleur F1 moyen : "
            f"{decrire(meilleure)}. {pourquoi}")


def en_tete_etape(reference):
    """Rappel de la référence d'une étape. Retourne une chaîne."""
    return (f"Référence de l'étape : `{libelle(reference)}`. « bat » = différence moyenne "
            "supérieure à son écart-type, sur 15 différences appariées.")


# ---------------------------------------------------------------------------
# Rapport : une fonction par section
# ---------------------------------------------------------------------------

def section_dispositif(etapes, cache, coherence):
    """Protocole et contrôle de cohérence. Retourne des lignes."""
    reference = etapes[0]["reference"]
    identiques, comparees = coherence
    seed = config.GRAINES_VARIANTES[0]
    f1_seed = [m["f1"] for m in mesures_de(reference, cache) if m["graine"] == seed]
    return ["# Variantes de construction des signatures", "",
            "Étude en validation croisée sur l'entraînement seul, méthode figée "
            "(somme · arbre · descente). **Ce script ne lit pas le test** : tout ce qui "
            "suit est mesuré sur les 750 exemples d'entraînement. Le test a été lu "
            "ensuite, une seule fois, pour la seule configuration retenue "
            "(`rapport_final_signatures.md`) ; la § 3.1 a été ajoutée après cette "
            "lecture et n'a donc pas pu la guider.", "",
            "## 0. Protocole", "",
            f"- **{config.GRILLE_PLIS} plis stratifiés par type**, répétés avec les graines "
            f"{', '.join(str(g) for g in config.GRAINES_VARIANTES)} : "
            f"{config.GRILLE_PLIS * len(config.GRAINES_VARIANTES)} mesures de F1 par "
            "configuration, toutes évaluées sur les mêmes plis.",
            "- **Différences appariées** pli par pli à la référence de chaque étape. Une "
            "configuration ne bat la référence que si la différence moyenne dépasse son "
            "écart-type.",
            "- **Statistiques tirées des données** (fréquences documentaires, centiles TRT, "
            "types trop fréquents) : calculées sur les termes d'entraînement du pli "
            "seulement, jamais sur les exemples de validation.",
            "- **Pondération** : un côté est un vecteur de poids réels, un nœud fusionné la "
            "somme de ceux de ses enfants, le cosinus se calcule sur les vecteurs. "
            "L'exemple à classer utilise les mêmes poids. Un symbole absent des "
            "statistiques d'idf reçoit le poids d'un symbole de df = 1 ; un poids nul "
            "(symbole présent chez tous les termes) retire le symbole.",
            "- **jdm** : H = poids de l'hyperonyme / poids maximal des H retenus du terme ; "
            "SST = poids / poids maximal des SST retenus ; TRT = log(1 + effectif) / "
            "log(1 + effectif maximal des types retenus) ; le terme lui-même vaut 1.",
            "- **Pondérations partielles** (`jdm_H`, `jdm_TRT`, `jdm_SST`) : seul le trait "
            "nommé reçoit ces poids, les deux autres restent à 1. Elles servent à lire le "
            "gain trait par trait (§ 3.1) et ne concourent pas au choix.",
            "- **Règle de choix** : la plus simple parmi les configurations qui ne se "
            "distinguent pas de la meilleure (différence appariée moyenne ≤ son "
            "écart-type). Complexité : moins d'hyperonymes < plus, puis binaire < idf < "
            "jdm < jdm×idf ; pour le terme, absent < sans préfixe < H: ; pour TRT et SST, "
            "réglage actuel < aucun < sélections plus élaborées ; sans filtre < avec filtre.",
            "- **Limite** : les 15 mesures ne sont pas indépendantes (les trois "
            "répétitions rebattent les mêmes 750 exemples), donc l'écart-type des "
            "différences sous-estime l'incertitude réelle. Et choisir la meilleure de "
            "plusieurs dizaines de configurations sur ces mêmes mesures est optimiste.",
            f"- **Contrôle** : la référence `{libelle(reference)}` reconstruite ici "
            f"donne, sur la seule graine {seed}, un F1 moyen de {fr(statistics.fmean(f1_seed))} "
            f"(`rapport_grille.md` : {fr(config.F1_REFERENCE_GRILLE)}) ; ses signatures "
            f"sont identiques à `data/signatures/` pour {identiques} termes sur {comparees}.",
            ""]


def section_etape_0(etape, diagnostic, cache):
    """Diagnostic et comparaison du terme. Retourne des lignes."""
    noms = {"T0": "T0 — sans préfixe (actuel)", "T1": "T1 — `H:<terme>`",
            "T2": "T2 — absent"}
    corps = [ligne_de_tableau([noms[c[2]]], c, etape["reference"], cache, etape["retenue"])
             for c in etape["candidats"]]
    maxi = diagnostic["maximum_h"]
    return ["## 1. Étape 0 — le symbole du terme", "",
            "Les hyperonymes portent le préfixe `H:`, le terme lui-même est ajouté sans "
            "préfixe : la signature de « chêne » contient `H:arbre`, celle d'« arbre » "
            "contient `arbre`, et ils ne s'intersectent jamais. Le but du papier "
            "(section 3), capturer les hyponymes, n'est alors pas atteint.", "",
            f"**Diagnostic** sur les {diagnostic['termes']} termes d'entraînement : le "
            f"symbole non préfixé d'un terme apparaît **{diagnostic['sans_prefixe']} fois** "
            "dans la signature d'un autre terme. "
            + ("C'est bien « jamais », comme attendu."
               if diagnostic["sans_prefixe"] == 0 else "Ce n'est pas « jamais »."),
            f"Sous la forme `H:<terme>`, en revanche, le symbole de "
            f"{diagnostic['termes_h']} termes ({pct(diagnostic['termes_h'] / diagnostic['termes'], 0)}) "
            f"figure parmi les hyperonymes d'au moins un autre terme, "
            f"{diagnostic['occurrences_h']} occurrences en tout, jusqu'à {maxi[1]} pour "
            f"« {maxi[0]} ». T1 rend donc l'intersection possible.", "",
            en_tete_etape(etape["reference"]), ""] + tableau(
                ["traitement", "F1 moyen ± é.-t.", "différence à T0 ± é.-t.",
                 "taille médiane", "durée"], corps) + [
            "", phrase_de_choix(etape, lambda c: noms[c[2]].split(" — ")[0]), ""]


def section_distribution(distribution):
    """Distribution du nombre d'hyperonymes par terme. Retourne des lignes."""
    corps = []
    for nom in ("bruts", "de poids > 0", "après fusion des doublons"):
        d = distribution[nom]
        corps.append([nom, d["min"], fr(d["q1"], 1), fr(d["mediane"], 1),
                      fr(d["q3"], 1), d["max"]])
    au_dela = distribution["au_dela"]
    n = distribution["termes"]
    return (["## 2. Nombre d'hyperonymes par terme", "",
             f"Sur les {n} termes d'entraînement présents dans JDM "
             f"({distribution['absents']} absents, réduits à eux-mêmes).", ""]
            + tableau(["hyperonymes", "min", "Q1", "médiane", "Q3", "max"], corps)
            + ["", "Nombre de termes qui ont plus de N hyperonymes (après fusion des "
               "doublons), c'est-à-dire ceux qu'une coupure à N tronque : "
               + ", ".join(f"N = {h} : **{k}** ({pct(k / n, 0)})" for h, k in au_dela.items())
               + f". « tous » ne diffère de « 200 » que pour {au_dela[200]} termes : "
               "au-delà de ce nombre, les deux coïncident.", ""])


def section_etape_1(etape, cache):
    """Grille hyperonymes × pondération. Retourne des lignes."""
    corps = [ligne_de_tableau([c[0], c[1]], c, etape["reference"], cache, etape["retenue"])
             for c in etape["candidats"]]
    return ["## 3. Étape 1 — hyperonymes × pondération", "",
            "TRT et SST restent aux réglages actuels ; le terme est traité selon "
            f"l'étape 0 ({etape['reference'][2]}). 20 configurations.", "",
            en_tete_etape(etape["reference"]), ""] + tableau(
                ["H", "pondération", "F1 moyen ± é.-t.", "différence ± é.-t.",
                 "taille médiane", "durée"], corps) + [
            "", phrase_de_choix(etape, lambda c: f"H {c[0]}, {c[1]}"), ""]


NOMS_TRAITS = {"binaire": "aucun (référence)", "jdm_H": "H seul", "jdm_TRT": "TRT seul",
               "jdm_SST": "SST seul", "jdm": "les trois (`jdm`)"}


def gains_par_trait(etape, cache):
    """Gain apparié moyen de chaque pondération sur la référence binaire.
    Retourne pondération -> flottant."""
    return {cle[1]: moyenne_et_ecart(differences(cle, etape["reference"], cache))[0]
            for cle in etape["candidats"] if cle != etape["reference"]}


def section_traits(etape, retenue_1, cache):
    """Ce que chaque trait pondéré apporte seul. Retourne des lignes."""
    reference = etape["reference"]
    corps = [ligne_de_tableau([NOMS_TRAITS[c[1]]], c, reference, cache, retenue_1)
             for c in etape["candidats"]]
    gains = gains_par_trait(etape, cache)
    parties = config.VARIANTES_PONDERATIONS_PAR_TRAIT
    somme = sum(gains[pond] for pond in parties)
    tout = variante(reference, pond="jdm")
    battants = [NOMS_TRAITS[pond] for pond in parties
                if bat_la_reference(variante(reference, pond=pond), reference, cache)]
    sobres = [NOMS_TRAITS[pond] for pond in parties
              if indistinguable(variante(reference, pond=pond), tout, cache)]
    lignes = ["### 3.1 Lecture par trait", "",
              "La pondération `jdm` touche les trois traits à la fois. Pour savoir lequel "
              "porte le gain, on ne pondère qu'un trait et on laisse les deux autres à 1, "
              "au nombre d'hyperonymes retenu à l'étape 1. **Ces configurations ne "
              "concourent pas au choix** : elles répondent à une question de lecture, pas "
              "de sélection.", "",
              en_tete_etape(reference), ""]
    lignes += tableau(["trait pondéré", "F1 moyen ± é.-t.", "différence ± é.-t.",
                       "taille médiane", "durée"], corps)
    lignes += ["", f"- **Seul à battre la référence** : "
               + (", ".join(battants) if battants else
                  "aucun trait pris seul ne la bat au sens de la règle") + ".",
               f"- **Le tout contre la somme de ses parties** : les trois gains séparés "
               f"valent {classify.ecart_signe(gains['jdm_H'])} (H), "
               f"{classify.ecart_signe(gains['jdm_TRT'])} (TRT) et "
               f"{classify.ecart_signe(gains['jdm_SST'])} (SST), soit "
               f"{classify.ecart_signe(somme)} au total, contre "
               f"{classify.ecart_signe(gains['jdm'])} pour les trois ensemble : "
               + ("les traits pondérés se renforcent, le tout dépasse la somme."
                  if gains["jdm"] > somme + 1e-9 else
                  "les traits pondérés se recouvrent, le tout reste sous la somme.")]
    if sobres:
        lignes += [f"- **Réserve de méthode** : {', '.join(sobres)} ne se distingue pas de "
                   "`jdm` en différences appariées. La règle de simplicité du projet, "
                   "appliquée ici, préférerait donc une pondération d'un seul trait. Elle "
                   "ne l'a pas été : l'étape 1 avait déjà tranché et le test a déjà été "
                   "lu pour `jdm` (`rapport_final_signatures.md`). Le noter plutôt que le "
                   "corriger après coup est la lecture honnête."]
        intransitifs = [NOMS_TRAITS[pond] for pond in parties
                        if indistinguable(variante(reference, pond=pond), tout, cache)
                        and not bat_la_reference(variante(reference, pond=pond),
                                                 reference, cache)]
        if intransitifs:
            lignes += ["- **La règle est ici intransitive**, et c'est son principal "
                       f"enseignement : `jdm` bat la référence, {', '.join(intransitifs)} "
                       "ne la bat pas, et `jdm` ne se distingue pourtant pas de "
                       f"{', '.join(intransitifs)}. Trois comparaisons incompatibles entre "
                       "elles signalent un manque de puissance, pas un classement : avec "
                       "15 mesures non indépendantes et des écarts de l'ordre de 0,03, "
                       "« moyenne > écart-type » ne départage pas ces configurations."]
    else:
        lignes += ["- Aucune pondération d'un seul trait ne tient le score de `jdm` : "
                   "pondérer les trois traits est nécessaire, et la configuration retenue "
                   "à l'étape 1 n'est pas remise en cause."]
    return lignes + [""]


def section_etape_2(etape, cache):
    """Sélection TRT et SST. Retourne des lignes."""
    corps = []
    for c in etape["candidats"]:
        parametre = ("réglage actuel" if c == etape["reference"]
                     else (f"TRT {c[3]}" if c[3] != etape["reference"][3] else f"SST {c[4]}"))
        corps.append(ligne_de_tableau([parametre], c, etape["reference"], cache,
                                      etape["retenue"]))
    return ["## 4. Étape 2 — sélection TRT et SST", "",
            "Un paramètre à la fois, autour du couple (H, pondération) retenu à l'étape 1. "
            "Les deux diagnostics antérieurs avaient été faits en union : ici on mesure "
            "sans les supposer.", "",
            en_tete_etape(etape["reference"]), ""] + tableau(
                ["paramètre changé", "F1 moyen ± é.-t.", "différence ± é.-t.",
                 "taille médiane", "durée"], corps) + [
            "", phrase_de_choix(etape, lambda c: f"TRT {c[3]}, SST {c[4]}"), ""]


def section_etape_3(etape, cache):
    """Seuil de fréquence minimale. Retourne des lignes."""
    corps = [ligne_de_tableau([f"df ≥ {c[5]}" if c[5] > 1 else "aucun seuil"], c,
                              etape["reference"], cache, etape["retenue"])
             for c in etape["candidats"]]
    lignes = ["## 5. Étape 3 — seuil de fréquence minimale", "",
              "Un symbole porté par un seul terme d'entraînement reçoit le poids idf "
              "maximal mais ne peut jamais généraliser à un autre terme. On compare, "
              "au meilleur réglage idf, aucun seuil et df ≥ 2.", ""]
    if not etape["sur_retenue"]:
        lignes += ["**La configuration retenue à l'étape 2 n'est pas pondérée par idf** : "
                   "le test porte donc sur la meilleure configuration idf de l'étape 1 "
                   f"(`{libelle(etape['reference'])}`) et **ne change pas la configuration "
                   "finale**.", ""]
    lignes += [en_tete_etape(etape["reference"]), ""] + tableau(
        ["filtre", "F1 moyen ± é.-t.", "différence ± é.-t.", "taille médiane", "durée"],
        corps)
    phrase = phrase_de_choix(etape, lambda c: f"df ≥ {c[5]}" if c[5] > 1 else "aucun seuil")
    if not etape["sur_retenue"]:
        phrase = phrase.replace("**Retenue :", "**Vainqueur du test complémentaire :") \
            + " Ce résultat ne modifie pas la configuration finale."
    lignes += ["", phrase, ""]
    return lignes


def statistiques_de_descente(cle, cache):
    """Moyennes sur les 15 mesures : part des racines, profondeur, internes. Retourne un dict."""
    mesures = mesures_de(cle, cache)
    return {"racine": statistics.fmean(m["racine"] for m in mesures),
            "profondeur": statistics.fmean(m["profondeur"] for m in mesures),
            "internes": statistics.fmean(m["internes"] for m in mesures),
            "internes_total": sum(m["internes"] for m in mesures)}


def feuilles_gagnantes(cle, cache):
    """Prédictions faites par une feuille, sur les 15 mesures. Retourne un entier."""
    return sum(config.TAILLE_PLI_VALIDATION - m["internes"] for m in mesures_de(cle, cache))


def hors_racine(cle, cache):
    """Prédictions faites par un nœud interne qui n'est pas une racine, sur les 15
    mesures. Retourne un entier.

    Chaque pli de validation compte config.TAILLE_PLI_VALIDATION exemples, et la mesure
    garde la part des racines : le nombre de racines s'en déduit."""
    return sum(m["internes"] - round(m["racine"] * config.TAILLE_PLI_VALIDATION)
               for m in mesures_de(cle, cache))


def f1_par_type(cle, cache, types):
    """F1 moyen de chaque type sur les 15 mesures. Retourne type -> flottant."""
    mesures = mesures_de(cle, cache)
    return {t: statistics.fmean(m["f1_types"][t] for m in mesures) for t in types}


def section_finale(etapes, cache):
    """Configuration finale, gain, F1 par type, descente. Retourne des lignes."""
    finale, actuelle = etapes["finale"], etapes[0]["reference"]
    moyenne, ecart = moyenne_et_ecart(differences(finale, actuelle, cache))
    sd_finale = statistiques_de_descente(finale, cache)
    sd_actuelle = statistiques_de_descente(actuelle, cache)
    types = DONNEES["types"]
    p_finale, p_actuelle = f1_par_type(finale, cache, types), f1_par_type(actuelle, cache, types)
    corps = []
    for t in sorted(types, key=lambda t: -(p_finale[t] - p_actuelle[t])):
        ecart_type = p_finale[t] - p_actuelle[t]
        corps.append([f"`{t}`", fr(p_actuelle[t], 3), fr(p_finale[t], 3),
                      ("+" if ecart_type >= 0 else "−") + fr(abs(ecart_type), 3)])
    identique = finale == actuelle
    lignes = ["## 6. Configuration finale", "",
              f"**`{libelle(finale)}`**", "",
              f"- F1 moyen : **{f1_moyen(finale, cache)}**, contre "
              f"{f1_moyen(actuelle, cache)} pour la référence actuelle "
              f"(`{libelle(actuelle)}`).",
              f"- Gain apparié sur la référence actuelle : "
              + ("nul, c'est la même configuration." if identique else
                 f"**{'+' if moyenne >= 0 else '−'}{fr(abs(moyenne))} ± {fr(ecart)}**, "
                 + ("supérieur à son écart-type." if moyenne > ecart
                    else "**inférieur à son écart-type : le gain ne dépasse pas le bruit.**"))
              ]
    lignes += ["", "### 6.1 F1 par type, moyenne des 15 mesures", ""]
    lignes += tableau(["type", "référence actuelle", "configuration finale", "écart"], corps)
    lignes += ["", "### 6.2 La descente", ""]
    lignes += tableau(["", "référence actuelle", "configuration finale"],
                      [["part des prédictions faites par une racine",
                        pct(sd_actuelle["racine"]), pct(sd_finale["racine"])],
                       ["profondeur d'arrêt moyenne (racine = 0)",
                        fr(sd_actuelle["profondeur"], 2), fr(sd_finale["profondeur"], 2)],
                       ["prédictions faites par un nœud interne, racines comprises "
                        "(par pli de 150)",
                        fr(sd_actuelle["internes"], 1), fr(sd_finale["internes"], 1)],
                       ["nœuds gagnants internes **hors racine**, total sur 15 plis",
                        hors_racine(actuelle, cache), hors_racine(finale, cache)],
                       ["prédictions faites par une feuille, total sur 15 plis",
                        feuilles_gagnantes(actuelle, cache),
                        feuilles_gagnantes(finale, cache)]])
    return lignes + [""]


def f1_de(cle, cache):
    """F1 moyen d'une configuration. Retourne un flottant."""
    return statistics.fmean(liste_f1(cle, cache))


def constats_mesures(etapes, cache):
    """Ce que les tableaux établissent, en phrases chiffrées. Retourne des lignes."""
    e0, e1, e2, e3 = etapes[0], etapes[1], etapes[2], etapes[3]
    ref1 = e1["reference"]
    ecarts_terme = [moyenne_et_ecart(differences(c, e0["reference"], cache))
                    for c in e0["candidats"] if c != e0["reference"]]
    constats = [f"**Le traitement du terme ne change rien de mesurable.** T1 et T2 s'écartent "
                f"de T0 d'au plus {fr(max(abs(m) for m, _ in ecarts_terme))} de F1, sous leur "
                "écart-type. T2 est retenu par la règle de simplicité, non parce qu'il "
                "gagnerait."]
    sous = []
    for h in config.VARIANTES_H:
        binaire = f1_de(variante(ref1, h=h, pond="binaire"), cache)
        ecart_idf = f1_de(variante(ref1, h=h, pond="idf"), cache) - binaire
        ecart_jdm_idf = f1_de(variante(ref1, h=h, pond="jdm×idf"), cache) - binaire
        sous.append(f"H {h} : idf {classify.ecart_signe(ecart_idf)}, "
                    f"jdm×idf {classify.ecart_signe(ecart_jdm_idf)}")
    constats.append("**La rareté (idf) dégrade le F1 à tous les nombres d'hyperonymes**, "
                    "avec ou sans poids de la collecte. Écart à binaire, à même H : "
                    + " ; ".join(sous) + ".")
    binaire_h = [f1_de(variante(ref1, h=h, pond="binaire"), cache) for h in config.VARIANTES_H]
    jdm_h = [f1_de(variante(ref1, h=h, pond="jdm"), cache) for h in config.VARIANTES_H]
    constats.append(f"**Plus d'hyperonymes n'aide pas.** En binaire, de H {config.VARIANTES_H[0]} "
                    f"à « tous » le F1 passe de {fr(binaire_h[0])} à {fr(binaire_h[-1])} ; avec "
                    f"les poids de la collecte, de {fr(jdm_h[0])} à {fr(jdm_h[-1])}. Les poids "
                    "de la collecte amortissent la chute sans l'annuler, et le meilleur "
                    f"réglage reste à H {config.VARIANTES_H[0]}.")
    m1, e_1 = moyenne_et_ecart(differences(e1["retenue"], ref1, cache))
    constats.append(f"**Le gain de la pondération de la collecte est mince** : "
                    f"{'+' if m1 >= 0 else '−'}{fr(abs(m1))} de F1 pour un écart-type de "
                    f"{fr(e_1)}, soit {fr(m1 / e_1, 2)} écart-type. Il franchit la règle fixée "
                    "de peu.")
    traits = etapes["traits"]
    gains = gains_par_trait(traits, cache)
    parties = config.VARIANTES_PONDERATIONS_PAR_TRAIT
    somme = sum(gains[pond] for pond in parties)
    battants = [pond for pond in parties
                if bat_la_reference(variante(traits["reference"], pond=pond),
                                    traits["reference"], cache)]
    detail = ", ".join(f"{NOMS_TRAITS[pond].replace(' seul', '')} seul "
                       f"{classify.ecart_signe(gains[pond])}" for pond in parties)
    if battants:
        constats.append(
            f"**Le gain de la pondération se localise** : "
            + ", ".join(NOMS_TRAITS[pond].replace(" seul", "") for pond in battants)
            + f" bat la référence à lui seul ({detail}), contre "
            f"{classify.ecart_signe(gains['jdm'])} pour les trois ensemble.")
    else:
        constats.append(
            f"**Aucun trait pondéré n'apporte quoi que ce soit seul** : {detail}, "
            f"quand les trois ensemble valent {classify.ecart_signe(gains['jdm'])}. La "
            f"somme des parties, {classify.ecart_signe(somme)}, est de signe opposé au "
            "tout : le gain de la pondération n'est pas la propriété d'un trait mais un "
            "effet de leur conjonction, et il n'y a donc pas de version allégée à en "
            "tirer. C'est aussi le constat le plus fragile du rapport, puisque chacune "
            "de ces différences tient dans son propre écart-type.")
    aucun_trt = variante(e2["reference"], trt="aucun")
    m_trt, _ = moyenne_et_ecart(differences(aucun_trt, e2["reference"], cache))
    autres = [c for c in e2["candidats"] if c != e2["reference"] and c != aucun_trt]
    ecart_max = max(abs(moyenne_et_ecart(differences(c, e2["reference"], cache))[0])
                    for c in autres)
    constats.append(f"**TRT est indispensable, sa sélection ne l'est pas.** Retirer tout TRT "
                    f"coûte {fr(abs(m_trt))} de F1. Les {len(autres)} autres variantes de TRT ou de "
                    f"SST s'écartent d'au plus {fr(ecart_max)}, dans le bruit : les "
                    "conclusions des diagnostics en union ne se transposent pas, mais ne "
                    "sont pas non plus renversées.")
    binaire_20 = f1_de(variante(e3["reference"], pond="binaire"), cache)
    constats.append(f"**Le seuil de fréquence répare l'idf sans le rendre utile.** df ≥ 2 "
                    f"gagne {fr(f1_de(e3['candidats'][-1], cache) - f1_de(e3['reference'], cache))} "
                    f"sur l'idf sans seuil, mais reste sous le binaire à même H "
                    f"({fr(f1_de(e3['candidats'][-1], cache))} contre {fr(binaire_20)}).")
    return constats


def section_lecture(etapes, cache):
    """Lecture honnête des résultats. Retourne des lignes."""
    actuelle, finale = etapes[0]["reference"], etapes["finale"]
    battantes = []
    for numero in (0, 1, 2, 3):
        etape = etapes[numero]
        battantes += [c for c in etape["candidats"]
                      if c != etape["reference"]
                      and bat_la_reference(c, etape["reference"], cache)]
    total = sum(len(etapes[n]["candidats"]) - 1 for n in (0, 1, 2, 3))
    moyenne, ecart = moyenne_et_ecart(differences(finale, actuelle, cache))
    lignes = ["## 7. Lecture", "",
              f"- **{len(battantes)} configurations sur {total}** comparées à la référence "
              "de leur étape la battent au sens de la règle (différence moyenne > son "
              "écart-type)."]
    if finale == actuelle:
        lignes.append("- **La configuration retenue est la configuration actuelle** : "
                      "aucune variante ne la bat au-delà du bruit, ou aucune de celles qui "
                      "la battent n'a survécu à la règle de simplicité.")
    elif moyenne <= ecart:
        lignes.append(f"- **Aucun gain ne dépasse le bruit** : la configuration finale "
                      f"gagne {fr(moyenne)} de F1 en moyenne, pour un écart-type de "
                      f"{fr(ecart)}. Le mettre au crédit des signatures serait excessif.")
    else:
        lignes.append(f"- La configuration finale gagne {fr(moyenne)} de F1 en moyenne sur "
                      f"la référence actuelle, pour un écart-type de {fr(ecart)} : le gain "
                      f"dépasse le bruit selon la règle fixée, de {fr(moyenne / ecart, 2)} "
                      "écart-type seulement.")
    lignes += [f"- {constat}" for constat in constats_mesures(etapes, cache)]
    lignes += ["- **Réserves** : la règle « moyenne > écart-type » est indulgente ; les "
               "15 mesures ne sont pas indépendantes ; et la configuration finale est la "
               "meilleure d'un balayage, donc son F1 de validation croisée est optimiste. "
               "Seule l'évaluation sur le test dit ce qui en reste : elle a été faite "
               "depuis, une seule fois, et elle est dans "
               "`rapport_final_signatures.md`.", ""]
    return lignes


def section_sorties():
    """Fichiers écrits. Retourne des lignes."""
    return ["## 8. Sorties", "",
            f"- `{config.FICHIER_MESURES_VARIANTES.relative_to(config.RACINE).as_posix()}` : "
            "les 15 mesures de chaque configuration (F1, F1 par type, statistiques de "
            "descente, durée), qui permettent de reconstruire ce rapport sans rien "
            "recalculer (`--rapport-seulement`).",
            "- `data/signatures/` n'est pas touché ; les signatures variantes n'existent "
            "qu'en mémoire.", ""]


def construire_rapport(etapes, cache, diagnostic, coherence):
    """Écrit reports/rapport_signatures_variantes.md. Ne retourne rien."""
    lignes = section_dispositif(etapes, cache, coherence)
    lignes += section_etape_0(etapes[0], diagnostic, cache)
    lignes += section_distribution(distribution_hyperonymes())
    lignes += section_etape_1(etapes[1], cache)
    lignes += section_traits(etapes["traits"], etapes[1]["retenue"], cache)
    lignes += section_etape_2(etapes[2], cache)
    lignes += section_etape_3(etapes[3], cache)
    lignes += section_finale(etapes, cache)
    lignes += section_lecture(etapes, cache)
    lignes += section_sorties()
    config.FICHIER_RAPPORT_VARIANTES.write_text("\n".join(lignes), encoding="utf-8")
    print(f"Rapport : {config.FICHIER_RAPPORT_VARIANTES}", flush=True)


# ---------------------------------------------------------------------------
# Enchaînement
# ---------------------------------------------------------------------------

def main():
    analyseur = argparse.ArgumentParser(description="Variantes de signatures, sans test.")
    analyseur.add_argument("--rapport-seulement", action="store_true", dest="rapport_seulement",
                           help="reconstruit le rapport depuis le cache, sans calcul")
    analyseur.add_argument("--processus", type=int, default=0,
                           help="nombre de processus de calcul")
    options = analyseur.parse_args()

    preparer_donnees()
    print(f"Entraînement : {sum(len(l) for l in DONNEES['lignes_train'].values())} exemples, "
          f"{len(DONNEES['termes'])} termes. Test non lu.", flush=True)
    cache = charger_cache()
    processus = nombre_de_processus(options.processus)
    if options.rapport_seulement:
        processus = 0
    debut = time.perf_counter()
    etapes = enchainer(cache, processus)
    diagnostic = diagnostic_terme()
    coherence = coherence_reference(diagnostic)
    print(f"Configuration finale : {libelle(etapes['finale'])} "
          f"({grasp.fr(time.perf_counter() - debut, 0)} s)", flush=True)
    construire_rapport(etapes, cache, diagnostic, coherence)


if __name__ == "__main__":
    main()
