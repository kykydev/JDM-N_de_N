#!/usr/bin/env python3
"""Expériences 1 et 2 de l'article avec les arbres et la descente (phase C).

Chaque configuration est un pipeline COMPLET : signatures restreintes aux traits
retenus, quinze arbres reconstruits, puis classement du test par descente. Se contenter
d'ignorer des symboles à la classification donnerait des arbres construits sur une
autre représentation que celle qu'on évalue.

  - Expérience 1 : H, H+SST, H+TRT, H+TRT+SST (Tableau 2 de l'article) ;
  - Expérience 2 : avec et sans annotations morphologiques de JDM, avec et sans trait
    de définitude (Tableau 4, étendu).

L'Expérience 3 (élagage) n'a plus d'objet telle quelle : la comparaison entre la
descente et l'exhaustif sur tous les nœuds, en phase B, oppose elle aussi coût et
qualité.

Le plus proche voisin sur les feuilles est reclassé pour chaque configuration : il dit
ce que valent les traits indépendamment de la descente.

Aucun appel réseau, aucune recollecte.

Usage : python3 src/evaluate.py
"""

import json
import time

import classify
import config
import grasp
import signatures as sig


# Scores publiés par l'article : Tableau 2 (traits) et Tableau 4 (définitude).
ARTICLE_TRAITS = {"H": 0.653, "H+SST": 0.691, "H+TRT": 0.767, "H+TRT+SST": 0.772}
ARTICLE_DEFINITUDE = {"H+TRT+SST": 0.772, "H+TRT+SST+DEF": 0.795}

# F1 de la méthode à seuil précédente, sur le même test, avant son remplacement.
ANCIEN = {"H": 0.443, "H+SST": 0.471, "H+TRT": 0.514, "H+TRT+SST": 0.597,
          "H+TRT+SST sans morpho": 0.591, "H+TRT+SST+DEF": 0.570,
          "H+TRT+SST sans morpho +DEF": 0.566}

# Préfixe des symboles de définitude ajoutés à la signature de B (Expérience 2).
PREFIXE_DEF = "DEF:"

# Les configurations, dans l'ordre des tableaux : (nom, traits, sans morpho, définitude).
EXPERIENCE_1 = (("H", {"H"}, False, False),
                ("H+SST", {"H", "SST"}, False, False),
                ("H+TRT", {"H", "TRT"}, False, False),
                ("H+TRT+SST", {"H", "TRT", "SST"}, False, False))
EXPERIENCE_2 = (("H+TRT+SST sans morpho", {"H", "TRT", "SST"}, True, False),
                ("H+TRT+SST+DEF", {"H", "TRT", "SST"}, False, True),
                ("H+TRT+SST sans morpho +DEF", {"H", "TRT", "SST"}, True, True))


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
    return {terme: signature_de_terme(terme, collecte.get(terme), traits, seuils,
                                      sans_morpho)
            for terme in sorted(termes)}


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
    gauche, droite = grasp.cotes_de_ligne(ligne, signatures)
    if avec_definitude:
        droite |= symboles_definitude(ligne)
    return gauche, droite


# ---------------------------------------------------------------------------
# Pipeline d'une configuration
# ---------------------------------------------------------------------------

def feuilles_de_configuration(lignes_train, signatures, avec_definitude):
    """Les feuilles de départ d'une configuration. Retourne relation -> liste de dicts."""
    depart = {}
    for relation in sorted(lignes_train):
        depart[relation] = []
        for ligne in lignes_train[relation]:
            gauche, droite = cotes_de_ligne(ligne, signatures, avec_definitude)
            depart[relation].append({"syntagme": ligne["syntagme"],
                                     "sL": gauche, "sR": droite})
    return depart


def classer_configuration(lignes_test, signatures, noeuds, racines, avec_definitude):
    """Classe le test par descente et par plus proche voisin. Retourne un dict."""
    feuilles = [noeuds[i] for i in sorted(noeuds) if grasp.est_feuille(noeuds[i])]
    descente, voisin = [], []
    debut = time.perf_counter()
    for ligne in lignes_test:
        gauche, droite = cotes_de_ligne(ligne, signatures, avec_definitude)
        resultat = classify.classer_par_descente(gauche, droite, noeuds, racines)
        descente.append(classify.prediction_descente(ligne, resultat, noeuds))
        identifiant, score, _ = classify.classer_exhaustif(gauche, droite, feuilles)
        voisin.append(classify.prediction_exhaustive(ligne, identifiant, score, noeuds,
                                                     len(feuilles)))
    return {"descente": descente, "voisin": voisin,
            "duree": time.perf_counter() - debut}


