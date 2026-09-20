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
# Tirages aléatoires
# ---------------------------------------------------------------------------

# Graine de tous les tirages du projet : découpe du calibrage, échantillons des
# rapports. Chaque tirage en dérive une sous-graine par type de relation, pour
# qu'ajouter un type ne change pas la découpe des autres.
GRAINE_ALEATOIRE = 42

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
# Apprentissage par fusion (src/grasp.py)
# ---------------------------------------------------------------------------

DOSSIER_MODELES = DOSSIER_DONNEES / "modeles"

# Découpe du split train en apprentissage et calibrage, par type de relation. Le split
# test (30 lignes par type) n'est pas touché et ne doit pas l'être avant l'évaluation.
FICHIER_SPLIT_CALIBRAGE = DOSSIER_CORPUS_PROPRE / "split_calibrage.csv"
TAILLE_APPRENTISSAGE = 40
TAILLE_CALIBRAGE = 10

# Les deux ordonnancements de fusion. Le papier ne tranche pas, et l'ordre change le
# résultat : fusionner A+B puis C ne donne pas la même règle que B+C puis A.
GRASP_STRATEGIES = ("glouton", "sequentiel")

# Seuils balayés. 0,50 est celui du papier : il figure dans tous les tableaux, même
# lorsqu'il ne fusionne presque rien, pour servir de point de comparaison.
GRASP_SEUILS = (0.30, 0.35, 0.40, 0.45, 0.50, 0.55)
GRASP_SEUIL_PAPIER = 0.50

# Détection d'emballement. Une règle qui couvre plus de la moitié des exemples de son
# type, ou dont la signature dépasse ce multiple de la taille initiale médiane, a
# absorbé trop de choses et ne discrimine plus rien.
EMBALLEMENT_PART_EXEMPLES = 0.5
EMBALLEMENT_FACTEUR_TAILLE = 3

# ---------------------------------------------------------------------------
# Classification (src/classify.py)
# ---------------------------------------------------------------------------

DOSSIER_RESULTATS = DOSSIER_DONNEES / "resultats"
FICHIER_MODELE_FINAL = DOSSIER_MODELES / "modele_final.json"

# Les trois mesures de similarité comparées. Elles ne diffèrent que par la pénalité
# qu'elles infligent à une règle large : le cosinus divise par la racine de sa taille,
# Tversky par une fraction de ce qu'elle contient en trop, la couverture par rien.
# C'est exactement la question posée par la fusion, qui produit des règles larges.
MESURES_SIMILARITE = ("cosinus", "tversky", "couverture")

# Poids de l'excédent de la règle dans l'indice de Tversky. À 0 on retrouve la
# couverture, à 0,5 l'indice de Dice, à 1 celui de Jaccard.
TVERSKY_BETA = 0.2

# Seuils d'abstention balayés : en deçà, le score gagnant est jugé trop faible pour
# que la prédiction veuille dire quelque chose.
# Les quatre premiers sont ceux de l'énoncé ; ils se sont révélés tous inférieurs au
# plus faible score observé, donc sans effet. Le balayage est prolongé jusqu'à la
# médiane pour que la courbe soit lisible, sans que cela tranche quoi que ce soit.
SEUILS_ABSTENTION_DEMANDES = (0.05, 0.10, 0.15, 0.20)
SEUILS_ABSTENTION = (0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40)

# Part des règles considérées comme « les plus grandes » quand on mesure si la
# couverture se fait capturer par elles.
PART_GRANDES_REGLES = 0.10

# ---------------------------------------------------------------------------
# Évaluation (src/evaluate.py) — paramètres FIGÉS à l'étape 5
# ---------------------------------------------------------------------------

# Mesure de similarité retenue pour la classification. Arrêtée sur le calibrage : le
# cosinus bat Tversky et la couverture, et l'écart croît quand on retire la pénalité de
# largeur. Ne plus toucher : le split test est ouvert.
MESURE_FIGEE = "cosinus"
