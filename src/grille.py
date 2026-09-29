#!/usr/bin/env python3
"""Grille d'options en validation croisée sur l'entraînement.

Trois choix, toutes combinaisons comparées :

  1. représentation d'un nœud fusionné : « union » des symboles, ou « somme » des
     comptes (lecture littérale de l'article, p. 29) ;
  2. structure : l'arbre complet, ou la forêt obtenue en coupant l'arbre au seuil t ;
  3. classification : descente, exhaustif sur tous les nœuds (No Trim de l'article),
     exhaustif sur les seules racines (Trim).

Plus le plus proche voisin, exhaustif sur les feuilles seules.

Protocole : 5 plis stratifiés par type sur les 750 exemples d'entraînement. Pour chaque
pli et chaque représentation, UN arbre complet par type est construit sur les 4 autres
plis ; toutes les coupes et toutes les classifications en découlent.

La coupe au seuil t garde toutes les fusions effectuées AVANT la première fusion dont
le lien est < t. On raisonne sur l'ordre des fusions, jamais sur les hauteurs : les
inversions les rendent non monotones.

Le score de chaque nœud de l'arbre complet est calculé une fois par exemple ; chaque
configuration lit dans cette table les scores de ses propres nœuds. Le nombre de calculs
reporté est celui que la méthode ferait seule : c'est son coût, pas celui de la grille.

**Le split test n'est pas lu.** Aucun appel réseau.

Usage : python3 src/grille.py
"""

import random
import statistics
import time
from collections import defaultdict

import classify
import config
import grasp


METHODES = ("descente", "tous", "racines")
NOMS_METHODES = {"descente": "descente", "tous": "exhaustif tous nœuds",
                 "racines": "exhaustif racines"}

# Structure « arbre » : aucune coupe. Représentée par None à côté des seuils.
ARBRE = None
STRUCTURES = (ARBRE,) + config.GRILLE_SEUILS

# Les configurations de référence : (représentation, structure, méthode) -> étiquette.
# L'article est « union + forêt à 0,50 + exhaustif » : ses deux variantes d'exhaustif
# sont marquées, Trim étant son réglage principal. La méthode du cours ne fixe pas la
# représentation : les deux sont marquées.
REFERENCES = {
    ("union", 0.5, "racines"): "article (Trim)",
    ("union", 0.5, "tous"): "article (No Trim)",
    ("union", ARBRE, "descente"): "cours (union)",
    ("somme", ARBRE, "descente"): "cours (somme)",
}
CLE_VOISIN = ("—", "feuilles", "voisin")


# ---------------------------------------------------------------------------
# Plis
# ---------------------------------------------------------------------------

