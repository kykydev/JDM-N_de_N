#!/usr/bin/env python3
"""Rejoue la chaîne complète après un changement de paramètre dans config.py.

À quoi ça sert : changer une valeur de config.py (H_TOP, TRT_POLITIQUE…)
invalide tout ce qui suit. Relancer les étapes une par une marche, mais dans le désordre
on évalue des signatures neuves avec un modèle périmé, sans que rien ne le signale. Ce
script impose l'ordre.

    signatures.py  ->  grasp.py  ->  grille.py  ->  evaluation_finale.py

La collecte n'est PAS rejouée : elle stocke les traits bruts, sans coupure ni filtre, et
ne dépend d'aucun des paramètres réglables. Aucun appel réseau, donc, et moins d'une
minute en tout.

AVERTISSEMENT DE MÉTHODE. La méthode retenue n'a aucun seuil, mais config.py garde des
paramètres de représentation (H_TOP, TRT_POLITIQUE…). `evaluation_finale.py` LIT le
test : changer l'un de ces paramètres, puis le garder au vu du F1 de test, revient à
régler le modèle sur le test, et le chiffre cesse d'estimer la généralisation. Le score
qui a le droit de guider un choix est celui de la validation croisée (`grille.py`, qui
ne lit que l'entraînement).

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
    ("grasp.py", "reconstruit les quinze arbres de la configuration par défaut"),
    ("grille.py", "compare toutes les configurations en validation croisée, sans test"),
    ("evaluation_finale.py", "réapprend sur les 750 exemples et LIT le test"),
]


def parametres_courants():
    """Les réglages qui pilotent la chaîne. Retourne une liste de couples."""
    return [
        ("H_TOP", config.H_TOP),
        ("TRT_POLITIQUE", config.TRT_POLITIQUE),
        ("TRT_CENTILE", config.TRT_CENTILE),
        ("SST_EXCLURE_MORPHO", config.SST_EXCLURE_MORPHO),
        ("REPRESENTATION", config.REPRESENTATION),
        ("STRUCTURE", config.STRUCTURE),
        ("CLASSIFICATION", config.CLASSIFICATION),
    ]


def lancer(script):
    """Exécute une étape et laisse sa sortie s'afficher. Retourne (succès, durée)."""
    chemin = config.RACINE / "src" / script
    depart = time.monotonic()
    resultat = subprocess.run([sys.executable, "-X", "utf8", str(chemin)],
                              cwd=str(config.RACINE / "src"))
    return resultat.returncode == 0, time.monotonic() - depart


def lire_score():
    """Relit le F1 de test de la descente. Retourne un flottant ou None."""
    chemin_test = config.FICHIER_PREDICTIONS_FINALES
    if not chemin_test.exists():
        return None
    charge = json.loads(chemin_test.read_text(encoding="utf-8"))
    return charge["macro_stricte"]["f1"]


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
    if apres is not None:
        if avant is None or abs(avant - apres) < 1e-9:
            print(f"    {'F1 test':<14s} {fr(apres)}")
        else:
            ecart = apres - avant
            signe = "+" if ecart > 0 else "−"
            print(f"    {'F1 test':<14s} {fr(avant)} -> {fr(apres)}"
                  f"   ({signe}{fr(abs(ecart))})")
    print()
    print("    Le F1 de TEST ne vaut comme estimation de généralisation que s'il")
    print("    n'a servi à rien décider. Garder un réglage de config.py au vu de ce")
    print("    chiffre, c'est régler sur le test.")
    print("=" * 66)


def main():
    analyseur = argparse.ArgumentParser(
        description="Rejoue la chaîne complète après un changement de config.py.")
    analyseur.add_argument("--sans-test", action="store_true", dest="sans_test",
                           help="s'arrête avant evaluation_finale.py, sans lire le test")
    options = analyseur.parse_args()

    afficher_parametres()
    avant = lire_score()

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

    afficher_bilan(avant, lire_score(), durees)
    if options.sans_test:
        print("    evaluation_finale.py n'a pas été lancé : le F1 affiché est l'ancien.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
