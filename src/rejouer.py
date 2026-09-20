#!/usr/bin/env python3
"""Rejoue la chaîne complète après un changement de paramètre dans config.py.

À quoi ça sert : changer une valeur de config.py (H_TOP, TRT_POLITIQUE, GRASP_SEUILS…)
invalide tout ce qui suit. Relancer les étapes une par une marche, mais dans le désordre
on évalue des signatures neuves avec un modèle périmé, sans que rien ne le signale. Ce
script impose l'ordre.

    signatures.py  ->  grasp.py  ->  classify.py  ->  evaluate.py

La collecte n'est PAS rejouée : elle stocke les traits bruts, sans coupure ni filtre, et
ne dépend d'aucun des paramètres réglables. Aucun appel réseau, donc, et une trentaine
de secondes en tout.

AVERTISSEMENT DE MÉTHODE. `evaluate.py` ouvre le split test. Le rejouer après avoir
changé un paramètre, puis choisir ce paramètre au vu du résultat, revient à régler le
modèle sur le test : le chiffre cesse d'estimer la généralisation. Le score qui a le
droit de guider un choix est celui du CALIBRAGE. Ce script affiche les deux côte à côte
pour que la distinction reste sous les yeux.

Usage : python3 src/rejouer.py [--sans-test]
"""

import argparse
import json
import subprocess
import sys
import time

import config


# Les quatre étapes, dans l'ordre où elles doivent tourner.
ETAPES = [
    ("signatures.py", "reconstruit les 1867 signatures depuis la collecte"),
    ("grasp.py", "réapprend les règles, balaie stratégies et seuils"),
    ("classify.py", "choisit le seuil sur le calibrage, réapprend le modèle final"),
    ("evaluate.py", "ouvre le split test et mène les trois expériences"),
]


def parametres_courants():
    """Les réglages qui pilotent la chaîne. Retourne une liste de couples."""
    return [
        ("H_TOP", config.H_TOP),
        ("TRT_POLITIQUE", config.TRT_POLITIQUE),
        ("TRT_CENTILE", config.TRT_CENTILE),
        ("SST_EXCLURE_MORPHO", config.SST_EXCLURE_MORPHO),
        ("MESURE_FIGEE", config.MESURE_FIGEE),
        ("GRASP_SEUILS", config.GRASP_SEUILS),
        ("GRASP_STRATEGIES", config.GRASP_STRATEGIES),
    ]


def lancer(script):
    """Exécute une étape et laisse sa sortie s'afficher. Retourne (succès, durée)."""
    chemin = config.RACINE / "src" / script
    depart = time.monotonic()
    resultat = subprocess.run([sys.executable, "-X", "utf8", str(chemin)],
                              cwd=str(config.RACINE / "src"))
    return resultat.returncode == 0, time.monotonic() - depart


def lire_scores():
    """Relit le F1 de calibrage et celui du test. Retourne un couple de flottants ou None."""
    calibrage = test = None
    if config.FICHIER_MODELE_FINAL.exists():
        modele = json.loads(config.FICHIER_MODELE_FINAL.read_text(encoding="utf-8"))
        calibrage = (modele.get("resume") or {}).get("f1_calibrage")
    chemin_test = config.DOSSIER_RESULTATS / "test_predictions.json"
    if chemin_test.exists():
        charge = json.loads(chemin_test.read_text(encoding="utf-8"))
        test = charge["macro_stricte"]["f1"]
    return calibrage, test


def fr(valeur, decimales=3):
    """Formate un nombre à la française, virgule décimale. Retourne une chaîne."""
    return f"{valeur:.{decimales}f}".replace(".", ",")


def afficher_parametres():
    """Rappelle les réglages avant de lancer quoi que ce soit. Ne retourne rien."""
    print("Paramètres lus dans config.py :")
    for nom, valeur in parametres_courants():
        print(f"    {nom:<20s} {valeur}")
    print()


def afficher_bilan(avant, apres, durees):
    """Compare les scores d'avant et d'après. Ne retourne rien."""
    print()
    print("=" * 66)
    total = sum(durees.values())
    for script, duree in durees.items():
        print(f"    {script:<18s} {duree:5.1f} s")
    print(f"    {'total':<18s} {total:5.1f} s")
    print()
    for nom, indice in (("F1 calibrage", 0), ("F1 test", 1)):
        ancien, nouveau = avant[indice], apres[indice]
        if nouveau is None:
            continue
        if ancien is None or abs(ancien - nouveau) < 1e-9:
            print(f"    {nom:<14s} {fr(nouveau)}")
        else:
            ecart = nouveau - ancien
            signe = "+" if ecart > 0 else "−"
            print(f"    {nom:<14s} {fr(ancien)} -> {fr(nouveau)}"
                  f"   ({signe}{fr(abs(ecart))})")
    print()
    print("    Le F1 de CALIBRAGE est celui qui a le droit de guider un choix de")
    print("    paramètre. Le F1 de TEST ne vaut comme estimation de généralisation")
    print("    que s'il n'a servi à rien décider. Choisir au vu du test, c'est régler")
    print("    sur le test.")
    print("=" * 66)


def main():
    analyseur = argparse.ArgumentParser(
        description="Rejoue la chaîne complète après un changement de config.py.")
    analyseur.add_argument("--sans-test", action="store_true", dest="sans_test",
                           help="s'arrête avant evaluate.py, pour ne pas rouvrir le test")
    options = analyseur.parse_args()

    afficher_parametres()
    avant = lire_scores()

    etapes = ETAPES[:-1] if options.sans_test else ETAPES
    durees = {}
    for numero, (script, role) in enumerate(etapes, 1):
        print(f"\n[{numero}/{len(etapes)}] {script} — {role}")
        print("-" * 66)
        succes, duree = lancer(script)
        durees[script] = duree
        if not succes:
            print(f"\n{script} a échoué. Chaîne interrompue : les sorties suivantes "
                  "seraient calculées sur des données périmées.", file=sys.stderr)
            return 1

    afficher_bilan(avant, lire_scores(), durees)
    if options.sans_test:
        print("    evaluate.py n'a pas été lancé : le F1 de test affiché est l'ancien.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