def decouper_plis(lignes_train, graine=None):
    """Attribue un pli à chaque ligne, stratifié par type. Retourne relation -> liste.

    Un seul générateur à graine fixe, types parcourus dans l'ordre alphabétique : on
    mélange les rangs, et le rang mélangé divisé par la taille d'un pli donne le pli.
    L'ordre des lignes, lui, n'est pas touché : il départage les ex aequo."""
    tirage = random.Random(config.GRAINE_ALEATOIRE if graine is None else graine)
    plis = {}
    for relation in sorted(lignes_train):
        n = len(lignes_train[relation])
        rangs = list(range(n))
        tirage.shuffle(rangs)
        taille = n // config.GRILLE_PLIS
        pli_de = [0] * n
        for position, rang in enumerate(rangs):
            pli_de[rang] = min(position // taille, config.GRILLE_PLIS - 1)
        plis[relation] = pli_de
    return plis


def separer(lignes_train, plis, pli):
    """Sépare apprentissage et validation pour un pli. Retourne (relation -> liste, liste).

    Les deux gardent l'ordre du corpus."""
    apprentissage, validation = {}, []
    for relation in sorted(lignes_train):
        lignes = lignes_train[relation]
        apprentissage[relation] = [l for i, l in enumerate(lignes)
                                   if plis[relation][i] != pli]
        validation += [l for i, l in enumerate(lignes) if plis[relation][i] == pli]
    return apprentissage, validation


# ---------------------------------------------------------------------------
# Coupe de l'arbre en forêt
# ---------------------------------------------------------------------------

def fusions_du_type(noeuds, relation):
    """Nœuds internes d'un type dans l'ordre des fusions. Retourne une liste de nœuds.

    L'identifiant d'un nœud interne croît avec son rang de fusion."""
    return [n for _, n in sorted(noeuds.items())
            if n["rt"] == relation and not grasp.est_feuille(n)]


def fusions_gardees(fusions, seuil):
    """Fusions antérieures à la première dont le lien est sous le seuil. Retourne une liste.

    Sans seuil, toutes : c'est l'arbre complet."""
    if seuil is ARBRE:
        return fusions
    for rang, noeud in enumerate(fusions):
        if noeud["hauteur"] < seuil:
            return fusions[:rang]
    return fusions


def structure(noeuds, parents, seuil):
    """La forêt au seuil donné. Retourne un dict : ids, racines, comptes par type.

    Les racines sont les nœuds de la forêt dont le parent n'y est pas, orphelines
    comprises."""
    ids, racines, par_type = [], [], {}
    types = sorted({n["rt"] for n in noeuds.values()})
    for relation in types:
        feuilles = [i for i, n in sorted(noeuds.items())
                    if n["rt"] == relation and grasp.est_feuille(n)]
        internes = [n["id"] for n in fusions_gardees(fusions_du_type(noeuds, relation),
                                                     seuil)]
        du_type = feuilles + internes
        gardes = set(du_type)
        tetes = [i for i in du_type if parents[i] not in gardes]
        ids += du_type
        racines += tetes
        par_type[relation] = (len(du_type), len(tetes))
    return {"ids": sorted(ids), "racines": sorted(racines), "par_type": par_type}


# ---------------------------------------------------------------------------
# Classification à partir d'une table de scores
# ---------------------------------------------------------------------------

def meilleur_parmi(scores, identifiants):
    """Le candidat de meilleur score, plus petit identifiant à égalité. Retourne un id."""
    meilleur, meilleur_score = None, -1.0
    for identifiant in identifiants:
        if scores[identifiant] > meilleur_score:
            meilleur, meilleur_score = identifiant, scores[identifiant]
    return meilleur


def descendre_scores(scores, noeuds, racine):
    """Descente dans un arbre de la forêt, scores déjà connus. Retourne (arrêt, calculs).

    Même règle qu'en classify.descendre : on descend tant que le meilleur enfant fait
    STRICTEMENT mieux ; à égalité entre enfants, le premier."""
    courant, calculs = racine, 1
    while not grasp.est_feuille(noeuds[courant]):
        enfants = noeuds[courant]["enfants"]
        calculs += len(enfants)
        meilleur = meilleur_parmi(scores, enfants)
        if scores[meilleur] <= scores[courant]:
            break
        courant = meilleur
    return courant, calculs


def classer_descente(scores, noeuds, racines):
    """Descend chaque arbre de la forêt, garde la meilleure réponse. Retourne (id, calculs)."""
    reponses, calculs = [], 0
    for racine in racines:
        arret, cout = descendre_scores(scores, noeuds, racine)
        reponses.append(arret)
        calculs += cout
    return meilleur_parmi(scores, sorted(reponses)), calculs


def classer(methode, scores, noeuds, forme):
    """Applique une méthode de classification à une forêt. Retourne (id, calculs)."""
    if methode == "descente":
        return classer_descente(scores, noeuds, forme["racines"])
    candidats = forme["ids"] if methode == "tous" else forme["racines"]
    return meilleur_parmi(scores, candidats), len(candidats)


def prediction(ligne, identifiant, calculs, noeuds, contexte):
    """Ce qu'on retient d'une prédiction. Retourne un dict.

    `contexte` donne les racines de la forêt et le nombre d'exemples de chaque type :
    le poids relatif du nœud gagnant vaut 1 quand il couvre tout son type."""
    noeud = noeuds[identifiant]
    return {"attendu": ligne["rt"], "predit": noeud["rt"],
            "correct": noeud["rt"] == ligne["rt"],
            "interne": not grasp.est_feuille(noeud), "calculs": calculs,
            "racine": identifiant in contexte["racines"],
            "poids_relatif": noeud["poids"] / contexte["tailles"][noeud["rt"]]}



def table_de_scores(ligne, signatures, noeuds):
    """Score de la ligne contre chaque nœud de l'arbre complet. Retourne id -> score."""
    signature_a, signature_b = grasp.cotes_de_ligne(ligne, signatures)
    return {i: classify.score_noeud(signature_a, signature_b, n) for i, n in noeuds.items()}


# ---------------------------------------------------------------------------
# Un pli
# ---------------------------------------------------------------------------

def mesurer(predictions, types, formes_par_type):
    """F1 macro et coûts d'une configuration sur un pli. Retourne un dict."""
    evaluation = classify.evaluer(predictions, types)
    return {"f1": evaluation["f1"],
            "interne": sum(p["interne"] for p in predictions) / len(predictions),
            "racine": sum(p["racine"] for p in predictions) / len(predictions),
            "poids_relatif": statistics.fmean(p["poids_relatif"] for p in predictions),
            "calculs": statistics.fmean(p["calculs"] for p in predictions),
            "noeuds": statistics.fmean(n for n, _ in formes_par_type.values()),
            "racines": statistics.fmean(r for _, r in formes_par_type.values())}


def evaluer_representation(apprentissage, validation, signatures, representation, types):
    """Construit les arbres d'une représentation, classe la validation dans toutes les
    configurations. Retourne (configuration -> mesures, table des scores)."""
    depart = grasp.feuilles_de_depart(apprentissage, signatures)
    noeuds, _, _ = grasp.construire_foret(depart, representation)
    parents = classify.parents_des_noeuds(noeuds)
    formes = {seuil: structure(noeuds, parents, seuil) for seuil in STRUCTURES}
    tables = [table_de_scores(ligne, signatures, noeuds) for ligne in validation]
    tailles = classify.tailles_des_types(noeuds)

    resultats = {}
    for seuil, forme in formes.items():
        contexte = {"racines": set(forme["racines"]), "tailles": tailles}
        for methode in METHODES:
            predictions = []
            for ligne, scores in zip(validation, tables):
                identifiant, calculs = classer(methode, scores, noeuds, forme)
                predictions.append(prediction(ligne, identifiant, calculs, noeuds,
                                              contexte))
            resultats[(representation, seuil, methode)] = mesurer(
                predictions, types, forme["par_type"])
    return resultats, noeuds, tables


def evaluer_voisin(validation, noeuds, tables, types):
    """Le plus proche voisin sur les feuilles seules. Retourne des mesures."""
    feuilles = [i for i in sorted(noeuds) if grasp.est_feuille(noeuds[i])]
    contexte = {"racines": set(feuilles), "tailles": classify.tailles_des_types(noeuds)}
    predictions = [prediction(ligne, meilleur_parmi(scores, feuilles), len(feuilles),
                              noeuds, contexte)
                   for ligne, scores in zip(validation, tables)]
    par_type = defaultdict(int)
    for i in feuilles:
        par_type[noeuds[i]["rt"]] += 1
    return mesurer(predictions, types, {rt: (n, n) for rt, n in par_type.items()})


def evaluer_pli(lignes_train, plis, pli, signatures, types):
    """Toutes les configurations sur un pli. Retourne configuration -> mesures."""
    apprentissage, validation = separer(lignes_train, plis, pli)
    resultats = {}
    for representation in grasp.REPRESENTATIONS:
        mesures, noeuds, tables = evaluer_representation(
            apprentissage, validation, signatures, representation, types)
        resultats.update(mesures)
        if representation == "union":
            resultats[CLE_VOISIN] = evaluer_voisin(validation, noeuds, tables, types)
    return resultats


# ---------------------------------------------------------------------------
# Agrégation sur les plis
# ---------------------------------------------------------------------------

def agreger(par_pli):
    """Moyennes et écart-type du F1 sur les plis. Retourne configuration -> dict.

    L'écart-type est celui de l'échantillon des 5 plis (dénominateur n − 1)."""
    agregat = {}
    for cle in par_pli[0]:
        lot = [resultats[cle] for resultats in par_pli]
        f1 = [m["f1"] for m in lot]
        agregat[cle] = {"cle": cle, "f1": statistics.fmean(f1),
                        "ecart": statistics.stdev(f1), "f1_plis": f1,
                        **{k: statistics.fmean(m[k] for m in lot)
                           for k in ("interne", "racine", "poids_relatif", "calculs",
                                     "noeuds", "racines")}}
    return agregat


def classement(agregat):
    """Configurations par F1 moyen décroissant. Retourne une liste.

    À égalité, la moins coûteuse en calculs d'abord."""
    return sorted(agregat.values(), key=lambda c: (-c["f1"], c["calculs"], str(c["cle"])))


def indistinguables(rangees):
    """Configurations à moins d'un écart-type de la meilleure. Retourne une liste.

    Règle : F1 moyen ≥ F1 moyen de la meilleure − son écart-type."""
    meilleure = rangees[0]
    plancher = meilleure["f1"] - meilleure["ecart"]
    return [c for c in rangees if c["f1"] >= plancher]


# ---------------------------------------------------------------------------
# Mise en forme
# ---------------------------------------------------------------------------

fr, pct, tableau = grasp.fr, grasp.pct, grasp.tableau


def nom_structure(seuil):
    """Libellé d'une structure. Retourne une chaîne."""
    return "arbre" if seuil is ARBRE else f"forêt {fr(seuil, 2)}"


def libelle(cle):
    """Libellé complet d'une configuration. Retourne une chaîne."""
    if cle == CLE_VOISIN:
        return "plus proche voisin (feuilles)"
    representation, seuil, methode = cle
    return f"{representation} · {nom_structure(seuil)} · {NOMS_METHODES[methode]}"


def etiquette_reference(cle):
    """Nom de la référence que représente une configuration, ou vide. Retourne une chaîne."""
    if cle == CLE_VOISIN:
        return "plus proche voisin"
    return REFERENCES.get(cle, "")


def f1_avec_ecart(config_):
    """F1 moyen ± écart-type. Retourne une chaîne."""
    return f"{fr(config_['f1'])} ± {fr(config_['ecart'])}"


# ---------------------------------------------------------------------------
# Courbes (SVG, sans dépendance)
# ---------------------------------------------------------------------------

COULEURS = {"union": "#2a78d6", "somme": "#eb6834"}
ENCRE, ENCRE_2, GRILLE_TRAIT, SURFACE = "#0b0b0b", "#52514e", "#e4e3de", "#fcfcfb"


def graduations(bas, haut):
    """Graduations tous les dixièmes entre deux bornes. Retourne une liste."""
    return [k / 10 for k in range(int(round(bas * 10)), int(round(haut * 10)) + 1)]


def echelle(valeur, bas, haut, debut, fin):
    """Projette une valeur d'un intervalle sur un autre. Retourne un flottant."""
    return debut + (valeur - bas) / (haut - bas) * (fin - debut)


def svg_panneau(agregat, methode, x0, largeur, y_haut, y_bas, f1_bas, f1_haut, voisin):
    """Un panneau : F1 contre seuil pour les deux représentations. Retourne des lignes SVG."""
    seuils = list(config.GRILLE_SEUILS)
    marge = 0.035
    x_arbre = x0 + largeur - 14

    def x_de(seuil):
        if seuil is ARBRE:
            return x_arbre
        return echelle(seuil, seuils[0] - marge, seuils[-1] + marge, x0, x_arbre - 34)

    def y_de(f1):
        return echelle(f1, f1_bas, f1_haut, y_bas, y_haut)

    sortie = [f'<text x="{x0}" y="{y_haut - 14}" font-size="13" font-weight="600" '
              f'fill="{ENCRE}">{NOMS_METHODES[methode]}</text>']
    for graduation in graduations(f1_bas, f1_haut):
        y = y_de(graduation)
        sortie.append(f'<line x1="{x0}" x2="{x0 + largeur}" y1="{y:.1f}" y2="{y:.1f}" '
                      f'stroke="{GRILLE_TRAIT}" stroke-width="1"/>')
    y_voisin = y_de(voisin)
    sortie.append(f'<line x1="{x0}" x2="{x0 + largeur}" y1="{y_voisin:.1f}" '
                  f'y2="{y_voisin:.1f}" stroke="{ENCRE_2}" stroke-width="1"/>')
    for seuil in seuils[::2]:
        sortie.append(f'<text x="{x_de(seuil):.1f}" y="{y_bas + 16}" font-size="10" '
                      f'text-anchor="middle" fill="{ENCRE_2}">{fr(seuil, 2)}</text>')
    sortie.append(f'<text x="{x_arbre:.1f}" y="{y_bas + 16}" font-size="10" '
                  f'text-anchor="middle" fill="{ENCRE_2}">arbre</text>')
    sortie.append(f'<line x1="{x_arbre - 20:.1f}" x2="{x_arbre - 20:.1f}" y1="{y_haut}" '
                  f'y2="{y_bas}" stroke="{GRILLE_TRAIT}" stroke-width="1"/>')

    for representation in grasp.REPRESENTATIONS:
        couleur = COULEURS[representation]
        points = [agregat[(representation, s, methode)] for s in seuils]
        haut = " ".join(f"{x_de(s):.1f},{y_de(p['f1'] + p['ecart']):.1f}"
                        for s, p in zip(seuils, points))
        bas = " ".join(f"{x_de(s):.1f},{y_de(p['f1'] - p['ecart']):.1f}"
                       for s, p in reversed(list(zip(seuils, points))))
        sortie.append(f'<polygon points="{haut} {bas}" fill="{couleur}" '
                      'fill-opacity="0.12" stroke="none"/>')
        trace = " ".join(f"{x_de(s):.1f},{y_de(p['f1']):.1f}" for s, p in zip(seuils, points))
        sortie.append(f'<polyline points="{trace}" fill="none" stroke="{couleur}" '
                      'stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>')
        for seuil in STRUCTURES:
            point = agregat[(representation, seuil, methode)]
            sortie.append(
                f'<circle cx="{x_de(seuil):.1f}" cy="{y_de(point["f1"]):.1f}" r="4" '
                f'fill="{couleur}" stroke="{SURFACE}" stroke-width="2">'
                f'<title>{representation} · {nom_structure(seuil)} · '
                f'{NOMS_METHODES[methode]} : F1 {fr(point["f1"])} ± '
                f'{fr(point["ecart"])}</title></circle>')
        for cle, nom in REFERENCES.items():
            if cle[0] == representation and cle[2] == methode:
                point = agregat[cle]
                sortie.append(f'<circle cx="{x_de(cle[1]):.1f}" '
                              f'cy="{y_de(point["f1"]):.1f}" r="8" fill="none" '
                              f'stroke="{ENCRE}" stroke-width="1.5"/>')
                sortie.append(f'<text x="{x_de(cle[1]):.1f}" '
                              f'y="{y_de(point["f1"]) - 12:.1f}" font-size="10" '
                              f'text-anchor="middle" fill="{ENCRE}">{nom}</text>')
    return sortie


def svg_courbes(agregat):
    """Trois panneaux côte à côte, un par méthode. Retourne le texte SVG."""
    largeur_panneau, espace, gauche = 290, 34, 44
    largeur = gauche + 3 * largeur_panneau + 2 * espace + 16
    y_haut, y_bas, hauteur = 78, 318, 372
    valeurs = [c["f1"] + s * c["ecart"] for c in agregat.values() for s in (-1, 1)]
    f1_bas = max(0.0, round(min(valeurs) - 0.05, 1))
    f1_haut = min(1.0, round(max(valeurs) + 0.05, 1))
    voisin = agregat[CLE_VOISIN]["f1"]
    sortie = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {largeur} {hauteur}" '
              f'width="{largeur}" height="{hauteur}" font-family="system-ui, sans-serif">',
              f'<rect width="{largeur}" height="{hauteur}" fill="{SURFACE}"/>',
              f'<text x="{gauche}" y="22" font-size="15" font-weight="600" '
              f'fill="{ENCRE}">F1 macro en validation croisée selon le seuil de coupe'
              '</text>',
              f'<text x="{gauche}" y="40" font-size="11" fill="{ENCRE_2}">Moyenne sur '
              f'{config.GRILLE_PLIS} plis, bande = ± 1 écart-type. « arbre » = aucune '
              f'coupe. Ligne grise : plus proche voisin ({fr(voisin)}). Cercles : '
              'configurations de référence.</text>']
    legende_x = largeur - 190
    for rang, representation in enumerate(grasp.REPRESENTATIONS):
        x = legende_x + rang * 90
        sortie.append(f'<line x1="{x}" x2="{x + 18}" y1="18" y2="18" '
                      f'stroke="{COULEURS[representation]}" stroke-width="2"/>')
        sortie.append(f'<circle cx="{x + 9}" cy="18" r="4" '
                      f'fill="{COULEURS[representation]}"/>')
        sortie.append(f'<text x="{x + 24}" y="22" font-size="11" '
                      f'fill="{ENCRE}">{representation}</text>')
    for graduation in graduations(f1_bas, f1_haut):
        y = echelle(graduation, f1_bas, f1_haut, y_bas, y_haut)
        sortie.append(f'<text x="{gauche - 6}" y="{y + 3:.1f}" font-size="10" '
                      f'text-anchor="end" fill="{ENCRE_2}">{fr(graduation, 1)}</text>')
    for rang, methode in enumerate(METHODES):
        x0 = gauche + rang * (largeur_panneau + espace)
        sortie += svg_panneau(agregat, methode, x0, largeur_panneau, y_haut, y_bas,
                              f1_bas, f1_haut, voisin)
    sortie.append(f'<text x="{largeur / 2:.0f}" y="{hauteur - 12}" font-size="11" '
                  f'text-anchor="middle" fill="{ENCRE_2}">seuil de coupe t</text>')
    sortie.append("</svg>")
    return "\n".join(sortie) + "\n"


