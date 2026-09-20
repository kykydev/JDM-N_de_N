#!/usr/bin/env python3
"""Étape 7 : prédire la relation d'un « A de B » quelconque, et expliquer la décision.

Rien de neuf ici : l'outil assemble ce que les étapes précédentes ont produit. Le
découpage A/B vient de corpus_check.py, l'accès au réseau de jdm_client.py, la
construction de signature de signatures.py, le calcul de score de classify.py, et les
règles de data/modeles/modele_final.json.

Trois modes : interactif, un syntagme en argument, ou un fichier de syntagmes vers un
CSV. Rien n'est réappris, rien n'est réévalué. Le corpus, la collecte, les signatures
et le modèle ne sont jamais modifiés : les signatures calculées à la volée vont dans un
cache à part, data/cache/signatures_ad_hoc.json.

Usage : python3 src/predire.py [syntagme] [--fichier F] [--top N] [--detail] [--sans-api]
"""

import argparse
import csv
import json
import sys
import textwrap

import classify
import config
import corpus_check
import jdm_collect
import signatures as sig
from jdm_client import ClientJDM, JDMErreur, JDMIntrouvable


CHEMIN_CACHE_AD_HOC = config.DOSSIER_CACHE / "signatures_ad_hoc.json"

# Nombre de symboles d'explication affichés de chaque côté.
SYMBOLES_EXPLIQUES = 5

# En deçà de cet écart relatif au meilleur score, la décision est jugée serrée. C'est le
# critère d'évaluation indulgente de l'article (§4.3) et le cas de classe multiple (§4.5).
ECART_SERRE = 0.05


# ---------------------------------------------------------------------------
# Chargement de ce que les étapes précédentes ont produit
# ---------------------------------------------------------------------------

def charger_modele():
    """Lit le modèle final. Retourne (liste de règles, en-tête du fichier)."""
    charge = json.loads(config.FICHIER_MODELE_FINAL.read_text(encoding="utf-8"))
    regles = []
    for identifiant, regle in enumerate(charge["regles"]):
        regles.append({"id": identifiant, "rt": regle["rt"], "poids": regle["poids"],
                       "sL": set(regle["sL"]), "sR": set(regle["sR"]),
                       "exemples": regle["exemples"]})
    return regles, charge


def charger_signatures_connues():
    """Lit les signatures des 1867 termes du corpus. Retourne terme -> ensemble."""
    brut = json.loads(config.FICHIER_SIGNATURES.read_text(encoding="utf-8"))
    return {terme: set(symboles) for terme, symboles in brut.items()}


def frequences_symboles(signatures):
    """Compte chez combien de termes chaque symbole apparaît. Retourne symbole -> entier.

    Sert à classer les symboles d'explication : un symbole rare explique mieux une
    décision qu'un symbole que tout le monde porte."""
    frequences = {}
    for symboles in signatures.values():
        for symbole in symboles:
            frequences[symbole] = frequences.get(symbole, 0) + 1
    return frequences


def charger_cache_ad_hoc():
    """Lit les signatures calculées lors des exécutions précédentes.
    Retourne terme -> ensemble."""
    if not CHEMIN_CACHE_AD_HOC.exists():
        return {}
    try:
        brut = json.loads(CHEMIN_CACHE_AD_HOC.read_text(encoding="utf-8"))
    except ValueError as erreur:
        print(f"  cache ad hoc illisible, ignoré : {erreur}", file=sys.stderr)
        return {}
    return {terme: set(symboles) for terme, symboles in brut.items()}


