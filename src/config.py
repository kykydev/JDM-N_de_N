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
DOSSIER_CORPUS_VARIANTES = DOSSIER_CORPUS / "variants"
FICHIER_TERMES = DOSSIER_CORPUS_PROPRE / "termes.csv"

DOSSIER_CACHE = DOSSIER_DONNEES / "cache"
DOSSIER_CACHE_JDM = DOSSIER_CACHE / "jdm"

DOSSIER_COLLECTE = DOSSIER_DONNEES / "collecte"
FICHIER_COLLECTE = DOSSIER_COLLECTE / "termes_jdm.jsonl"
FICHIER_ERREURS = DOSSIER_COLLECTE / "erreurs.jsonl"
FICHIER_SESSIONS = DOSSIER_COLLECTE / "sessions.json"

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

# Variantes de déterminant (src/corpus_variants.py) : lignes modifiées par split,
# soit 6/50 en train et 4/30 en test = 10/80 = 12,5 % des lignes d'un type.
CIBLE_VARIANTES = {"train": 6, "test": 4}

# ---------------------------------------------------------------------------
# Sonde (src/jdm_probe.py)
# ---------------------------------------------------------------------------

# Graine du tirage des strates : la sonde doit être reproductible à l'identique.
GRAINE_ALEATOIRE = 42
TERMES_PAR_STRATE = 6

# Plafond de H pendant la sonde, et rangs auxquels la décroissance des poids est mesurée.
H_PLAFOND_SONDE = 50
H_RANGS_MESURES = [1, 5, 10, 20, 30, 50]

# Coupure de H recommandée par la sonde. Proposition : rien ne l'applique à la collecte.
H_TOP_RECOMMANDE = 20

# Types de relations entrantes méta, lexicaux ou techniques : candidats à l'exclusion du
# trait TRT. Proposition soumise à décision, non appliquée aux mesures brutes.
TRT_TYPES_NON_SEMANTIQUES = (
    "r_aki", "r_wiki", "r_associated", "r_context", "r_variante", "r_translation", "r_lemma",
    "r_meaning/glose", "r_raff_sem-1", "r_sing_form", "r_der_morpho", "r_masc", "r_homophone",
    "r_locution", "r_error",
)