# ---------------------------------------------------------------------------
# Rapport
# ---------------------------------------------------------------------------

def rang_de(rangees, cle):
    """Rang d'une configuration dans le classement, à partir de 1. Retourne un entier."""
    return next(i for i, c in enumerate(rangees, 1) if c["cle"] == cle)


def ligne_complete(rang, c):
    """Une ligne du tableau complet. Retourne une liste de cellules."""
    reference = etiquette_reference(c["cle"])
    return [rang, libelle(c["cle"]) + (f" — **{reference}**" if reference else ""),
            f"**{fr(c['f1'])}**", fr(c["ecart"]), fr(c["noeuds"], 1),
            fr(c["racines"], 1), pct(c["interne"], 1), fr(c["poids_relatif"], 2),
            fr(c["calculs"], 0)]


ENTETE_COMPLET = ["rang", "configuration", "F1 moyen", "écart-type", "nœuds / type",
                  "racines / type", "prédictions internes", "poids relatif gagnant",
                  "calculs / exemple"]


def section_dispositif(n_train, n_plis, duree):
    """1 : protocole. Retourne des lignes."""
    return ["## 1. Dispositif", "",
            f"- **Validation croisée** sur les {n_train} exemples d'entraînement : "
            f"{n_plis} plis stratifiés par type (10 exemples par type et par pli), "
            f"`random.Random({config.GRAINE_ALEATOIRE})`. **Le test n'est pas lu.**",
            "- Pour chaque pli et chaque représentation, **un arbre complet par type** "
            "est construit sur les 4 autres plis (40 exemples par type) ; toutes les "
            "coupes et les trois classifications en découlent.",
            "- **Représentations** : « union » (ensemble des symboles, `similarite()` "
            "inchangée) et « somme » (comptes par symbole, cosinus sur vecteurs — revient "
            "à comparer au centroïde). Un exemple à classer est un vecteur de 1.",
            f"- **Structures** : l'arbre complet, et la forêt coupée à t = "
            f"{fr(config.GRILLE_SEUILS[0], 2)} … {fr(config.GRILLE_SEUILS[-1], 2)} par pas "
            "de 0,05. La forêt à t garde les fusions effectuées **avant la première "
            "fusion de lien < t** : l'ordre des fusions fait foi, pas les hauteurs, que "
            "les inversions rendent non monotones.",
            "- **Classifications** : descente dans chaque arbre de la forêt ; exhaustif "
            "sur tous les nœuds de la forêt (No Trim) ; exhaustif sur ses racines, "
            "orphelines comprises (Trim). Score : formule 3, moyenne des deux côtés. "
            "Lien de construction : minimum des deux côtés.",
            "- **Nombre de calculs** : scores que la méthode calcule seule pour un "
            "exemple. La grille, elle, calcule chaque nœud une fois et le relit.",
            "- **Écart-type** : sur les 5 valeurs de F1 des plis, dénominateur n − 1.",
            f"- Durée totale : {fr(duree, 0)} s.", ""]