def ecrire_cache_ad_hoc(cache):
    """Enregistre les signatures calculées à la volée. Ne retourne rien."""
    CHEMIN_CACHE_AD_HOC.parent.mkdir(parents=True, exist_ok=True)
    serialisable = {terme: sorted(symboles) for terme, symboles in sorted(cache.items())}
    with open(CHEMIN_CACHE_AD_HOC, "w", encoding="utf-8", newline="") as f:
        json.dump(serialisable, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")


# ---------------------------------------------------------------------------
# Accès au réseau, ouvert seulement si nécessaire
# ---------------------------------------------------------------------------

def ouvrir_client(contexte):
    """Crée le client JDM au premier besoin. Retourne le client ou None.

    Les tables de types coûtent deux appels : on ne les demande que si un terme inconnu
    se présente vraiment."""
    if contexte["sans_api"]:
        return None
    if contexte["client"] is not None:
        return contexte["client"]
    try:
        client = ClientJDM(dossier_cache=config.DOSSIER_CACHE_JDM,
                           delai=config.DELAI_POLITESSE,
                           timeout=config.TIMEOUT_DEFAUT, essais=config.NB_ESSAIS)
        nom_vers_id, id_vers_relation = client.tables_types_relations()
        contexte["client"] = client
        contexte["id_vers_relation"] = id_vers_relation
        contexte["ids_relations"] = {n: nom_vers_id[n]
                                     for n in ("r_isa", "r_infopot", "r_raff_sem")}
        contexte["noms_types_noeuds"] = {t["id"]: t["name"]
                                         for t in client.types_de_noeuds()}
        return client
    except (JDMErreur, JDMIntrouvable, OSError) as erreur:
        print(f"  API JeuxDeMots injoignable ({erreur}) — on continue hors ligne.")
        contexte["sans_api"] = True
        return None


def terme_existe(terme, contexte):
    """Dit si un terme est connu, du corpus ou de JDM. Retourne un booléen."""
    if terme in contexte["signatures"] or terme in contexte["cache"]:
        return True
    client = ouvrir_client(contexte)
    if client is None:
        return False
    try:
        return client.existe(terme)
    except (JDMErreur, OSError) as erreur:
        print(f"  impossible de vérifier « {terme} » ({erreur}).")
        return False


# ---------------------------------------------------------------------------
# Découpage A / B (logique de corpus_check.py, arbitrage de l'article §4.1)
# ---------------------------------------------------------------------------

def choisir_a_la_main(syntagme, candidats):
    """Demande à l'utilisateur de trancher entre plusieurs découpages.
    Retourne un candidat ou None."""
    print(f"  « {syntagme} » admet {len(candidats)} découpages, tous plausibles :")
    for numero, candidat in enumerate(candidats, 1):
        print(f"    {numero}. A = « {candidat['A']} »   B = « {candidat['B']} »")
    try:
        reponse = input("  lequel ? (numéro, ou vide pour abandonner) ").strip()
    except EOFError:
        return None
    if not reponse.isdigit() or not 1 <= int(reponse) <= len(candidats):
        return None
    return candidats[int(reponse) - 1]


def decouper(syntagme, contexte, interactif):
    """Découpe « A de B ». Retourne (candidat, message) ; candidat vaut None en échec.

    Un seul découpage possible : on le prend. Plusieurs : on applique la méthode de
    l'article (§4.1) en ne gardant que ceux dont les DEUX termes existent dans JDM. Si
    l'ambiguïté résiste, l'utilisateur tranche."""
    candidats = corpus_check.decoupages_possibles(syntagme)
    if not candidats:
        return None, "aucune préposition « de » trouvée — le syntagme doit être « A de B »"
    if len(candidats) == 1:
        return candidats[0], ""

    valides = [c for c in candidats
               if terme_existe(c["A"], contexte) and terme_existe(c["B"], contexte)]
    if len(valides) == 1:
        return valides[0], (f"découpage ambigu tranché par JDM : « {valides[0]['A']} » "
                            f"et « {valides[0]['B']} » existent tous deux")
    restants = valides or candidats
    if len(restants) == 1:
        return restants[0], "découpage ambigu tranché par JDM"
    if interactif:
        choisi = choisir_a_la_main(syntagme, restants)
        if choisi:
            return choisi, "découpage choisi à la main"
        return None, "découpage ambigu non tranché"
    return restants[0], (f"découpage ambigu, {len(restants)} candidats — premier retenu "
                         "par défaut (mode non interactif)")


# ---------------------------------------------------------------------------
# Signature d'un terme
# ---------------------------------------------------------------------------

def signature_par_api(terme, contexte):
    """Interroge JDM et construit la signature d'un terme inconnu.
    Retourne (ensemble, provenance)."""
    client = ouvrir_client(contexte)
    if client is None:
        return {terme}, "inconnu, hors ligne"
    try:
        enregistrement = jdm_collect.collecter_terme(
            client, terme, contexte["ids_relations"], contexte["id_vers_relation"],
            contexte["noms_types_noeuds"])
    except (JDMErreur, OSError) as erreur:
        print(f"  appel JDM échoué pour « {terme} » ({erreur}).")
        return {terme}, "appel échoué"
    if not enregistrement.get("existe"):
        return {terme}, "ABSENT de JDM"
    signature = sig.construire_signature(terme, enregistrement, contexte["seuils"])
    contexte["cache"][terme] = signature
    contexte["cache_modifie"] = True
    return signature, "via API, mis en cache"


def signature_du_terme(terme, contexte):
    """Signature d'un terme, du corpus, du cache, ou de l'API.
    Retourne (ensemble, provenance)."""
    if terme in contexte["signatures"]:
        return contexte["signatures"][terme], "du corpus"
    if terme in contexte["cache"]:
        return contexte["cache"][terme], "du cache"
    return signature_par_api(terme, contexte)


# ---------------------------------------------------------------------------
# Classement (formule 3, mesure figée à l'étape 5)
# ---------------------------------------------------------------------------

def classer(signature_a, signature_b, regles):
    """Score chaque règle et résume par type. Retourne une liste triée de dicts."""
    mesure = classify.MESURES[config.MESURE_FIGEE]
    meilleure_par_type = {}
    for regle in regles:
        score = 0.5 * (mesure(signature_a, regle["sL"])
                       + mesure(signature_b, regle["sR"]))
        ancienne = meilleure_par_type.get(regle["rt"])
        if ancienne is None or score > ancienne["score"] or (
                score == ancienne["score"] and regle["id"] < ancienne["regle"]["id"]):
            meilleure_par_type[regle["rt"]] = {"rt": regle["rt"], "score": score,
                                               "regle": regle}
    classement = list(meilleure_par_type.values())
    classement.sort(key=lambda e: (-e["score"], e["rt"]))
    return classement


def ecart_relatif(classement):
    """Écart relatif entre le premier et le deuxième type. Retourne un flottant."""
    if len(classement) < 2 or not classement[0]["score"]:
        return 1.0
    return (classement[0]["score"] - classement[1]["score"]) / classement[0]["score"]


# ---------------------------------------------------------------------------
# Explication
# ---------------------------------------------------------------------------

def symboles_decisifs(signature_terme, signature_regle, frequences, combien):
    """Symboles communs au terme et à la règle, les plus rares d'abord.
    Retourne une liste.

    Un symbole que presque personne ne porte explique mieux une décision qu'un symbole
    que tout le corpus partage."""
    communs = signature_terme & signature_regle
    return sorted(communs, key=lambda s: (frequences.get(s, 0), s))[:combien]


# ---------------------------------------------------------------------------
# Affichage
# ---------------------------------------------------------------------------

def fr(valeur, decimales=3):
    """Formate un nombre à la française, virgule décimale. Retourne une chaîne."""
    return f"{valeur:.{decimales}f}".replace(".", ",")


def aligner(etiquette, elements, largeur=78):
    """Met en page une liste d'éléments sous une étiquette. Retourne une liste de lignes."""
    if not elements:
        return [f"{etiquette} (aucun)"]
    retrait = " " * len(etiquette)
    enveloppe = textwrap.wrap(", ".join(elements), width=largeur - len(etiquette))
    return [etiquette + enveloppe[0]] + [retrait + suite for suite in enveloppe[1:]]


def decrire_regle(regle):
    """Phrase décrivant la règle gagnante et son origine. Retourne une liste de lignes."""
    exemples = regle["exemples"]
    etiquette = "Règle gagnante : "
    lignes = [f"{etiquette}apprise sur « {exemples[0]} »"]
    autres = len(exemples) - 1
    if autres == 0:
        lignes[0] += "  (règle orpheline, poids 1)"
    elif autres == 1:
        lignes.append(" " * len(etiquette)
                      + f"et 1 autre exemple (poids {regle['poids']})")
    else:
        lignes.append(" " * len(etiquette)
                      + f"et {autres} autres exemples (poids {regle['poids']})")
    return lignes


def afficher_prediction(resultat, options):
    """Affiche le résultat d'un syntagme. Ne retourne rien."""
    print()
    print(f"A = {resultat['A']}   ({len(resultat['sA'])} symboles, "
          f"{resultat['provenance_a']})")
    print(f"B = {resultat['B']}   ({len(resultat['sB'])} symboles, "
          f"{resultat['provenance_b']})")
    print(f"    déterminant : {resultat['det']}+{resultat['definitude']} "
          "— relevé mais NON utilisé : le trait de définitude dégradait le F1 "
          "(Expérience 2)")
    if resultat["message"]:
        print(f"    {resultat['message']}")
    print()

    if not resultat["classement"][0]["score"]:
        print("  AUCUNE PRÉDICTION : pas un seul symbole en commun avec une règle.")
        print("  Les deux termes sont trop mal décrits pour que la question ait un sens.")
        print()
        return

    for rang, entree in enumerate(resultat["classement"][:options.top], 1):
        marque = "   <- prédiction" if rang == 1 else ""
        print(f"  {rang}. {entree['rt']:<22s} {fr(entree['score'])}{marque}")
    print()

    for ligne in decrire_regle(resultat["classement"][0]["regle"]):
        print(ligne)
    print()

    for ligne in aligner("Symboles décisifs côté A : ", resultat["decisifs_a"]):
        print(ligne)
    for ligne in aligner("Symboles décisifs côté B : ", resultat["decisifs_b"]):
        print(ligne)
    print()

    if len(resultat["classement"]) > 1:
        absolu = resultat["classement"][0]["score"] - resultat["classement"][1]["score"]
        if resultat["ecart"] < ECART_SERRE:
            verdict = (f"décision serrée, le 2e type "
                       f"({resultat['classement'][1]['rt']}) est également plausible")
        else:
            verdict = "décision nette"
        print(f"Écart avec le 2e : {fr(absolu)} "
              f"({fr(100 * resultat['ecart'], 1)} %) — {verdict}")

    if options.detail:
        print()
        for ligne in aligner(f"Signature de « {resultat['A']} » : ",
                             sorted(resultat["sA"])):
            print(ligne)
        for ligne in aligner(f"Signature de « {resultat['B']} » : ",
                             sorted(resultat["sB"])):
            print(ligne)
    print()


# ---------------------------------------------------------------------------
# Traitement d'un syntagme
# ---------------------------------------------------------------------------

def traiter(syntagme, contexte, interactif):
    """Découpe, signe, classe et explique un syntagme. Retourne un dict ou None."""
    candidat, message = decouper(syntagme, contexte, interactif)
    if candidat is None:
        print(f"  {message}")
        return None

    signature_a, provenance_a = signature_du_terme(candidat["A"], contexte)
    signature_b, provenance_b = signature_du_terme(candidat["B"], contexte)
    classement = classer(signature_a, signature_b, contexte["regles"])
    gagnante = classement[0]["regle"]

    return {
        "syntagme": syntagme, "A": candidat["A"], "B": candidat["B"],
        "det": candidat["det"], "definitude": candidat["definitude"],
        "sA": signature_a, "sB": signature_b,
        "provenance_a": provenance_a, "provenance_b": provenance_b,
        "message": message, "classement": classement,
        "ecart": ecart_relatif(classement),
        "decisifs_a": symboles_decisifs(signature_a, gagnante["sL"],
                                        contexte["frequences"], SYMBOLES_EXPLIQUES),
        "decisifs_b": symboles_decisifs(signature_b, gagnante["sR"],
                                        contexte["frequences"], SYMBOLES_EXPLIQUES),
    }


# ---------------------------------------------------------------------------
# Les trois modes
# ---------------------------------------------------------------------------

def mode_interactif(contexte, options):
    """Boucle de saisie, quitte sur une ligne vide ou « q ». Ne retourne rien."""
    print("Tapez un syntagme « A de B ». Ligne vide ou « q » pour quitter.")
    while True:
        try:
            saisie = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not saisie or saisie.lower() == "q":
            return
        resultat = traiter(saisie, contexte, interactif=True)
        if resultat:
            afficher_prediction(resultat, options)


def mode_fichier(chemin, contexte, options):
    """Traite un syntagme par ligne et écrit un CSV. Ne retourne rien."""
    try:
        lignes = [l.strip() for l in
                  open(chemin, encoding="utf-8").read().splitlines() if l.strip()]
    except OSError as erreur:
        print(f"Fichier illisible : {erreur}", file=sys.stderr)
        return
    sortie = chemin + ".predictions.csv"
    with open(sortie, "w", encoding="utf-8", newline="") as f:
        redacteur = csv.writer(f, lineterminator="\n")
        redacteur.writerow(["syntagme", "A", "B", "predit", "score", "second",
                            "ecart_relatif", "serre", "poids_regle", "exemple_regle"])
        for syntagme in lignes:
            resultat = traiter(syntagme, contexte, interactif=False)
            if resultat is None:
                redacteur.writerow([syntagme, "", "", "", "", "", "", "", "", ""])
                continue
            premier = resultat["classement"][0]
            if not premier["score"]:
                redacteur.writerow([syntagme, resultat["A"], resultat["B"],
                                    "AUCUNE", "0", "", "", "", "", ""])
                print(f"  {syntagme} -> aucune prédiction (aucun symbole partagé)")
                continue
            second = (resultat["classement"][1]["rt"]
                      if len(resultat["classement"]) > 1 else "")
            redacteur.writerow([
                syntagme, resultat["A"], resultat["B"], premier["rt"],
                f"{premier['score']:.4f}", second, f"{resultat['ecart']:.4f}",
                "oui" if resultat["ecart"] < ECART_SERRE else "non",
                premier["regle"]["poids"], premier["regle"]["exemples"][0]])
            print(f"  {syntagme} -> {premier['rt']} ({fr(premier['score'])})")
    print(f"\nÉcrit : {sortie}")


# ---------------------------------------------------------------------------
# Enchaînement
# ---------------------------------------------------------------------------

def analyser_arguments():
    """Lit la ligne de commande. Retourne les options."""
    analyseur = argparse.ArgumentParser(
        description="Prédit la relation sémantique d'un syntagme « A de B ».")
    analyseur.add_argument("syntagme", nargs="*", help="syntagme à traiter")
    analyseur.add_argument("--fichier", help="fichier de syntagmes, un par ligne")
    analyseur.add_argument("--top", type=int, default=3,
                           help="nombre de types affichés (défaut 3)")
    analyseur.add_argument("--detail", action="store_true",
                           help="afficher les signatures complètes")
    analyseur.add_argument("--sans-api", action="store_true", dest="sans_api",
                           help="ne jamais interroger JDM")
    return analyseur.parse_args()


def preparer_contexte(options):
    """Charge le modèle, les signatures et le cache. Retourne un dict."""
    regles, entete = charger_modele()
    signatures = charger_signatures_connues()
    contexte = {
        "regles": regles, "signatures": signatures,
        "frequences": frequences_symboles(signatures),
        "cache": charger_cache_ad_hoc(), "cache_modifie": False,
        "client": None, "sans_api": options.sans_api, "seuils": {},
        "ids_relations": None, "id_vers_relation": None, "noms_types_noeuds": None,
    }
    print(f"Modèle : {len(regles)} règles, seuil {entete['seuil']}, "
          f"{entete['strategie']}, mesure {config.MESURE_FIGEE}. "
          f"{len(signatures)} signatures connues, {len(contexte['cache'])} en cache."
          + (" Mode hors ligne." if options.sans_api else ""))
    return contexte


def main():
    options = analyser_arguments()
    contexte = preparer_contexte(options)

    if options.fichier:
        mode_fichier(options.fichier, contexte, options)
    elif options.syntagme:
        resultat = traiter(" ".join(options.syntagme), contexte, interactif=False)
        if resultat:
            afficher_prediction(resultat, options)
    else:
        mode_interactif(contexte, options)

    if contexte["cache_modifie"]:
        ecrire_cache_ad_hoc(contexte["cache"])
        print(f"Cache ad hoc mis à jour : {len(contexte['cache'])} signatures.")


if __name__ == "__main__":
    main()
