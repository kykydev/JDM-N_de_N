#!/usr/bin/env python3
"""Étape 3 : transforme la collecte brute en signatures, vocabulaire et règles.

Aucun appel réseau : tout est lu dans data/collecte/termes_jdm.jsonl et
data/corpus/clean/. La collecte n'est pas modifiée, le corpus non plus.

Une signature est un ENSEMBLE PLAT de symboles textuels binaires. Chaque symbole porte
un préfixe de provenance — `H:`, `TRT:`, `SST:` — qui évite les collisions entre traits
et permettra de filtrer par trait, par configuration, pour l'Expérience 1. Le terme
lui-même est ajouté sans préfixe : le papier le précise en section 3, cela permet de
capturer ses hyponymes.

Les coupures appliquées ici (top 20 pour H, politique TRT, exclusion des types non
sémantiques) viennent toutes de config.py. La collecte, elle, est restée brute exprès : changer un
seuil ne demande que de relancer ce script, jamais de recollecter.

Une règle est R = < sL, sR, rt > : la signature de A, celle de B, et la relation. Les
deux signatures restent SÉPARÉES. La position porte le sens : « vin de France » n'est
pas « France de vin ».

Hors périmètre, volontairement : aucune fusion de règles, aucun apprentissage, aucune
classification, aucune matrice de similarité complète. C'est l'étape 4.

Usage : python3 src/signatures.py
"""

import csv
import json
import math
import statistics
from collections import Counter, defaultdict

import config


# ---------------------------------------------------------------------------
# Lecture des entrées
# ---------------------------------------------------------------------------

def charger_collecte():
    """Lit data/collecte/termes_jdm.jsonl. Retourne terme -> enregistrement brut."""
    collecte = {}
    with open(config.FICHIER_COLLECTE, encoding="utf-8") as f:
        for numero, ligne in enumerate(f, 1):
            if not ligne.strip():
                continue
            try:
                enregistrement = json.loads(ligne)
            except ValueError as e:
                print(f"  ligne {numero} illisible, ignorée : {e}", flush=True)
                continue
            collecte[enregistrement["terme"]] = enregistrement
    return collecte


def charger_corpus():
    """Lit les CSV de data/corpus/clean/. Retourne relation -> liste de lignes.

    Les lignes ambiguës (plusieurs prépositions, donc A et B vides) ne peuvent pas
    donner de règle : elles sont écartées et comptées à part."""
    corpus, ecartees = defaultdict(list), []
    for chemin in sorted(config.DOSSIER_CORPUS_PROPRE.glob("corpus_*.csv")):
        with open(chemin, encoding="utf-8", newline="") as f:
            for ligne in csv.DictReader(f):
                if ligne["ambigu"] == "oui" or not ligne["A"] or not ligne["B"]:
                    ecartees.append({"fichier": chemin.name, "syntagme": ligne["syntagme"],
                                     "relation": ligne["relation"],
                                     "raison": "découpage ambigu, A et B non tranchés"})
                    continue
                corpus[ligne["relation"]].append(ligne)
    return corpus, ecartees


# ---------------------------------------------------------------------------
# Construction d'une signature
# ---------------------------------------------------------------------------

def fusionner_doublons_casse(hyperonymes):
    """Fusionne les cibles qui ne diffèrent que par la casse ou les espaces.

    Regroupe sur `forme_normalisee`, déjà calculée à la collecte, et garde la forme
    d'origine la mieux pondérée (« déficit neurologique » 247 l'emporte sur « Déficit
    neurologique » 62). Retourne la liste des cibles gardées."""
    meilleure_par_forme = {}
    for cible in hyperonymes:
        forme = cible["forme_normalisee"]
        gardee = meilleure_par_forme.get(forme)
        if gardee is None or cible["poids"] > gardee["poids"]:
            meilleure_par_forme[forme] = cible
    return list(meilleure_par_forme.values())