def section_references(rangees):
    """2 : où se placent les configurations de référence. Retourne des lignes."""
    corps = []
    for cle, nom in list(REFERENCES.items()) + [(CLE_VOISIN, "plus proche voisin")]:
        c = next(c for c in rangees if c["cle"] == cle)
        corps.append([f"**{nom}**", libelle(cle), f"{rang_de(rangees, cle)} / {len(rangees)}",
                      f1_avec_ecart(c), pct(c["interne"], 1), pct(c["racine"], 0),
                      fr(c["poids_relatif"], 2), fr(c["calculs"], 0)])
    return (["## 2. Les configurations de référence", "",
             "L'article est « union + forêt à 0,50 + exhaustif » ; ses deux variantes "
             "d'exhaustif sont données, Trim étant son réglage principal. La méthode du "
             "cours — arbre complet + descente — ne fixe pas la représentation : les deux "
             "sont données.", ""]
            + tableau(["référence", "configuration", "rang", "F1 moyen ± é.-t.",
                       "prédictions internes", "prédictions par une racine",
                       "poids relatif gagnant", "calculs / exemple"], corps)
            + ["", "« poids relatif gagnant » : poids du nœud qui fait la prédiction divisé "
               "par le nombre d'exemples de son type, en moyenne. 1 = le nœud couvre tout "
               "le type ; 1/40 = une feuille.", ""])