def pipeline(configuration, donnees):
    """Signatures, arbres, classification pour une configuration. Retourne un dict."""
    nom, traits, sans_morpho, avec_definitude = configuration
    signatures = construire_signatures(donnees["collecte"], donnees["termes"], traits,
                                       sans_morpho)
    depart = feuilles_de_configuration(donnees["train"], signatures, avec_definitude)
    noeuds, racines, _ = grasp.construire_foret(depart)
    classes = classer_configuration(donnees["test"], signatures, noeuds, racines,
                                    avec_definitude)
    types = donnees["types"]
    resultat = {
        "nom": nom, "signatures": signatures, "n_noeuds": len(noeuds),
        "descente": classify.evaluer(classes["descente"], types),
        "voisin": classify.evaluer(classes["voisin"], types),
        "part_interne": classify.part_interne(classes["descente"]),
        "taille_racines": sum(len(noeuds[r]["sL"]) + len(noeuds[r]["sR"])
                              for r in racines.values()) / (2 * len(racines)),
        "duree": classes["duree"],
    }
    print(f"  {nom:28s} descente F1 {grasp.fr(resultat['descente']['f1'])}, "
          f"plus proche voisin F1 {grasp.fr(resultat['voisin']['f1'])}, "
          f"{grasp.pct(resultat['part_interne'])} internes", flush=True)
    return resultat


# ---------------------------------------------------------------------------
# Rapport de phase C
# ---------------------------------------------------------------------------

fr, pct, tableau, ecart_signe = grasp.fr, grasp.pct, grasp.tableau, classify.ecart_signe


def ligne_de_tableau(resultat, article):
    """Une ligne des tableaux d'expérience. Retourne une liste de cellules."""
    descente, voisin = resultat["descente"], resultat["voisin"]
    return [f"**{resultat['nom']}**", fr(100 * descente["precision"], 1),
            fr(100 * descente["rappel"], 1), f"**{fr(descente['f1'])}**",
            pct(resultat["part_interne"], 0), fr(voisin["f1"]),
            fr(ANCIEN[resultat["nom"]]), fr(article) if article is not None else "—",
            fr(resultat["taille_racines"], 0)]


ENTETE = ["configuration", "P (%)", "R (%)", "F1 descente", "prédictions internes",
          "F1 plus proche voisin", "F1 méthode à seuil", "F1 article",
          "taille moy. d'un côté de racine"]


def section_dispositif():
    """C.1 : ce qui est refait et comment. Retourne des lignes."""
    return ["## C. Expériences de l'article avec la nouvelle méthode", "",
            "### C.1 Dispositif", "",
            "- Chaque configuration est un **pipeline complet** : signatures restreintes "
            "aux traits retenus, quinze arbres **reconstruits** sur les 50 exemples "
            "d'entraînement de chaque type, puis classement des 450 exemples de test "
            "par descente.",
            "- Pour chaque configuration, le **plus proche voisin** sur les 750 feuilles "
            "est aussi classé. Il dit ce que valent les traits indépendamment de la "
            "descente, dont la phase B a montré le biais.",
            "- Colonnes de référence : la méthode à seuil précédente, sur le même test, "
            "et l'article.",
            "- **Expérience 3** (élagage) : n'a plus d'objet telle quelle. La "
            "comparaison entre (b), l'exhaustif sur les 1485 nœuds, et (c), la "
            "descente, en partie B.2, oppose elle aussi coût et qualité.", ""]


def section_experience_1(resultats):
    """C.2 : apport de chaque trait. Retourne des lignes."""
    corps = [ligne_de_tableau(resultats[nom], ARTICLE_TRAITS[nom])
             for nom, _, _, _ in EXPERIENCE_1]
    base, complet = resultats["H"], resultats["H+TRT+SST"]
    noms = [nom for nom, _, _, _ in EXPERIENCE_1]
    return (["### C.2 Expérience 1 — apport de chaque trait (Tableau 2)", ""]
            + tableau(ENTETE, corps)
            + ["",
               f"- De H seul à la configuration complète : descente "
               f"{ecart_signe(complet['descente']['f1'] - base['descente']['f1'])}, plus "
               f"proche voisin "
               f"{ecart_signe(complet['voisin']['f1'] - base['voisin']['f1'])}, méthode "
               f"à seuil {ecart_signe(ANCIEN['H+TRT+SST'] - ANCIEN['H'])}, article "
               f"{ecart_signe(ARTICLE_TRAITS['H+TRT+SST'] - ARTICLE_TRAITS['H'])}.",
               "- " + ("L'ordre des configurations de l'article est **reproduit par le "
                       "plus proche voisin**"
                       if croissant([resultats[n]["voisin"]["f1"] for n in noms]) else
                       "Le plus proche voisin ne reproduit pas l'ordre de l'article")
               + (", et **pas par la descente** : ses écarts entre configurations "
                  "reflètent le biais de B.7 plus que la valeur des traits."
                  if not croissant([resultats[n]["descente"]["f1"] for n in noms])
                  else ", et par la descente."),
               "- La dernière colonne donne la taille moyenne d'un côté de racine : "
               "chaque trait ajouté élargit les nœuds lourds, pas les feuilles.", ""])