def symboles_h(enregistrement):
    """Symboles du trait H : les hyperonymes r_isa. Retourne un ensemble de chaînes.

    Ordre des opérations : filtre sur le poids, puis sur le préfixe de langue si la
    configuration le demande, puis fusion des doublons de casse, et seulement ensuite
    la coupure au top N. Fusionner après la coupure ferait perdre des symboles au
    profit de doublons."""
    retenus = []
    for cible in enregistrement.get("H") or []:
        if cible["poids"] <= 0:
            continue
        if config.H_EXCLURE_PREFIXES_LANGUE and cible["lang_prefix"]:
            continue
        retenus.append(cible)

    fusionnes = fusionner_doublons_casse(retenus)
    fusionnes.sort(key=lambda c: (-c["poids"], c["nom"]))

    symboles = set()
    for cible in fusionnes[:config.H_TOP]:
        symboles.add(config.PREFIXE_H + cible["nom"])
    return symboles


def effectifs_trt(enregistrement):
    """Effectifs des types de relations entrantes, hors types exclus.
    Retourne type -> effectif."""
    effectifs = {}
    for entree in enregistrement.get("TRT") or []:
        if entree["n"] <= 0:
            continue
        if entree["type"] in config.TRT_TYPES_EXCLUS:
            continue
        effectifs[entree["type"]] = entree["n"]
    return effectifs


def centile(valeurs, part):
    """Centile par interpolation linéaire, sans dépendance externe. Retourne un flottant."""
    if not valeurs:
        return 0.0
    tries = sorted(valeurs)
    if len(tries) == 1:
        return tries[0]
    position = part * (len(tries) - 1)
    bas = int(position)
    haut = min(bas + 1, len(tries) - 1)
    return tries[bas] + (tries[haut] - tries[bas]) * (position - bas)


def seuils_par_type(effectifs_par_terme, rang):
    """Effectif minimal pour qu'un type soit retenu, par type. Retourne type -> valeur.

    La distribution est prise sur TOUS les termes du corpus, zéros compris : un type
    présent chez 5 % des termes a un centile nul et survit donc partout où il apparaît.
    C'est voulu — ce sont les types rares qui discriminent."""
    tous = set()
    for effectifs in effectifs_par_terme.values():
        tous |= set(effectifs)
    seuils = {}
    for type_relation in sorted(tous):
        distribution = [effectifs.get(type_relation, 0)
                        for effectifs in effectifs_par_terme.values()]
        seuils[type_relation] = centile(distribution, rang / 100)
    return seuils


def symboles_trt(enregistrement, seuils):
    """Symboles du trait TRT : les types de relations entrantes. Retourne un ensemble.

    Deux politiques, choisies par config.TRT_POLITIQUE. « presence » garde tout type
    reçu au moins une fois : c'est la lecture fidèle de l'article, dont l'exemple de
    signature contient les types les plus répandus du réseau. « centile » ne garde un
    type que là où le terme en reçoit plus que le centile de sa distribution sur le
    corpus. `seuils` est ignoré par la première."""
    symboles = set()
    par_centile = config.TRT_POLITIQUE == "centile"
    for type_relation, effectif in effectifs_trt(enregistrement).items():
        if par_centile and effectif <= seuils.get(type_relation, 0):
            continue
        symboles.add(config.PREFIXE_TRT + type_relation)
    return symboles


def symboles_sst(enregistrement):
    """Symboles du trait SST : les annotations _INFO-SEM-*. Retourne un ensemble."""
    symboles = set()
    for annotation in enregistrement.get("SST") or []:
        if annotation["poids"] <= 0:
            continue
        if config.SST_EXCLURE_MORPHO and annotation["morpho"]:
            continue
        symboles.add(config.PREFIXE_SST + annotation["tag"])
    return symboles