def section_meilleure(rangees):
    """3 : la meilleure configuration et ses ex aequo statistiques. Retourne des lignes."""
    meilleure = rangees[0]
    proches = indistinguables(rangees)
    plancher = meilleure["f1"] - meilleure["ecart"]
    corps = [ligne_complete(rang_de(rangees, c["cle"]), c) for c in proches]
    return (["## 3. Meilleure configuration", "",
             f"**{libelle(meilleure['cle'])}** : F1 {f1_avec_ecart(meilleure)}.", "",
             f"Configurations qui ne s'en distinguent pas au-delà d'un écart-type — F1 "
             f"moyen ≥ {fr(meilleure['f1'])} − {fr(meilleure['ecart'])} = "
             f"{fr(plancher)} : **{len(proches)}** sur {len(rangees)}.", ""]
            + tableau(ENTETE_COMPLET, corps) + [""])


def section_lecture(agregat, rangees):
    """3 bis : ce que fait vraiment la meilleure configuration. Retourne des lignes."""
    meilleure = rangees[0]
    centroide = agregat[("somme", ARBRE, "racines")]
    union_arbre = agregat[("union", ARBRE, "racines")]
    meilleure_union = next(c for c in rangees if c["cle"][0] == "union")
    return ["### 3.1 Lecture", "",
            f"- **La meilleure configuration prédit surtout par des nœuds très lourds.** "
            f"{pct(meilleure['racine'], 0)} de ses prédictions viennent d'une racine de la "
            f"forêt, et le nœud gagnant couvre en moyenne {pct(meilleure['poids_relatif'], 0)} "
            "de son type.",
            f"- **somme · arbre · exhaustif racines** compare l'exemple aux quinze seules "
            f"racines, soit au centroïde de chaque type : F1 {f1_avec_ecart(centroide)}, "
            f"pour {fr(centroide['calculs'], 0)} calculs. La meilleure configuration fait "
            f"{classify.ecart_signe(meilleure['f1'] - centroide['f1'])} par rapport à ce "
            "classifieur par centroïde. **L'essentiel du gain vient de la représentation "
            "somme, pas de l'arbre.**",
            f"- La même comparaison aux racines en union donne {f1_avec_ecart(union_arbre)} : "
            "en union, un symbole porté par un seul exemple du type pèse autant qu'un "
            "symbole porté par tous, et la racine est pénalisée pour chacun d'eux. En "
            "somme, la norme du nœud est dominée par les symboles que partagent beaucoup "
            "d'exemples : ce qui est typique du type compte, l'accidentel s'efface. C'est "
            "le biais de rapport_arbres.md vu de l'autre côté — le gros nœud y perdait, "
            "il devient ici le meilleur candidat.",
            f"- La meilleure configuration en union est **{libelle(meilleure_union['cle'])}**, "
            f"F1 {f1_avec_ecart(meilleure_union)}, rang "
            f"{rang_de(rangees, meilleure_union['cle'])}.", ""]


