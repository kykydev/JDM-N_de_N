#!/usr/bin/env python3
"""Apprentissage par clustering hiérarchique agglomératif complet (phase A).

Un arbre par type de relation, soit quinze arbres. Deux règles de types différents ne
fusionnent jamais (papier, note 2). Chaque arbre est appris sur les 50 exemples
d'entraînement de son type : il n'y a plus de seuil à choisir, donc plus de calibrage.

Un nœud est une règle < sL, sR > : signature attendue à gauche, signature attendue à
droite. Les deux côtés restent SÉPARÉS, jamais concaténés : « vin de France » n'est pas
« France de vin ».

    1. chaque exemple devient une feuille, de poids 1 ;
    2. le lien entre deux nœuds actifs vaut min( sim(sL₁, sL₂), sim(sR₁, sR₂) ) : le
       minimum exige que les DEUX côtés se ressemblent ;
    3. la paire de lien maximal fusionne, ex aequo départagés par l'ordre du corpus ;
    4. le nouveau nœud unit les signatures côté à côté, additionne les poids, et prend
       pour hauteur la valeur du lien ;
    5. seule la ligne du nouveau nœud est calculée, jamais toute la matrice ;
    6. on recommence jusqu'à la racine.

Pour 50 feuilles : 49 fusions, 99 nœuds. Tous sont stockés, feuilles comprises.

Aucun seuil, aucune classification, aucun appel réseau. Le split test n'est pas lu.

Usage : python3 src/grasp.py
"""

import csv
import json
import math
import re
import statistics
import time
from collections import defaultdict
from datetime import datetime, timezone

import config
import signatures as sig


# ---------------------------------------------------------------------------
# Lecture des entrées
# ---------------------------------------------------------------------------

def charger_signatures():
    """Lit data/signatures/signatures_termes.json. Retourne terme -> ensemble."""
    brut = json.loads(config.FICHIER_SIGNATURES.read_text(encoding="utf-8"))
    return {terme: set(symboles) for terme, symboles in brut.items()}


def charger_lignes(split):
    """Lignes d'un split, par type, dans l'ordre du corpus. Retourne relation -> liste.

    L'ordre du corpus est conservé : c'est lui qui départage les ex aequo."""
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
    return dict(par_type)


def cotes_de_ligne(ligne, signatures):
    """Signatures gauche et droite d'une ligne de corpus. Retourne un couple d'ensembles.

    Un terme sans signature se réduit à lui-même, comme à l'étape 3."""
    return (set(signatures.get(ligne["A"], {ligne["A"]})),
            set(signatures.get(ligne["B"], {ligne["B"]})))


def feuilles_de_depart(lignes_par_type, signatures):
    """Les cotés de chaque exemple d'entraînement. Retourne relation -> liste de dicts."""
    depart = {}
    for relation in sorted(lignes_par_type):
        depart[relation] = []
        for ligne in lignes_par_type[relation]:
            gauche, droite = cotes_de_ligne(ligne, signatures)
            depart[relation].append({"syntagme": ligne["syntagme"],
                                     "sL": gauche, "sR": droite})
    return depart


# ---------------------------------------------------------------------------
# Représentation d'un nœud : union d'ensembles ou somme de comptes
# ---------------------------------------------------------------------------
#
# « union »  : un côté est un ensemble de symboles. Similarité : similarite() de
#              signatures.py, telle quelle.
# « somme »  : un côté est un dict symbole -> nombre d'exemples couverts qui le portent,
#              lecture littérale de l'article (p. 29, « la somme vectorielle des deux
#              signatures »). Une feuille est un vecteur de 1. Le cosinus ignorant
#              l'échelle, comparer à une somme revient à comparer au centroïde.
#
# Un exemple à classer reste un ensemble : c'est un vecteur de 1.

REPRESENTATIONS = ("union", "somme")


def choisir_representation(representation):
    """Résout un paramètre optionnel : None donne la représentation par défaut du projet.
    Retourne une chaîne."""
    return config.REPRESENTATION if representation is None else representation