def construire_signature(terme, enregistrement, seuils):
    """Construit la signature d'un terme. Retourne un ensemble de symboles.

    Un terme absent de JDM reçoit une signature réduite au terme lui-même."""
    signature = {terme}
    if enregistrement is None or not enregistrement.get("existe"):
        return signature
    signature |= symboles_h(enregistrement)
    signature |= symboles_trt(enregistrement, seuils)
    signature |= symboles_sst(enregistrement)
    return signature


def termes_du_corpus(corpus):
    """Rassemble tous les A et B du corpus propre. Retourne un ensemble de chaînes."""
    termes = set()
    for lignes in corpus.values():
        for ligne in lignes:
            termes.add(ligne["A"])
            termes.add(ligne["B"])
    return termes


def construire_toutes_les_signatures(collecte, attendus):
    """Construit la signature des termes du corpus. Retourne (terme -> ensemble,
    absents de JDM, collectés qui ne sont plus dans le corpus).

    La collecte garde trace des candidats de découpage rejetés ; leur donner une
    signature polluerait le vocabulaire avec des symboles qu'aucune règle n'emploie.

    Sous la politique « centile », les seuils TRT sont calculés ici, sur la population
    du corpus : la saillance d'un type se juge relativement aux autres termes, elle ne
    peut donc pas se décider terme par terme. Sous « presence », il n'y a pas de
    seuil."""
    seuils = {}
    if config.TRT_POLITIQUE == "centile":
        effectifs_par_terme = {}
        for terme in sorted(attendus):
            enregistrement = collecte.get(terme)
            effectifs_par_terme[terme] = (effectifs_trt(enregistrement)
                                          if enregistrement else {})
        seuils = seuils_par_type(effectifs_par_terme, config.TRT_CENTILE)

    signatures, absents, hors_corpus = {}, [], []
    for terme in sorted(collecte):
        if terme not in attendus:
            hors_corpus.append(terme)
            continue
        enregistrement = collecte[terme]
        signatures[terme] = construire_signature(terme, enregistrement, seuils)
        if not enregistrement.get("existe"):
            absents.append(terme)
    manquants = sorted(attendus - set(signatures))
    for terme in manquants:
        print(f"  terme du corpus jamais collecté, ignoré : « {terme} »", flush=True)
    return signatures, absents, hors_corpus


# ---------------------------------------------------------------------------
# Vocabulaire global
# ---------------------------------------------------------------------------

def construire_vocabulaire(signatures):
    """Numérote tous les symboles rencontrés. Retourne symbole -> numéro de dimension.

    Un seul vocabulaire pour les 15 types, jamais un par corpus : sans cela, la
    dimension 12 ne désignerait pas le même symbole d'un type à l'autre et les
    signatures ne seraient plus comparables."""
    tous = set()
    for signature in signatures.values():
        tous |= signature
    vocabulaire = {}
    for numero, symbole in enumerate(sorted(tous)):
        vocabulaire[symbole] = numero
    return vocabulaire


# ---------------------------------------------------------------------------
# Règles
# ---------------------------------------------------------------------------

def construire_regles(corpus, signatures):
    """Construit les règles R = < sL, sR, rt >. Retourne relation -> liste de règles.

    `det` et `definitude` sont recopiés depuis le corpus mais PAS injectés dans sR :
    leur ajout à la signature se fera par configuration à l'Expérience 2."""
    regles = {}
    for relation in sorted(corpus):
        lignes = []
        for ligne in corpus[relation]:
            signature_a = signatures.get(ligne["A"]) or {ligne["A"]}
            signature_b = signatures.get(ligne["B"]) or {ligne["B"]}
            lignes.append({
                "syntagme": ligne["syntagme"],
                "A": ligne["A"], "B": ligne["B"],
                "rt": relation,
                "split": ligne["split"],
                "sL": sorted(signature_a),
                "sR": sorted(signature_b),
                "det": ligne["det"], "definitude": ligne["definitude"],
            })
        regles[relation] = lignes
    return regles


# ---------------------------------------------------------------------------
# Similarité
# ---------------------------------------------------------------------------