def section_courbes(agregat, nom_svg):
    """4 : F1 contre seuil, en figure et en tableau. Retourne des lignes."""
    lignes = ["## 4. F1 en fonction du seuil", "",
              f"![F1 macro selon le seuil de coupe]({nom_svg})", "",
              "Même contenu en tableau (F1 moyen ; l'écart-type est au tableau complet) :",
              ""]
    corps = []
    for representation in grasp.REPRESENTATIONS:
        for methode in METHODES:
            corps.append([representation, NOMS_METHODES[methode]]
                         + [fr(agregat[(representation, s, methode)]["f1"])
                            for s in STRUCTURES[1:] + (ARBRE,)])
    lignes += tableau(["représentation", "classification"]
                      + [fr(s, 2) for s in config.GRILLE_SEUILS] + ["arbre"], corps)
    lignes += ["", f"Plus proche voisin : {f1_avec_ecart(agregat[CLE_VOISIN])}.", ""]
    return lignes


def section_complete(rangees):
    """5 : toutes les configurations, triées par F1 moyen. Retourne des lignes."""
    corps = [ligne_complete(rang, c) for rang, c in enumerate(rangees, 1)]
    return (["## 5. Tableau complet", "",
             "Trié par F1 moyen décroissant ; à égalité, la moins coûteuse d'abord. "
             "« nœuds / type » et « racines / type » sont moyennés sur les 15 types et "
             "les 5 plis.", ""]
            + tableau(ENTETE_COMPLET, corps) + [""])