def signature_de_feuille(symboles, representation):
    """Un côté de feuille dans la représentation voulue. Retourne un ensemble ou un dict.

    En somme, des symboles déjà pondérés (un dict symbole -> poids réel) sont gardés tels
    quels ; un simple ensemble reçoit le poids 1 pour chaque symbole."""
    if representation == "somme":
        if isinstance(symboles, dict):
            return dict(symboles)
        return {symbole: 1 for symbole in symboles}
    return set(symboles)


def unir(signature_1, signature_2):
    """Fusionne deux côtés : union d'ensembles ou somme de comptes. Retourne le côté parent."""
    if isinstance(signature_1, dict):
        somme = dict(signature_1)
        for symbole, compte in signature_2.items():
            somme[symbole] = somme.get(symbole, 0) + compte
        return somme
    return signature_1 | signature_2


def norme(signature):
    """Norme euclidienne d'un côté ; un ensemble est un vecteur de 1. Retourne un flottant."""
    if isinstance(signature, dict):
        return math.sqrt(sum(compte * compte for compte in signature.values()))
    return math.sqrt(len(signature))


def produit_scalaire(signature_1, signature_2):
    """Produit scalaire de deux côtés, ensembles ou comptes. Retourne un nombre.

    On parcourt le plus petit des deux, qui décide du coût."""
    petit, grand = sorted((signature_1, signature_2), key=len)
    if isinstance(petit, dict):
        if isinstance(grand, dict):
            return sum(compte * grand.get(s, 0) for s, compte in petit.items())
        return sum(compte for s, compte in petit.items() if s in grand)
    if isinstance(grand, dict):
        return sum(grand.get(s, 0) for s in petit)
    return len(petit & grand)


def similarite_signatures(signature_1, signature_2, norme_1=None, norme_2=None):
    """Cosinus de deux côtés, quelle que soit leur représentation. Retourne un flottant.

    Deux ensembles passent par similarite() telle quelle. Sinon produit scalaire sur
    produit des normes, celles-ci pouvant être fournies précalculées."""
    if not isinstance(signature_1, dict) and not isinstance(signature_2, dict):
        return sig.similarite(signature_1, signature_2)
    if not signature_1 or not signature_2:
        return 0.0
    norme_1 = norme(signature_1) if norme_1 is None else norme_1
    norme_2 = norme(signature_2) if norme_2 is None else norme_2
    return produit_scalaire(signature_1, signature_2) / (norme_1 * norme_2)


def similarite_cote(signature, noeud, cote):
    """Cosinus d'une signature d'exemple avec le côté « L » ou « R » d'un nœud.
    Retourne un flottant."""
    return similarite_signatures(signature, noeud["s" + cote], None, noeud["n" + cote])


# ---------------------------------------------------------------------------
# Nœuds
# ---------------------------------------------------------------------------

def avec_normes(noeud):
    """Ajoute au nœud la norme de ses deux côtés. Retourne le nœud."""
    noeud["nL"], noeud["nR"] = norme(noeud["sL"]), norme(noeud["sR"])
    return noeud


def nouvelle_feuille(identifiant, relation, exemple, ordre, representation):
    """Construit une feuille à partir d'un exemple. Retourne un dict.

    `ordre` est le rang de l'exemple dans son type : il départage les ex aequo."""
    return avec_normes({
        "id": identifiant, "rt": relation,
        "sL": signature_de_feuille(exemple["sL"], representation),
        "sR": signature_de_feuille(exemple["sR"], representation),
        "poids": 1, "hauteur": None, "enfants": None,
        "syntagmes": [exemple["syntagme"]], "ordre": ordre, "profondeur": None})