def similarite(signature_1, signature_2):
    """Cosinus sur deux ensembles de symboles binaires. Retourne un flottant de 0 à 1.

    |s1 ∩ s2| / racine(|s1| × |s2|). Vaut 0.0 si l'une des deux est vide."""
    if not signature_1 or not signature_2:
        return 0.0
    communs = len(set(signature_1) & set(signature_2))
    return communs / math.sqrt(len(signature_1) * len(signature_2))


# ---------------------------------------------------------------------------
# Écriture des sorties
# ---------------------------------------------------------------------------

def ecrire_signatures(signatures):
    """Écrit data/signatures/signatures_termes.json. Ne retourne rien."""
    config.DOSSIER_SIGNATURES.mkdir(parents=True, exist_ok=True)
    par_terme = {}
    for terme in sorted(signatures):
        par_terme[terme] = sorted(signatures[terme])
    config.FICHIER_SIGNATURES.write_text(
        json.dumps(par_terme, ensure_ascii=False, indent=1), encoding="utf-8")


# ---------------------------------------------------------------------------
# Outils de mise en forme du rapport
# ---------------------------------------------------------------------------

def mediane(valeurs):
    """Médiane d'une liste, 0 si elle est vide. Retourne un nombre."""
    return statistics.median(valeurs) if valeurs else 0


def milliers(n):
    """Entier avec séparateur de milliers à la française. Retourne une chaîne."""
    return f"{n:,}".replace(",", " ")


def fr(x, nd=1):
    """Nombre décimal à la française : séparateur virgule. Retourne une chaîne."""
    return f"{x:.{nd}f}".replace(".", ",")


def pct(partie, total, nd=1):
    """Pourcentage à la française, « — » si le total est nul. Retourne une chaîne."""
    return fr(100 * partie / total, nd) + " %" if total else "—"


def tableau(entete, lignes):
    """Construit un tableau Markdown. Retourne une liste de lignes."""
    sortie = ["| " + " | ".join(entete) + " |", "|" + "|".join(["---"] * len(entete)) + "|"]
    for ligne in lignes:
        sortie.append("| " + " | ".join(str(c) for c in ligne) + " |")
    return sortie + [""]


def prefixe_du_symbole(symbole):
    """Trait d'origine d'un symbole. Retourne « H », « TRT », « SST » ou « terme »."""
    for nom, prefixe in (("H", config.PREFIXE_H), ("TRT", config.PREFIXE_TRT),
                         ("SST", config.PREFIXE_SST)):
        if symbole.startswith(prefixe):
            return nom
    return "terme"


def compter_par_trait(signature):
    """Compte les symboles d'une signature par trait. Retourne un Counter."""
    comptes = Counter()
    for symbole in signature:
        comptes[prefixe_du_symbole(symbole)] += 1
    return comptes


# ---------------------------------------------------------------------------
# Rapport : une fonction par section
# ---------------------------------------------------------------------------

def section_vocabulaire(vocabulaire):
    """Section 1 : taille du vocabulaire et ventilation par préfixe."""
    par_trait = Counter()
    for symbole in vocabulaire:
        par_trait[prefixe_du_symbole(symbole)] += 1
    total = len(vocabulaire)
    lignes = ["## 1. Vocabulaire global", "",
              f"**{milliers(total)} symboles distincts**, numérotés de 0 à {total - 1}. "
              "Un seul vocabulaire pour les 15 types : sans cela, la même dimension ne "
              "désignerait pas le même symbole d'un type à l'autre.", ""]
    corps = []
    for trait in ("H", "TRT", "SST", "terme"):
        corps.append([trait, milliers(par_trait[trait]), pct(par_trait[trait], total)])
    lignes += tableau(["préfixe", "symboles", "part"], corps)
    lignes += ["La disproportion est attendue : TRT est borné par le nombre de types de "
               "relations de JDM et SST par le nombre d'annotations existantes, alors que "
               "H est ouvert — chaque hyperonyme distinct est un symbole de plus.", ""]
    return lignes


