#!/usr/bin/env python3
"""Configuration du projet : chemins, réglages réseau et seuils. Aucun appel réseau ici.

Ce module ne contient que des constantes. Il est importé par tous les autres et ne doit
jamais importer l'un d'eux, pour qu'il n'y ait pas de cycle.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Chemins
# ---------------------------------------------------------------------------

RACINE = Path(__file__).resolve().parent.parent

DOSSIER_DONNEES = RACINE / "data"
DOSSIER_CORPUS = DOSSIER_DONNEES / "corpus"
DOSSIER_CORPUS_BRUT = DOSSIER_CORPUS / "raw"
DOSSIER_CORPUS_PROPRE = DOSSIER_CORPUS / "clean"
FICHIER_TERMES = DOSSIER_CORPUS_PROPRE / "termes.csv"

DOSSIER_CACHE = DOSSIER_DONNEES / "cache"
DOSSIER_CACHE_JDM = DOSSIER_CACHE / "jdm"

DOSSIER_COLLECTE = DOSSIER_DONNEES / "collecte"
FICHIER_COLLECTE = DOSSIER_COLLECTE / "termes_jdm.jsonl"
FICHIER_ERREURS = DOSSIER_COLLECTE / "erreurs.jsonl"
FICHIER_SESSIONS = DOSSIER_COLLECTE / "sessions.json"

DOSSIER_SIGNATURES = DOSSIER_DONNEES / "signatures"
FICHIER_SIGNATURES = DOSSIER_SIGNATURES / "signatures_termes.json"

DOSSIER_RAPPORTS = RACINE / "reports"
DOSSIER_LOGS = RACINE / "logs"
FICHIER_LOG_APPELS = DOSSIER_LOGS / "jdm_calls.log"

# ---------------------------------------------------------------------------
# API JeuxDeMots
# ---------------------------------------------------------------------------

URL_BASE_JDM = "https://jdm-api.demo.lirmm.fr/v0"

# Délai minimal entre deux appels réseau réels, en secondes : politesse envers le serveur.
DELAI_POLITESSE = 0.3

# Timeout par défaut, en secondes.
TIMEOUT_DEFAUT = 10.0

# Timeout des relations entrantes : « eau » en a 165 004 et a répondu en 22 s à la sonde.
TIMEOUT_RELATIONS_ENTRANTES = 60.0

# Nombre d'essais par requête, et base du délai d'attente exponentiel entre deux essais.
NB_ESSAIS = 3
BACKOFF = 1.0

# Paramètres de /relations/to retenus en phase 1 : 82 % de volume en moins pour un
# résultat strictement identique. `relation_fields` DOIT contenir `w`, sinon 500.
PARAMS_RELATIONS_ENTRANTES = {"without_nodes": True, "relation_fields": ["type", "w"]}

# ---------------------------------------------------------------------------
# Collecte (src/jdm_collect.py)
# ---------------------------------------------------------------------------

# Annotations _INFO-SEM-* de nature morphologique : conservées dans le JSONL, mais
# marquées `morpho: true` pour que l'étape 3 puisse les inclure ou les exclure sans
# recollecte. Liste volontairement exacte : PERS-MASC et PERS-FEM sont sémantiques.
SST_ANNOTATIONS_MORPHO = frozenset({
    "DET", "NODET", "PLUR", "SING", "PLURIEL", "SINGULIER",
    "MASC", "FEM", "GENRE-MASC", "GENRE-FEM", "INV",
})

# ---------------------------------------------------------------------------
# Contrôle du corpus (src/corpus_check.py)
# ---------------------------------------------------------------------------

# Chaque fichier source doit compter ce nombre de lignes, dont les premières en train.
LIGNES_ATTENDUES = 80
TAILLE_TRAIN = 50

# Seuil à partir duquel un même terme A ou B est signalé comme répété dans un type.
SEUIL_REPETITION = 3

# ---------------------------------------------------------------------------
# Signatures (src/signatures.py)
# ---------------------------------------------------------------------------

# Préfixes de provenance des symboles. Ils évitent les collisions entre traits
# (« PLACE » comme hyperonyme et « PLACE » comme annotation) et permettront de filtrer
# une signature par trait, par configuration, pour l'Expérience 1.
PREFIXE_H = "H:"
PREFIXE_TRT = "TRT:"
PREFIXE_SST = "SST:"

# H : nombre d'hyperonymes gardés, par poids décroissant. Coupure mesurée par la sonde
# (reports/rapport_sonde_jdm.md, §3) : au-delà, les poids s'effondrent. Les doublons de
# casse sont fusionnés AVANT la coupure, sur la forme normalisée, en gardant la forme
# d'origine la mieux pondérée.
H_TOP = 20

# Les cibles à préfixe de langue (« en:aircraft ») sont conservées par défaut.
# Passer à True pour les écarter, sans recollecte.
H_EXCLURE_PREFIXES_LANGUE = False

# TRT : types de relations entrantes écartés de la signature, quel que soit l'effectif.
# Relations méta, lexicales ou techniques, repérées par la sonde
# (reports/rapport_sonde_jdm.md) : elles disent comment un terme est écrit ou documenté,
# pas ce qu'il est. Aucune n'apparaît dans l'exemple de signature de l'article.
TRT_TYPES_EXCLUS = (
    "r_aki", "r_wiki", "r_associated", "r_context", "r_variante", "r_translation", "r_lemma",
    "r_meaning/glose", "r_raff_sem-1", "r_sing_form", "r_der_morpho", "r_masc", "r_homophone",
    "r_locution", "r_error",
)

# TRT : politique de sélection des types de relations entrantes.
#
#   "presence" — tout type reçu au moins une fois, hors TRT_TYPES_EXCLUS. C'est la
#                lecture FIDÈLE À L'ARTICLE, et le réglage par défaut. L'exemple de
#                signature donné par l'article (§3, terme « véhicule ») contient
#                `r_isa`, `r_hypo`, `r_has_part`, `r_holo`, `r_agent`, `r_patient`,
#                `r_lieu`… : les auteurs gardent les types très répandus. Ils
#                annoncent F1 = 0,772 avec cette représentation.
#
#   "centile"  — P8@C66 : un type n'est gardé pour un terme que si l'effectif reçu
#                dépasse le centile TRT_CENTILE de la distribution de ce type sur tout
#                le corpus. Politique issue de nos diagnostics
#                (reports/diagnostic_trt.md et diagnostic_trt_tour2.md), qui montraient
#                qu'elle sépare bien mieux deux termes tirés au hasard. MAIS cette
#                mesure est un proxy : elle n'a pas été validée sur le F1, et c'est
#                justement ce que la suite doit trancher.
#
# Les deux politiques coexistent exprès : l'une pour reproduire l'article, l'autre pour
# nos essais. Changer cette ligne et relancer signatures.py suffit à basculer.
TRT_POLITIQUE = "presence"
TRT_CENTILE = 66

# SST : les annotations morphologiques (DET, NODET...) sont gardées par défaut.
# Passer à True pour les écarter, sans recollecte.
SST_EXCLURE_MORPHO = False

# En deçà de ce nombre de symboles, une signature est signalée comme quasi vide.
SEUIL_SIGNATURE_QUASI_VIDE = 3

# Nombre de symboles les plus fréquents listés dans le rapport.
NB_SYMBOLES_FREQUENTS = 30

# ---------------------------------------------------------------------------
# Configuration retenue : SOMME · ARBRE · DESCENTE
# ---------------------------------------------------------------------------
#
# Choisie en validation croisée (reports/rapport_grille.md), sur l'entraînement seul.
# C'est la SEULE configuration par défaut du projet : toute fonction qui a un choix à
# faire lit ces trois constantes. Les autres options restent disponibles en paramètre
# explicite, pour rejouer la grille ou les méthodes écartées.

# Représentation d'un nœud fusionné : « somme » (vecteur des comptes symbole -> nombre
# d'exemples couverts qui le portent, donc un profil moyen) ou « union » (ensemble).
REPRESENTATION = "somme"

# Structure : « arbre », fusion jusqu'à la racine, aucun seuil de coupe.
STRUCTURE = "arbre"

# Classification : « descente » depuis la racine de chacun des 15 arbres, vers le
# meilleur enfant tant qu'il fait STRICTEMENT mieux que le nœud courant.
CLASSIFICATION = "descente"

# Lien de construction : minimum des deux côtés. Score de classification : formule 3 de
# l'article, moyenne des deux côtés. L'asymétrie est voulue.

# ---------------------------------------------------------------------------
# Apprentissage par clustering hiérarchique (src/grasp.py)
# ---------------------------------------------------------------------------
#
# Aucun seuil de fusion : chaque type est fusionné jusqu'à sa racine. Les arbres sont
# appris sur les 50 exemples d'entraînement de chaque type ; il n'y a plus de
# calibrage, puisqu'il n'y a plus rien à choisir.

DOSSIER_MODELES = DOSSIER_DONNEES / "modeles"

# Les quinze arbres du clustering hiérarchique, tous nœuds compris (src/grasp.py). Le
# nom porte la représentation : changer REPRESENTATION n'écrase pas les arbres d'une
# autre. Les arbres en union ont été supprimés (ils sont dans le commit 8bd078a).
FICHIER_ARBRES = DOSSIER_MODELES / f"arbres_{REPRESENTATION}.json"

# Rapport de grasp.py. Même principe : rapport_arbres.md, sans suffixe, documente la
# version en union et n'est plus régénérable.
FICHIER_RAPPORT_ARBRES = DOSSIER_RAPPORTS / f"rapport_arbres_{REPRESENTATION}.md"

# ---------------------------------------------------------------------------
# Classification par descente (src/classify.py)
# ---------------------------------------------------------------------------

DOSSIER_RESULTATS = DOSSIER_DONNEES / "resultats"

# Évaluation finale de la configuration retenue (src/evaluation_finale.py). Fichiers à
# part, pour la version en union (dont les résultats sont dans le commit 8bd078a).
FICHIER_PREDICTIONS_FINALES = DOSSIER_RESULTATS / "predictions_finales.json"
FICHIER_MATRICE_FINALE = DOSSIER_RESULTATS / "matrice_confusion_finale.csv"
FICHIER_RAPPORT_FINAL = DOSSIER_RAPPORTS / "rapport_final.md"

# ---------------------------------------------------------------------------
# Grille d'options en validation croisée (src/grille.py)
# ---------------------------------------------------------------------------

# Validation croisée sur les 750 exemples d'entraînement : 5 plis stratifiés par type,
# 10 exemples par type et par pli. Le test n'est pas lu.
GRILLE_PLIS = 5
GRAINE_ALEATOIRE = 42

# Seuils de coupe des arbres en forêt, balayés séparément pour chaque représentation :
# le cosinus sur comptes n'a pas la même échelle que sur ensembles.
GRILLE_SEUILS = tuple(round(0.30 + 0.05 * k, 2) for k in range(9))

FICHIER_RAPPORT_GRILLE = DOSSIER_RAPPORTS / "rapport_grille.md"
FICHIER_COURBES_GRILLE = DOSSIER_RAPPORTS / "rapport_grille_courbes.svg"

# ---------------------------------------------------------------------------
# Variantes de signatures en validation croisée (src/variantes_signatures.py)
# ---------------------------------------------------------------------------
#
# La méthode reste figée (somme · arbre · descente). Ce qui varie : la construction des
# signatures. Tout est calculé en mémoire depuis data/collecte/ ; data/signatures/ n'est
# pas touché et le test n'est pas lu. Statistiques documentaires et centiles ne sont
# calculés que sur les termes d'entraînement du pli.

# Répétitions de la validation croisée : une graine par répétition, 5 plis chacune.
GRAINES_VARIANTES = (42, 43, 44)

# Nombre d'hyperonymes gardés ; « tous » = tous ceux de poids > 0 après fusion des
# doublons de casse. Rangés du plus simple au plus complexe.
VARIANTES_H = (H_TOP, 50, 100, 200, "tous")

# Pondérations des symboles, de la plus simple à la plus complexe.
#   binaire : poids 1.  idf : log(N / df) sur les termes d'entraînement du pli.
#   jdm : poids de la collecte, normalisés par terme et par trait.  jdm×idf : produit.
VARIANTES_PONDERATIONS = ("binaire", "idf", "jdm", "jdm×idf")

# Pondérations partielles : seul le trait nommé reçoit les poids de la collecte, les deux
# autres restent binaires. Elles ne concourent PAS au choix de la configuration, qui
# reste celui de l'étape 1 ; elles répondent à une autre question, celle de savoir quel
# trait apporte quelque chose seul, et si le tout vaut la somme de ses parties.
VARIANTES_PONDERATIONS_PAR_TRAIT = ("jdm_H", "jdm_TRT", "jdm_SST")

# Traitement du symbole du terme lui-même : T2 absent, T0 sans préfixe (actuel), T1 sous
# la forme H:<terme>. Rangés du plus simple au plus complexe.
VARIANTES_TERME = ("T2", "T0", "T1")

# Sélection TRT et SST, du réglage actuel aux plus retouchés.
#   sans_frequents : retrait des types présents chez plus de SEUIL_TRT_FREQUENT des
#   termes d'entraînement.  centile : politique P8@C66, centile TRT_CENTILE.
VARIANTES_TRT = ("tous", "aucun", "sans_frequents", "centile")
VARIANTES_SST = ("toutes", "aucune", "sans_morpho")
SEUIL_TRT_FREQUENT = 0.80

# Fréquence documentaire minimale d'un symbole d'entraînement : 1 = aucun seuil.
VARIANTES_DF_MIN = (1, 2)

# Exemples de validation par pli : 10 par type, 15 types.
TAILLE_PLI_VALIDATION = 150

# Réglages actuels du projet, pris comme référence de toute la phase.
REFERENCE_VARIANTES = {"h": H_TOP, "pond": "binaire", "terme": "T0", "trt": "tous",
                       "sst": "toutes", "df_min": 1}

# F1 de la même référence dans rapport_grille.md (une répétition, graine 42), pour
# vérifier que la nouvelle chaîne la retrouve à l'identique.
F1_REFERENCE_GRILLE = 0.784

# Nombre de processus de calcul ; None = nombre de cœurs, plafonné.
PROCESSUS_VARIANTES = None
PROCESSUS_MAXIMUM = 6

DOSSIER_SIGNATURES_VARIANTES = DOSSIER_DONNEES / "signatures_variantes"
FICHIER_MESURES_VARIANTES = DOSSIER_SIGNATURES_VARIANTES / "mesures_cv.json"
FICHIER_RAPPORT_VARIANTES = DOSSIER_RAPPORTS / "rapport_signatures_variantes.md"

# ---------------------------------------------------------------------------
# Test complémentaire de la pondération par trait (src/ponderation_traits.py)
# ---------------------------------------------------------------------------
#
# Éclairage sur le §3.1 du rapport des variantes, PAS une règle de choix : la
# configuration retenue reste SIGNATURES_RETENUES, décidée à l'étape 1 avant toute
# lecture du test. Dix graines au lieu de trois, et un test apparié sur la moyenne par
# graine : les 5 plis d'une graine rebattent les mêmes 750 exemples, donc les traiter
# comme 15 mesures indépendantes surestime la précision. Une graine = un découpage
# complet, et les moyennes par graine sont échangeables sous l'hypothèse nulle.

GRAINES_PONDERATION = tuple(range(42, 52))

# Les cinq configurations comparées, à H_TOP et terme T2 : la référence binaire, les
# trois pondérations partielles, puis les trois traits ensemble.
PONDERATIONS_COMPAREES = ("binaire", "jdm_H", "jdm_TRT", "jdm_SST", "jdm")

FICHIER_MESURES_PONDERATION = DOSSIER_SIGNATURES_VARIANTES / "mesures_ponderation.json"
FICHIER_RAPPORT_PONDERATION = DOSSIER_RAPPORTS / "rapport_ponderation.md"

# ---------------------------------------------------------------------------
# Signatures retenues par la validation croisée (src/evaluation_signatures.py)
# ---------------------------------------------------------------------------
#
# Choisies dans reports/rapport_signatures_variantes.md. `predire.py` et
# `evaluation_signatures.py` les construisent en mémoire ; data/signatures/ garde les
# signatures initiales (REFERENCE_VARIANTES), que lit encore `evaluation_finale.py`.
SIGNATURES_RETENUES = {"h": 20, "pond": "jdm", "terme": "T2", "trt": "tous",
                       "sst": "toutes", "df_min": 1}

FICHIER_PREDICTIONS_SIGNATURES = DOSSIER_RESULTATS / "predictions_finales_jdm.json"
FICHIER_MATRICE_SIGNATURES = DOSSIER_RESULTATS / "matrice_confusion_finale_jdm.csv"
FICHIER_RAPPORT_SIGNATURES = DOSSIER_RAPPORTS / "rapport_final_signatures.md"