def fusionner(identifiant, noeud_1, noeud_2, hauteur):
    """Unit deux nœuds de même type. Retourne le nœud parent.

    Les côtés fusionnent côté à côté — union ou somme selon la représentation — et
    les poids s'additionnent. L'enfant cité en premier est le plus ancien du corpus."""
    premier, second = sorted((noeud_1, noeud_2), key=lambda n: n["ordre"])
    return avec_normes({
        "id": identifiant, "rt": premier["rt"],
        "sL": unir(premier["sL"], second["sL"]), "sR": unir(premier["sR"], second["sR"]),
        "poids": premier["poids"] + second["poids"], "hauteur": hauteur,
        "enfants": [premier["id"], second["id"]],
        "syntagmes": premier["syntagmes"] + second["syntagmes"],
        "ordre": premier["ordre"], "profondeur": None})


def est_feuille(noeud):
    """Dit si un nœud est une feuille. Retourne un booléen."""
    return noeud["enfants"] is None


# ---------------------------------------------------------------------------
# Clustering hiérarchique d'un type
# ---------------------------------------------------------------------------

def lien(noeud_1, noeud_2):
    """Lien de deux nœuds : le plus faible des deux côtés. Retourne un flottant.

    Le minimum exige que les A ET les B se ressemblent : une paire qui colle d'un côté
    et pas de l'autre est faible, comme l'avait montré le diagnostic du critère."""
    return min(similarite_signatures(noeud_1["sL"], noeud_2["sL"],
                                     noeud_1["nL"], noeud_2["nL"]),
               similarite_signatures(noeud_1["sR"], noeud_2["sR"],
                                     noeud_1["nR"], noeud_2["nR"]))


def cle_de_paire(id_1, id_2):
    """Clé d'une case de la demi-matrice, plus petit identifiant d'abord. Retourne un couple."""
    return (id_1, id_2) if id_1 < id_2 else (id_2, id_1)


def matrice_initiale(noeuds, actifs):
    """Moitié supérieure de la matrice des liens entre feuilles. Retourne (i, j) -> lien."""
    liens = {}
    for rang, id_1 in enumerate(actifs):
        for id_2 in actifs[rang + 1:]:
            liens[cle_de_paire(id_1, id_2)] = lien(noeuds[id_1], noeuds[id_2])
    return liens


def meilleure_paire(liens, noeuds):
    """La paire de lien maximal. Retourne (id_1, id_2, lien).

    Ex aequo départagés par l'ordre d'apparition dans le corpus des deux nœuds, le plus
    ancien d'abord : le résultat ne dépend pas de l'ordre de parcours d'un dict."""
    def cle(case):
        ordres = sorted((noeuds[case[0]]["ordre"], noeuds[case[1]]["ordre"]))
        return (-liens[case], ordres[0], ordres[1])
    choisie = min(liens, key=cle)
    return choisie[0], choisie[1], liens[choisie]


def retirer_de_la_matrice(liens, identifiants):
    """Supprime toutes les cases qui touchent ces nœuds. Ne retourne rien."""
    for case in [c for c in liens if c[0] in identifiants or c[1] in identifiants]:
        del liens[case]


def ajouter_ligne(liens, noeuds, actifs, nouveau):
    """Calcule la seule ligne du nouveau nœud contre les actifs. Retourne le nombre de liens."""
    for autre in actifs:
        liens[cle_de_paire(autre, nouveau["id"])] = lien(noeuds[autre], nouveau)
    return len(actifs)