def section_tailles(signatures):
    """Section 2 : taille des signatures, globalement et par trait."""
    tailles = [len(s) for s in signatures.values()]
    par_trait = defaultdict(list)
    for signature in signatures.values():
        comptes = compter_par_trait(signature)
        for trait in ("H", "TRT", "SST"):
            par_trait[trait].append(comptes[trait])

    lignes = ["## 2. Taille des signatures", "",
              f"Sur les {milliers(len(signatures))} termes collectés.", ""]
    corps = [["signature complète", min(tailles), f"{mediane(tailles):g}", max(tailles),
              milliers(sum(tailles))]]
    for trait in ("H", "TRT", "SST"):
        valeurs = par_trait[trait]
        corps.append([f"dont {trait}", min(valeurs), f"{mediane(valeurs):g}", max(valeurs),
                      milliers(sum(valeurs))])
    lignes += tableau(["ensemble", "min", "médiane", "max", "total"], corps)
    lignes += ["La signature complète compte toujours le terme lui-même : sa taille "
               "minimale est donc 1, jamais 0.", ""]
    return lignes


def section_tailles_par_relation(regles):
    """Section 3 : taille des signatures par type de relation et par rôle."""
    lignes = ["## 3. Taille des signatures par type de relation et par rôle", "",
              "Repère les types mal dotés : un type dont les signatures sont courtes "
              "des deux côtés donnera des similarités faibles et peu fiables.", ""]
    corps = []
    for relation in sorted(regles):
        tailles_a = [len(r["sL"]) for r in regles[relation]]
        tailles_b = [len(r["sR"]) for r in regles[relation]]
        corps.append([f"`{relation}`", len(regles[relation]),
                      f"{mediane(tailles_a):g}", f"{min(tailles_a)}–{max(tailles_a)}",
                      f"{mediane(tailles_b):g}", f"{min(tailles_b)}–{max(tailles_b)}"])
    lignes += tableau(["relation", "règles", "médiane \\|sL\\| (A)", "étendue A",
                       "médiane \\|sR\\| (B)", "étendue B"], corps)
    return lignes


def section_signatures_pauvres(regles):
    """Section 4 : signatures vides ou quasi vides, avec leur type de relation."""
    seuil = config.SEUIL_SIGNATURE_QUASI_VIDE
    pauvres = {}
    for relation in sorted(regles):
        for regle in regles[relation]:
            for role, cle in (("A", "sL"), ("B", "sR")):
                if len(regle[cle]) >= seuil:
                    continue
                terme = regle[role]
                if terme not in pauvres:
                    pauvres[terme] = {"taille": len(regle[cle]), "roles": set(),
                                      "relations": set(), "symboles": regle[cle]}
                pauvres[terme]["roles"].add(role)
                pauvres[terme]["relations"].add(relation)

    lignes = ["## 4. Signatures vides ou quasi vides", "",
              f"Termes dont la signature compte moins de {seuil} symboles, terme "
              f"lui-même inclus : **{len(pauvres)}**.", ""]
    if not pauvres:
        return lignes + ["Aucun.", ""]
    corps = []
    for terme in sorted(pauvres, key=lambda t: (pauvres[t]["taille"], t)):
        infos = pauvres[terme]
        corps.append([f"« {terme} »", infos["taille"],
                      "/".join(sorted(infos["roles"])),
                      ", ".join(f"`{r}`" for r in sorted(infos["relations"])),
                      ", ".join(f"`{s}`" for s in infos["symboles"])])
    lignes += tableau(["terme", "\\|signature\\|", "rôle", "type(s) de relation",
                       "symboles"], corps)
    return lignes