def construire_rapport(agregat, n_train, duree):
    """Écrit reports/rapport_grille.md et sa figure. Ne retourne rien."""
    rangees = classement(agregat)
    config.FICHIER_COURBES_GRILLE.write_text(svg_courbes(agregat), encoding="utf-8")
    lignes = ["# Grille d'options en validation croisée", "",
              "Représentation × structure × classification, comparées sur l'entraînement "
              "seul. Une configuration sera retenue pour l'évaluation sur le test, "
              "qui n'a pas encore été lu.", ""]
    lignes += section_dispositif(n_train, config.GRILLE_PLIS, duree)
    lignes += section_references(rangees)
    lignes += section_meilleure(rangees)
    lignes += section_lecture(agregat, rangees)
    lignes += section_courbes(agregat, config.FICHIER_COURBES_GRILLE.name)
    lignes += section_complete(rangees)
    config.FICHIER_RAPPORT_GRILLE.write_text("\n".join(lignes), encoding="utf-8")
    print(f"Rapport : {config.FICHIER_RAPPORT_GRILLE}", flush=True)


# ---------------------------------------------------------------------------
# Enchaînement
# ---------------------------------------------------------------------------

def main():
    signatures = grasp.charger_signatures()
    lignes_train = grasp.charger_lignes("train")
    types = sorted(lignes_train)
    n_train = sum(len(l) for l in lignes_train.values())
    plis = decouper_plis(lignes_train)
    print(f"Entraînement : {n_train} exemples, {len(types)} types, "
          f"{config.GRILLE_PLIS} plis. Test non lu.", flush=True)

    debut = time.perf_counter()
    par_pli = []
    for pli in range(config.GRILLE_PLIS):
        par_pli.append(evaluer_pli(lignes_train, plis, pli, signatures, types))
        print(f"  pli {pli + 1}/{config.GRILLE_PLIS} : {len(par_pli[-1])} configurations, "
              f"{fr(time.perf_counter() - debut, 0)} s", flush=True)

    agregat = agreger(par_pli)
    meilleure = classement(agregat)[0]
    print(f"Meilleure : {libelle(meilleure['cle'])}, F1 {f1_avec_ecart(meilleure)}",
          flush=True)
    construire_rapport(agregat, n_train, time.perf_counter() - debut)


if __name__ == "__main__":
    main()