def construire_arbre(relation, exemples, premier_id, representation):
    """Clustering hiérarchique complet d'un type. Retourne (nœuds, id racine, journal).

    Les identifiants partent de `premier_id` : feuilles d'abord, dans l'ordre du corpus,
    puis nœuds internes dans l'ordre des fusions — l'identifiant d'un nœud interne dit
    donc à quel rang il a été fusionné."""
    noeuds = {}
    for rang, exemple in enumerate(exemples):
        feuille = nouvelle_feuille(premier_id + rang, relation, exemple, rang,
                                   representation)
        noeuds[feuille["id"]] = feuille
    actifs = sorted(noeuds)
    liens = matrice_initiale(noeuds, actifs)
    calculs = len(liens)
    prochain = premier_id + len(exemples)

    while len(actifs) > 1:
        id_1, id_2, valeur = meilleure_paire(liens, noeuds)
        parent = fusionner(prochain, noeuds[id_1], noeuds[id_2], valeur)
        noeuds[parent["id"]] = parent
        prochain += 1
        retirer_de_la_matrice(liens, {id_1, id_2})
        actifs = [a for a in actifs if a not in (id_1, id_2)]
        calculs += ajouter_ligne(liens, noeuds, actifs, parent)
        actifs.append(parent["id"])

    racine = actifs[0]
    fixer_profondeurs(noeuds, racine)
    return noeuds, racine, {"liens_calcules": calculs}


def fixer_profondeurs(noeuds, racine):
    """Donne à chaque nœud sa distance à la racine, qui vaut 0. Ne retourne rien."""
    pile = [(racine, 0)]
    while pile:
        identifiant, profondeur = pile.pop()
        noeuds[identifiant]["profondeur"] = profondeur
        for enfant in noeuds[identifiant]["enfants"] or []:
            pile.append((enfant, profondeur + 1))


def construire_foret(depart, representation=None):
    """Un arbre par type, identifiants uniques sur toute la forêt.
    Retourne (id -> nœud, relation -> id racine, relation -> journal)."""
    representation = choisir_representation(representation)
    noeuds, racines, journaux = {}, {}, {}
    for relation in sorted(depart):
        arbre, racine, journal = construire_arbre(relation, depart[relation], len(noeuds),
                                                  representation)
        noeuds.update(arbre)
        racines[relation] = racine
        journaux[relation] = journal
    return noeuds, racines, journaux


# ---------------------------------------------------------------------------
# Mesures sur un arbre
# ---------------------------------------------------------------------------

# Nombre d'isolats listés par type dans le rapport, du dernier rattaché au précédent.
ISOLATS_LISTES = 3

# Au-delà de ce poids, un groupe détaché près de la racine n'est plus un isolat mais
# une vraie branche.
TAILLE_ISOLAT = 3

def noeuds_du_type(noeuds, relation):
    """Les nœuds d'un arbre, par identifiant croissant. Retourne une liste."""
    return [n for _, n in sorted(noeuds.items()) if n["rt"] == relation]


def inversions(noeuds, relation):
    """Nœuds plus hauts qu'un de leurs enfants internes. Retourne une liste de dicts.

    Dans un clustering classique la hauteur décroît en remontant ; ici l'union des
    signatures peut rendre un nœud fusionné plus proche d'un tiers que ne l'étaient
    ses composantes, et la fusion suivante se fait alors à un lien plus élevé."""
    trouvees = []
    for noeud in noeuds_du_type(noeuds, relation):
        if est_feuille(noeud):
            continue
        for enfant in noeud["enfants"]:
            hauteur_enfant = noeuds[enfant]["hauteur"]
            if hauteur_enfant is not None and noeud["hauteur"] > hauteur_enfant:
                trouvees.append({"id": noeud["id"], "enfant": enfant,
                                 "ecart": noeud["hauteur"] - hauteur_enfant})
                break
    return trouvees


def greffes(noeuds, relation):
    """Fusions qui rattachent une feuille isolée à un groupe. Retourne un entier.

    Un arbre en peigne n'est fait que de greffes ; un arbre équilibré en a peu."""
    compte = 0
    for noeud in noeuds_du_type(noeuds, relation):
        if est_feuille(noeud):
            continue
        poids = sorted(noeuds[e]["poids"] for e in noeud["enfants"])
        if poids[0] == 1 and poids[1] > 1:
            compte += 1
    return compte