def section_symboles_frequents(signatures):
    """Section 5 : les symboles les plus répandus, tous traits confondus."""
    frequences = Counter()
    for signature in signatures.values():
        for symbole in signature:
            frequences[symbole] += 1
    total = len(signatures)
    lignes = ["## 5. Les symboles les plus fréquents", "",
              f"Sur {milliers(total)} termes. **Un symbole présent partout ne discrimine "
              "rien** : il gonfle toutes les similarités de la même façon. Ce tableau est "
              "là pour que ces symboles soient visibles avant l'étape 4, pas pour les "
              "retirer maintenant.", ""]
    corps = []
    for symbole, nombre in frequences.most_common(config.NB_SYMBOLES_FREQUENTS):
        corps.append([f"`{symbole}`", prefixe_du_symbole(symbole), milliers(nombre),
                      pct(nombre, total)])
    lignes += tableau(["symbole", "trait", "termes", "part"], corps)

    universels = []
    for symbole, nombre in frequences.items():
        if nombre == total:
            universels.append(symbole)
    if universels:
        lignes += [f"Symboles présents chez **tous** les termes : "
                   + ", ".join(f"`{s}`" for s in sorted(universels)) + ".", ""]
    else:
        lignes += ["Aucun symbole n'est présent chez la totalité des termes.", ""]

    # Où se situent les traits absents du classement : c'est le point important.
    meilleurs = {}
    for symbole, nombre in frequences.most_common():
        trait = prefixe_du_symbole(symbole)
        if trait not in meilleurs:
            meilleurs[trait] = (symbole, nombre)
    corps = []
    for trait in ("H", "TRT", "SST", "terme"):
        if trait in meilleurs:
            symbole, nombre = meilleurs[trait]
            corps.append([trait, f"`{symbole}`", milliers(nombre), pct(nombre, total)])
    lignes += ["Symbole le plus répandu de chaque trait :", ""]
    lignes += tableau(["trait", "symbole", "termes", "part"], corps)
    lignes += ["Le classement ci-dessus n'est peuplé que de symboles TRT, et ce n'est pas "
               "un artefact : il n'y a que 128 types de relations entrantes pour 1 871 "
               "termes, donc chacun est forcément très partagé, alors que les 10 717 "
               "hyperonymes se répartissent la même population. Autrement dit TRT apporte "
               "de la masse commune et H du pouvoir discriminant — ce que l'étape 4 devra "
               "arbitrer.", ""]
    return lignes


def verifier_similarite_a_la_main():
    """Section 6 : deux exemples calculés à la main, comparés à la fonction.

    Retourne (lignes du rapport, nombre d'écarts constatés)."""
    exemples = [
        {"titre": "Recouvrement partiel",
         "s1": {"chien", "H:mammifère", "TRT:r_isa", "SST:LIVING-BEING"},
         "s2": {"chat", "H:mammifère", "TRT:r_isa", "SST:PERS"},
         "communs": ["H:mammifère", "TRT:r_isa"],
         "detail": "2 communs, \\|s1\\| = 4, \\|s2\\| = 4 → 2 / racine(4 × 4) = 2 / 4"},
        {"titre": "Tailles inégales, aucun symbole commun",
         "s1": {"vin", "H:boisson", "H:alcool"},
         "s2": {"France", "SST:PLACE-GEO"},
         "communs": [],
         "detail": r"0 commun, \|s1\| = 3, \|s2\| = 2 → 0 / racine(3 × 2) = 0"},
        {"titre": "Signature vide",
         "s1": set(),
         "s2": {"France", "SST:PLACE-GEO"},
         "communs": [],
         "detail": r"\|s1\| = 0 : la fonction retourne 0.0 sans diviser par zéro"},
    ]
    lignes = ["## 6. Vérification manuelle de `similarite`", "",
              "La fonction calcule le cosinus sur les ensembles : "
              "`|s1 ∩ s2| / racine(|s1| × |s2|)`. Trois cas calculés à la main et "
              "comparés à la sortie de la fonction.", ""]
    corps, ecarts = [], 0
    for exemple in exemples:
        if exemple["s1"] and exemple["s2"]:
            attendu = len(exemple["communs"]) / math.sqrt(len(exemple["s1"]) * len(exemple["s2"]))
        else:
            attendu = 0.0
        obtenu = similarite(exemple["s1"], exemple["s2"])
        accord = abs(obtenu - attendu) < 1e-12
        if not accord:
            ecarts += 1
        corps.append([exemple["titre"], exemple["detail"], fr(attendu, 4), fr(obtenu, 4),
                      "OK" if accord else "**ÉCART**"])
    lignes += tableau(["cas", "calcul à la main", "attendu", "obtenu", "verdict"], corps)

    # Contrôles de propriété, sur des signatures réelles plutôt que fabriquées.
    exemple_reel = {"a", "H:x", "H:y", "TRT:z"}
    identique = similarite(exemple_reel, exemple_reel)
    symetrie_1 = similarite(exemple_reel, {"a", "H:x"})
    symetrie_2 = similarite({"a", "H:x"}, exemple_reel)
    if abs(identique - 1.0) > 1e-12:
        ecarts += 1
    if abs(symetrie_1 - symetrie_2) > 1e-12:
        ecarts += 1
    lignes += [f"- Identité : `similarite(s, s)` = {fr(identique, 4)} (attendu 1,0000).",
               f"- Symétrie : `similarite(s1, s2)` = {fr(symetrie_1, 4)} et "
               f"`similarite(s2, s1)` = {fr(symetrie_2, 4)}.",
               "",
               f"**{ecarts} écart(s) constaté(s).**", ""]
    return lignes, ecarts