def croissant(valeurs):
    """Dit si une suite est strictement croissante. Retourne un booléen."""
    return all(a < b for a, b in zip(valeurs, valeurs[1:]))


def section_experience_2(resultats):
    """C.3 : trait de définitude, avec et sans annotations morphologiques. Retourne des lignes."""
    noms = ("H+TRT+SST",) + tuple(nom for nom, _, _, _ in EXPERIENCE_2)
    corps = []
    for nom in noms:
        corps.append(ligne_de_tableau(resultats[nom], ARTICLE_DEFINITUDE.get(nom)))
    reference = resultats["H+TRT+SST"]
    sans_morpho = resultats["H+TRT+SST sans morpho"]

    def ecarts(a, b):
        return (f"descente {ecart_signe(a['descente']['f1'] - b['descente']['f1'])}, "
                f"plus proche voisin {ecart_signe(a['voisin']['f1'] - b['voisin']['f1'])}")

    return (["### C.3 Expérience 2 — trait de définitude (Tableau 4)", "",
             "Deux symboles sont ajoutés à la signature de B : `DEF:Det` ou `DEF:NoDet`, "
             "et `DEF:Def` ou `DEF:NoDef`. Ils dépendent de la ligne et non du terme. "
             "Les deux lignes « sans morpho » retirent les annotations `DET`/`NODET` "
             "que JDM porte déjà, pour isoler ce que notre trait apporte.", ""]
            + tableau(ENTETE, corps)
            + ["",
               f"- Définitude ajoutée aux annotations de JDM : "
               f"{ecarts(resultats['H+TRT+SST+DEF'], reference)} (article "
               f"{ecart_signe(ARTICLE_DEFINITUDE['H+TRT+SST+DEF'] - ARTICLE_DEFINITUDE['H+TRT+SST'])}, "
               f"méthode à seuil "
               f"{ecart_signe(ANCIEN['H+TRT+SST+DEF'] - ANCIEN['H+TRT+SST'])}).",
               f"- Annotations morphologiques de JDM retirées : "
               f"{ecarts(sans_morpho, reference)}.",
               f"- Notre trait seul, annotations de JDM retirées : "
               f"{ecarts(resultats['H+TRT+SST sans morpho +DEF'], sans_morpho)}.", ""])


def section_coherence(resultats, signatures_fichier, f1_phase_b):
    """C.4 : la configuration complète recoupe-t-elle la phase B ? Retourne des lignes."""
    complet = resultats["H+TRT+SST"]
    identiques = complet["signatures"] == signatures_fichier
    meme_f1 = abs(complet["descente"]["f1"] - f1_phase_b) < classify.EPSILON
    return ["### C.4 Contrôle de cohérence", "",
            "La configuration H+TRT+SST reconstruit ses signatures depuis la collecte. "
            + ("Elles sont **identiques** à celles du fichier de signatures"
               if identiques else "Elles **diffèrent** de celles du fichier de signatures")
            + f", et son F1 de descente ({fr(complet['descente']['f1'])}) "
            + ("**égale** celui de la phase B."
               if meme_f1 else f"diffère de celui de la phase B ({fr(f1_phase_b)})."),
            ""]


def construire_rapport(resultats, signatures_fichier, f1_phase_b):
    """Écrit la partie C du rapport commun. Ne retourne rien."""
    lignes = section_dispositif()
    lignes += section_experience_1(resultats)
    lignes += section_experience_2(resultats)
    lignes += section_coherence(resultats, signatures_fichier, f1_phase_b)
    grasp.ecrire_partie_rapport("C", lignes)


# ---------------------------------------------------------------------------
# Enchaînement
# ---------------------------------------------------------------------------

def f1_de_phase_b():
    """Relit le F1 de descente écrit par classify.py. Retourne un flottant ou None."""
    if not classify.CHEMIN_PREDICTIONS.exists():
        return None
    charge = json.loads(classify.CHEMIN_PREDICTIONS.read_text(encoding="utf-8"))
    return charge["macro_stricte"]["f1"]


def main():
    corpus, _ = sig.charger_corpus()
    test = grasp.charger_lignes("test")
    donnees = {"collecte": sig.charger_collecte(), "termes": sig.termes_du_corpus(corpus),
               "train": grasp.charger_lignes("train"),
               "test": [l for rt in sorted(test) for l in test[rt]],
               "types": sorted(test)}
    print(f"Test : {len(donnees['test'])} exemples sur {len(donnees['types'])} types.",
          flush=True)

    resultats = {}
    for titre, configurations in (("Expérience 1 — traits", EXPERIENCE_1),
                                  ("Expérience 2 — définitude", EXPERIENCE_2)):
        print(titre, flush=True)
        for configuration in configurations:
            resultats[configuration[0]] = pipeline(configuration, donnees)

    f1_phase_b = f1_de_phase_b()
    construire_rapport(resultats, grasp.charger_signatures(),
                       f1_phase_b if f1_phase_b is not None else float("nan"))


if __name__ == "__main__":
    main()