def isolats_de_racine(noeuds, racine):
    """Petits groupes rattachés en dernier au reste de l'arbre. Retourne une liste de dicts.

    On descend de la racine vers l'enfant lourd tant que l'autre enfant ne pèse pas plus
    de TAILLE_ISOLAT exemples. Ce qu'on a détaché ainsi, ce sont les exemples que le
    type n'a su rapprocher de personne ; ce qui reste est le noyau."""
    isolats, noeud = [], noeuds[racine]
    while not est_feuille(noeud):
        rangs = {e: rang for rang, e in enumerate(noeud["enfants"])}
        petit, gros = sorted((noeuds[e] for e in noeud["enfants"]),
                             key=lambda n: (n["poids"], rangs[n["id"]]))
        if petit["poids"] > TAILLE_ISOLAT:
            break
        isolats.append({"syntagmes": petit["syntagmes"], "hauteur": noeud["hauteur"]})
        noeud = gros
    return isolats, noeud["poids"]


def mesurer_arbre(noeuds, relation, racine, journal):
    """Profondeur, hauteur, inversions, taille et forme d'un arbre. Retourne un dict."""
    tous = noeuds_du_type(noeuds, relation)
    internes = [n for n in tous if not est_feuille(n)]
    tete = noeuds[racine]
    enfants = [noeuds[e] for e in tete["enfants"]]
    trouvees = inversions(noeuds, relation)
    isolats, noyau = isolats_de_racine(noeuds, racine)
    hauteurs = [n["hauteur"] for n in internes]
    return {
        "rt": relation, "feuilles": len(tous) - len(internes), "noeuds": len(tous),
        "profondeur": max(n["profondeur"] for n in tous),
        "hauteur_racine": tete["hauteur"],
        "hauteur_max": max(hauteurs), "hauteur_mediane": statistics.median(hauteurs),
        "inversions": len(trouvees),
        "inversion_max": max((i["ecart"] for i in trouvees), default=0.0),
        "racine_sL": len(tete["sL"]), "racine_sR": len(tete["sR"]),
        "plus_gros_enfant": max(e["poids"] for e in enfants),
        "greffes": greffes(noeuds, relation),
        "isolats": isolats, "noyau": noyau,
        "liens_calcules": journal["liens_calcules"],
    }


# ---------------------------------------------------------------------------
# Écriture des arbres
# ---------------------------------------------------------------------------

def serialiser_noeud(noeud):
    """Prépare un nœud pour le JSON : ensembles triés, ordre retiré. Retourne un dict."""
    return {"id": noeud["id"], "rt": noeud["rt"], "poids": noeud["poids"],
            "hauteur": noeud["hauteur"], "enfants": noeud["enfants"],
            "profondeur": noeud["profondeur"], "syntagmes": noeud["syntagmes"],
            "sL": serialiser_cote(noeud["sL"]), "sR": serialiser_cote(noeud["sR"])}


def serialiser_cote(signature):
    """Un côté prêt pour le JSON : liste triée ou comptes triés. Retourne une liste ou un dict."""
    if isinstance(signature, dict):
        return dict(sorted(signature.items()))
    return sorted(signature)


def ecrire_arbres(noeuds, racines, representation=None):
    """Écrit les arbres dans config.FICHIER_ARBRES, un nœud par ligne. Retourne le chemin.

    Un nœud par ligne plutôt qu'un symbole par ligne : le fichier reste lisible et
    comparable d'une version à l'autre sans tripler de volume."""
    representation = choisir_representation(representation)
    entete = {
        "methode": "clustering hiérarchique agglomératif complet, un arbre par type",
        "representation": representation,
        "lien": "min( sim(sL1, sL2), sim(sR1, sR2) ), cosinus",
        "ex_aequo": "ordre d'apparition dans le corpus",
        "split": "train complet (50 exemples par type)",
        "trt_politique": config.TRT_POLITIQUE, "h_top": config.H_TOP,
        "genere_le": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "n_noeuds": len(noeuds), "racines": racines,
    }
    lignes = [json.dumps(serialiser_noeud(noeuds[i]), ensure_ascii=False)
              for i in sorted(noeuds)]
    texte = ('{"entete": ' + json.dumps(entete, ensure_ascii=False) + ',\n"noeuds": [\n'
             + ",\n".join(lignes) + "\n]}\n")
    config.FICHIER_ARBRES.parent.mkdir(parents=True, exist_ok=True)
    config.FICHIER_ARBRES.write_text(texte, encoding="utf-8")
    return config.FICHIER_ARBRES