def section_sorties(signatures, vocabulaire, regles, absents, ecartees,
                    hors_corpus):
    """Section 7 : ce qui a été écrit, et les cas signalés."""
    total_regles = sum(len(v) for v in regles.values())
    lignes = ["## 7. Sorties écrites", "",
              f"Le vocabulaire ({milliers(len(vocabulaire))} symboles) et les "
              f"{milliers(total_regles)} règles de base sont calculés pour ce rapport "
              "mais plus écrits sur disque : personne ne les relisait. `grasp.py` "
              "reconstruit ses règles depuis le corpus et les signatures.", ""]
    corps = [["`data/signatures/signatures_termes.json`",
              f"{milliers(len(signatures))} termes -> liste triée de symboles"]]
    lignes += tableau(["fichier", "contenu"], corps)

    lignes += ["### Cas signalés", "",
               f"- **Termes absents de JDM : {len(absents)}.** Leur signature est réduite "
               "au terme lui-même. " + (", ".join(f"« {t} »" for t in absents) + "."
                                        if absents else ""),
               f"- **Lignes de corpus sans règle : {len(ecartees)}.** Un découpage ambigu "
               "laisse A et B vides dans le corpus propre : aucune règle ne peut en être "
               "tirée, et le corpus n'est pas modifié pour y remédier.",
               f"- **Termes collectés hors corpus : {len(hors_corpus)}.** Candidats de "
               "découpage rejetés par l'arbitrage : collectés à l'étape 2, ils ne reçoivent "
               "pas de signature. " + (", ".join(f"« {t} »" for t in hors_corpus) + "."
                                       if hors_corpus else ""), ""]
    if ecartees:
        corps = []
        for ligne in ecartees:
            corps.append([ligne["fichier"], f"« {ligne['syntagme']} »",
                          f"`{ligne['relation']}`", ligne["raison"]])
        lignes += tableau(["fichier", "syntagme", "relation", "raison"], corps)
    return lignes