def charger_arbres():
    """Lit config.FICHIER_ARBRES. Retourne (id -> nœud, relation -> id racine)."""
    charge = json.loads(config.FICHIER_ARBRES.read_text(encoding="utf-8"))
    noeuds = {}
    for brut in charge["noeuds"]:
        noeud = dict(brut)
        for cote in ("sL", "sR"):
            noeud[cote] = dict(brut[cote]) if isinstance(brut[cote], dict) else set(brut[cote])
        noeuds[noeud["id"]] = avec_normes(noeud)
    return noeuds, charge["entete"]["racines"]


# ---------------------------------------------------------------------------
# Rapport partagé entre les trois phases
# ---------------------------------------------------------------------------

TITRE_RAPPORT = "# Clustering hiérarchique et classification par descente"


def lire_parties_rapport():
    """Parties déjà écrites dans le rapport commun. Retourne clé -> texte."""
    if not config.FICHIER_RAPPORT_ARBRES.exists():
        return {}
    texte = config.FICHIER_RAPPORT_ARBRES.read_text(encoding="utf-8")
    motif = re.compile(r"<!-- partie (\w+) -->\n(.*?)\n<!-- fin \1 -->", re.DOTALL)
    return {cle: contenu for cle, contenu in motif.findall(texte)}


def ecrire_partie_rapport(cle, lignes):
    """Remplace une partie du rapport commun, laisse les autres. Ne retourne rien.

    Chaque phase a son script ; chacun ne réécrit que sa partie, repérée par des
    marqueurs invisibles au rendu."""
    parties = lire_parties_rapport()
    parties[cle] = "\n".join(lignes).rstrip("\n")
    sortie = [TITRE_RAPPORT, ""]
    for nom in sorted(parties):
        sortie += [f"<!-- partie {nom} -->", parties[nom], f"<!-- fin {nom} -->", ""]
    config.FICHIER_RAPPORT_ARBRES.parent.mkdir(parents=True, exist_ok=True)
    config.FICHIER_RAPPORT_ARBRES.write_text("\n".join(sortie), encoding="utf-8")
    print(f"Rapport, partie {cle} : {config.FICHIER_RAPPORT_ARBRES}", flush=True)


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


# ---------------------------------------------------------------------------
# Rapport de phase A
# ---------------------------------------------------------------------------