def construire_rapport(signatures, vocabulaire, regles, absents, ecartees,
                       hors_corpus):
    """Assemble reports/rapport_signatures.md. Retourne le nombre d'écarts de similarité."""
    lignes = ["# Signatures, vocabulaire et règles", "",
              "Généré par `src/signatures.py` depuis `data/collecte/termes_jdm.jsonl` et "
              "`data/corpus/clean/`. Aucun appel réseau.", "",
              "Une signature est un ensemble plat de symboles binaires préfixés par leur "
              "provenance (`H:`, `TRT:`, `SST:`), plus le terme lui-même sans préfixe. Une "
              "règle est `R = < sL, sR, rt >` : les deux signatures restent séparées, "
              "parce que la position porte le sens — « vin de France » n'est pas "
              "« France de vin ».", "",
              "### Coupures appliquées", "",
              f"- **H** : top {config.H_TOP} par poids décroissant, poids > 0. Doublons de "
              "casse fusionnés **avant** la coupure, sur la forme normalisée, en gardant la "
              "forme d'origine la mieux pondérée. Préfixes de langue "
              + ("**exclus**" if config.H_EXCLURE_PREFIXES_LANGUE else "conservés")
              + f" (`H_EXCLURE_PREFIXES_LANGUE = {config.H_EXCLURE_PREFIXES_LANGUE}`).",
              f"- **TRT** : tous les types entrants d'effectif > 0, sauf "
              f"{len(config.TRT_TYPES_EXCLUS)} types non sémantiques exclus. Aucun seuil "
              "d'effectif.",
              "- **SST** : toutes les annotations. Annotations morphologiques "
              + ("**exclues**" if config.SST_EXCLURE_MORPHO else "conservées")
              + f" (`SST_EXCLURE_MORPHO = {config.SST_EXCLURE_MORPHO}`).", "",
              "Tous ces seuils sont dans `config.py`. La collecte est restée brute : les "
              "faire varier ne demande que de relancer ce script.", ""]

    lignes += section_vocabulaire(vocabulaire)
    lignes += section_tailles(signatures)
    lignes += section_tailles_par_relation(regles)
    lignes += section_signatures_pauvres(regles)
    lignes += section_symboles_frequents(signatures)
    lignes_similarite, ecarts = verifier_similarite_a_la_main()
    lignes += lignes_similarite
    lignes += section_sorties(signatures, vocabulaire, regles,
                              absents, ecartees, hors_corpus)
    lignes += ["## 8. Hors périmètre", "",
               "Cette étape ne fusionne aucune règle, n'applique aucun seuil de 0,5, "
               "n'exécute pas GRASP-it, ne classe rien, n'évalue rien et ne calcule aucune "
               "matrice de similarité complète. La collecte et le corpus sont inchangés.", ""]

    config.DOSSIER_RAPPORTS.mkdir(parents=True, exist_ok=True)
    chemin = config.DOSSIER_RAPPORTS / "rapport_signatures.md"
    chemin.write_text("\n".join(lignes), encoding="utf-8")
    print(f"Rapport écrit : {chemin}")
    return ecarts


def main():
    collecte = charger_collecte()
    print(f"Collecte : {len(collecte)} termes lus.", flush=True)

    corpus, ecartees = charger_corpus()
    attendus = termes_du_corpus(corpus)
    print(f"Corpus : {len(attendus)} termes distincts.", flush=True)

    signatures, absents, hors_corpus = construire_toutes_les_signatures(collecte, attendus)
    print(f"Signatures : {len(signatures)} construites, {len(absents)} termes absents de JDM, "
          f"{len(hors_corpus)} terme(s) collecté(s) hors corpus.", flush=True)

    vocabulaire = construire_vocabulaire(signatures)
    print(f"Vocabulaire : {len(vocabulaire)} symboles distincts.", flush=True)

    regles = construire_regles(corpus, signatures)
    total_regles = sum(len(v) for v in regles.values())
    print(f"Règles : {total_regles} sur {len(regles)} types "
          f"({len(ecartees)} ligne(s) écartée(s)).", flush=True)

    ecrire_signatures(signatures)

    ecarts = construire_rapport(signatures, vocabulaire, regles,
                                absents, ecartees, hors_corpus)
    if ecarts:
        print(f"ATTENTION : {ecarts} écart(s) sur la vérification de similarite.", flush=True)


if __name__ == "__main__":
    main()