def section_dispositif(mesures, noeuds, duree):
    """A.1 : ce qui a été construit. Retourne des lignes."""
    feuilles = sum(m["feuilles"] for m in mesures)
    calculs = sum(m["liens_calcules"] for m in mesures)
    complet = sum(k * (k - 1) // 2 for m in mesures for k in range(2, m["feuilles"] + 1))
    return ["## A. Construction des arbres", "",
            "### A.1 Dispositif", "",
            f"- **{len(mesures)} arbres**, un par type : deux règles de types différents "
            "ne fusionnent jamais (note 2 de l'article).",
            f"- **{feuilles} feuilles**, les 50 exemples d'entraînement de chaque type. "
            "Le calibrage n'a plus d'objet : il n'y a plus de seuil à choisir.",
            f"- **{len(noeuds)} nœuds** stockés, feuilles comprises, dans "
            f"`{config.FICHIER_ARBRES.relative_to(config.RACINE).as_posix()}`.",
            "- **Lien** : `min( sim(sLi, sLj), sim(sRi, sRj) )`, cosinus sur ensembles. "
            "Le minimum exige que les deux côtés se ressemblent.",
            "- **Ex aequo** : départagés par l'ordre d'apparition dans le corpus.",
            "- **Aucun seuil** : on fusionne jusqu'à la racine.",
            f"- **Coût** : {calculs} liens calculés en tout — la demi-matrice initiale, "
            "puis une seule ligne par fusion. Recalculer toute la matrice à chaque "
            f"fusion en aurait coûté de l'ordre de {complet}. Durée : "
            f"{fr(duree, 1)} s.", ""]


def section_par_type(mesures):
    """A.2 : le tableau par type. Retourne des lignes."""
    corps = []
    for m in mesures:
        corps.append([f"`{m['rt']}`", m["profondeur"], fr(m["hauteur_racine"]),
                      fr(m["hauteur_mediane"]), fr(m["hauteur_max"]),
                      m["inversions"],
                      fr(m["inversion_max"]) if m["inversions"] else "—",
                      f"{m['racine_sL']} / {m['racine_sR']}",
                      f"{m['plus_gros_enfant']} / {m['feuilles']}",
                      f"{m['greffes']} / {m['feuilles'] - 1}"])
    return (["### A.2 Les quinze arbres", "",
             "- **profondeur** : celle de la feuille la plus profonde, la racine étant à "
             "0. Un arbre parfaitement équilibré de 50 feuilles a une profondeur de 6, "
             "un peigne pur de 49.",
             "- **hauteur** : valeur du lien au moment de la fusion. Celle de la racine "
             "est le lien de la dernière fusion ; médiane et maximum portent sur les 49 "
             "fusions du type.",
             "- **inversions** : nœuds dont la hauteur dépasse celle d'un de leurs "
             "enfants internes ; « écart max » est le plus grand dépassement.",
             "- **plus gros enfant** : poids du plus lourd des deux enfants de la "
             "racine. 25 / 50 est l'équilibre parfait, 49 / 50 le peigne.",
             "- **greffes** : fusions d'une feuille isolée avec un groupe déjà formé, "
             "sur les 49 fusions du type.", ""]
            + tableau(["type", "profondeur", "hauteur racine", "hauteur méd.",
                       "hauteur max", "inversions", "écart max",
                       "\\|sL\\| / \\|sR\\| racine", "plus gros enfant", "greffes"],
                      corps) + [""])


def section_synthese(mesures):
    """A.3 : ce que le tableau dit, en chiffres agrégés. Retourne des lignes."""
    internes = sum(m["feuilles"] - 1 for m in mesures)
    total_inv = sum(m["inversions"] for m in mesures)
    profondeurs = [m["profondeur"] for m in mesures]
    parts = [m["plus_gros_enfant"] / m["feuilles"] for m in mesures]
    desequilibres = [m for m in mesures if m["plus_gros_enfant"] / m["feuilles"] >= 0.9]
    greffes_tot = sum(m["greffes"] for m in mesures)
    racines = [m["hauteur_racine"] for m in mesures]
    return ["### A.3 Synthèse", "",
            f"- **Inversions** : {total_inv} nœuds internes sur {internes} "
            f"({pct(total_inv / internes)}), dans "
            f"{sum(1 for m in mesures if m['inversions'])} arbres sur {len(mesures)}. "
            "Écart maximal observé : "
            f"{fr(max(m['inversion_max'] for m in mesures))}.",
            f"- **Profondeur** : de {min(profondeurs)} à {max(profondeurs)}, médiane "
            f"{fr(statistics.median(profondeurs), 0)}.",
            f"- **Forme** : le plus gros enfant de la racine pèse de "
            f"{pct(min(parts), 0)} à {pct(max(parts), 0)} des feuilles, et "
            f"{len(desequilibres)} racines sur {len(mesures)} sont à 90 % ou plus. "
            f"Un peigne pur de 50 feuilles a une profondeur de 49, un arbre équilibré de "
            f"6 : les nôtres vont de {min(profondeurs)} à {max(profondeurs)}, et "
            f"{greffes_tot} fusions sur {internes} ({pct(greffes_tot / internes)}) sont "
            "des greffes d'une feuille isolée sur un groupe déjà formé. "
            + ("**Ce sont des peignes.**" if min(profondeurs) >= 30 else
               "Ce ne sont pas des peignes : le déséquilibre vient d'isolats rattachés "
               "en tout dernier (A.4).")
            + "",
            f"- **Hauteur de la racine** : de {fr(min(racines))} à {fr(max(racines))}, "
            f"médiane {fr(statistics.median(racines))}. C'est ce que valent, au pire "
            "des deux côtés, les deux moitiés d'un type l'une pour l'autre.", ""]


def section_isolats(mesures):
    """A.4 : les exemples que leur type n'a rapprochés de personne. Retourne des lignes."""
    corps = []
    for m in mesures:
        for isolat in m["isolats"][:ISOLATS_LISTES]:
            corps.append([f"`{m['rt']}`", fr(isolat["hauteur"]),
                          ", ".join(f"« {s} »" for s in isolat["syntagmes"])])
        if len(m["isolats"]) > ISOLATS_LISTES:
            corps.append([f"`{m['rt']}`", "…", f"{len(m['isolats']) - ISOLATS_LISTES} "
                          "autres rattachements, jusqu'au cœur du noyau"])
    avec = [m for m in mesures if m["isolats"]]
    detaches = sum(len(i["syntagmes"]) for m in mesures for i in m["isolats"])
    return (["### A.4 Isolats de racine", "",
             "En descendant de la racine vers l'enfant lourd, on détache tant que "
             f"l'autre enfant pèse au plus {TAILLE_ISOLAT} exemples. Ce sont les "
             "exemples que leur type n'a su rapprocher de personne : ils ne rejoignent "
             "l'arbre qu'à la toute fin, par un lien très faible.", ""]
            + tableau(["type", "lien de rattachement", "exemples détachés"], corps)
            + ["",
               f"{len(avec)} arbres sur {len(mesures)} ont au moins un isolat, "
               f"{detaches} exemples en tout sur {sum(m['feuilles'] for m in mesures)}. "
               "Une fois détachés, les noyaux pèsent de "
               f"{min(m['noyau'] for m in mesures)} à {max(m['noyau'] for m in mesures)} "
               "exemples.", ""])


def construire_rapport(mesures, noeuds, duree):
    """Écrit la partie A du rapport commun. Ne retourne rien."""
    lignes = section_dispositif(mesures, noeuds, duree)
    lignes += section_par_type(mesures)
    lignes += section_synthese(mesures)
    lignes += section_isolats(mesures)
    ecrire_partie_rapport("A", lignes)


# ---------------------------------------------------------------------------
# Enchaînement
# ---------------------------------------------------------------------------

def main():
    signatures = charger_signatures()
    lignes_train = charger_lignes("train")
    depart = feuilles_de_depart(lignes_train, signatures)
    print(f"Signatures : {len(signatures)}. Entraînement : "
          f"{sum(len(e) for e in depart.values())} exemples sur {len(depart)} types. "
          "Test non lu.", flush=True)

    debut = time.perf_counter()
    noeuds, racines, journaux = construire_foret(depart)
    duree = time.perf_counter() - debut
    mesures = [mesurer_arbre(noeuds, r, racines[r], journaux[r]) for r in sorted(racines)]
    for m in mesures:
        print(f"  {m['rt']:22s} profondeur {m['profondeur']:2d}, racine "
              f"{fr(m['hauteur_racine'])}, {m['inversions']:2d} inversions, "
              f"plus gros enfant {m['plus_gros_enfant']}/{m['feuilles']}", flush=True)

    chemin = ecrire_arbres(noeuds, racines)
    print(f"{len(noeuds)} nœuds en {fr(duree, 1)} s -> {chemin}", flush=True)
    construire_rapport(mesures, noeuds, duree)


if __name__ == "__main__":
    main()
