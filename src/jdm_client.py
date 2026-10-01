#!/usr/bin/env python3
"""Client minimal et poli pour l'API JeuxDeMots (https://jdm-api.demo.lirmm.fr/v0).

- Cache disque : un JSON par requête dans data/cache/jdm/, nommé par le SHA-256 du
  chemin et des paramètres ; consulté avant tout appel réseau, jamais invalidé.
  Les réponses « introuvable » sont aussi mises en cache (réponse négative).
- Politesse : délai minimal entre deux appels réels (0,3 s par défaut), timeout,
  3 essais avec backoff exponentiel sur erreur réseau ou 5xx. Aucun parallélisme.
- Chaque appel réel est chronométré, journalisé (logs/jdm_calls.log) et sa durée
  est conservée dans le fichier de cache, pour que les statistiques de latence
  restent reproductibles après relance.

Particularités de l'API constatées le 2026-09-18 (voir reports/rapport_sonde_jdm.md) :
- un nœud inexistant renvoie HTTP 500 avec {"status_code": 404, "detail": "... not found!"} ;
- `relation_fields` doit contenir `w`, sinon le serveur répond 500 (mesuré en phase 2 :
  ce n'est pas la combinaison avec `types_ids` qui plante, contrairement à ce que la
  sonde avait supposé) ;
- les poids de relation peuvent être négatifs (relation niée).

Aucun appel réseau n'est fait à l'import. Bibliothèque standard uniquement.
"""

import hashlib
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import config

log = logging.getLogger("jdm")


class JDMIntrouvable(Exception):
    """Le nœud demandé n'existe pas dans JDM."""


class JDMErreur(Exception):
    """Échec après tous les essais (réseau, 5xx, réponse illisible)."""


# ---------------------------------------------------------------------------
# Journalisation
# ---------------------------------------------------------------------------

def preparer_journal():
    """Branche le journal des appels sur logs/jdm_calls.log, une seule fois. Ne retourne rien."""
    if log.handlers:
        return
    config.FICHIER_LOG_APPELS.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(config.FICHIER_LOG_APPELS, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(handler)
    log.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Nommage des fichiers de cache
# ---------------------------------------------------------------------------
#
# ATTENTION : les deux fonctions qui suivent déterminent le nom de chaque fichier du
# cache. Le cache représente deux heures de requêtes. Toute modification de leur calcul,
# fût-elle cosmétique, rend les 9 398 fichiers déjà écrits introuvables et oblige à tout
# recollecter. Leur corps est repris au caractère près de la version initiale.

def normaliser_parametres(params):
    """Paramètres -> liste triée de paires (les listes deviennent des clés répétées)."""
    paires = []
    for cle, valeur in (params or {}).items():
        if valeur is None:
            continue
        valeurs = valeur if isinstance(valeur, (list, tuple)) else [valeur]
        for v in valeurs:
            paires.append((cle, str(v).lower() if isinstance(v, bool) else str(v)))
    return sorted(paires)


def chemin_cache(dossier_cache, chemin, paires):
    """Fichier de cache d'une requête, nommé par le SHA-256 du chemin et des paramètres."""
    cle = json.dumps({"path": chemin, "params": paires}, ensure_ascii=False, sort_keys=True)
    return dossier_cache / (hashlib.sha256(cle.encode("utf-8")).hexdigest() + ".json")


# ---------------------------------------------------------------------------
# Lecture des réponses HTTP
# ---------------------------------------------------------------------------

def est_introuvable(statut, corps):
    """Dit si la réponse signale un nœud inexistant. Retourne un booléen.

    JDM renvoie un 500 dont le corps porte `status_code: 404`, d'où la lecture du corps."""
    if statut == 404:
        return True
    try:
        charge = json.loads(corps)
    except (ValueError, TypeError):
        return False
    return isinstance(charge, dict) and (
        charge.get("status_code") == 404 or "not found" in str(charge.get("detail", "")).lower())


def construire_url(url_base, chemin, paires):
    """Assemble l'URL complète d'une requête. Retourne une chaîne."""
    return url_base + chemin + ("?" + urllib.parse.urlencode(paires) if paires else "")


def executer_requete(url, timeout):
    """Fait un appel HTTP. Retourne (statut, corps, exception) : exception non nulle si
    l'appel n'a pas abouti du tout (réseau, timeout), sinon statut et corps sont remplis."""
    try:
        requete = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(requete, timeout=timeout) as reponse:
            return reponse.status, reponse.read(), None
    except urllib.error.HTTPError as e:
        return e.code, e.read(), None
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
        return None, b"", e


def encoder_segment(nom):
    """Encode un nom de nœud pour l'insérer dans un chemin d'URL. Retourne une chaîne."""
    return urllib.parse.quote(nom, safe="")


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class ClientJDM:
    """Client HTTP avec cache disque, délai de politesse et nouvelle tentative sur 5xx."""

    def __init__(self, url_base=config.URL_BASE_JDM, dossier_cache=config.DOSSIER_CACHE_JDM,
                 delai=config.DELAI_POLITESSE, timeout=config.TIMEOUT_DEFAUT,
                 essais=config.NB_ESSAIS, backoff=config.BACKOFF, hors_ligne=False):
        self.url_base = url_base.rstrip("/")
        self.dossier_cache = Path(dossier_cache)
        self.dossier_cache.mkdir(parents=True, exist_ok=True)
        self.delai = delai
        self.timeout = timeout
        self.essais = essais
        self.backoff = backoff
        self.hors_ligne = hors_ligne  # True : lève une erreur plutôt que d'appeler le réseau
        self._dernier_appel = 0.0
        self.appels = []  # une entrée par requête servie (cache ou réseau)
        preparer_journal()

    # ------------------------------------------------------------------ cache

    def _lire_cache(self, fichier):
        """Lit une réponse déjà en cache. Retourne l'entrée, ou None si absente du cache."""
        if not fichier.exists():
            return None
        return json.loads(fichier.read_text(encoding="utf-8"))

    def _ecrire_cache(self, fichier, chemin, paires, statut, donnees, duree, taille):
        """Écrit une réponse dans le cache, par fichier temporaire puis renommage atomique."""
        entree = {"request": {"path": chemin, "params": paires}, "status": statut,
                  "elapsed_s": round(duree, 4), "bytes": taille, "data": donnees}
        temporaire = fichier.with_suffix(".tmp")
        temporaire.write_text(json.dumps(entree, ensure_ascii=False), encoding="utf-8")
        temporaire.replace(fichier)

    def _noter_appel(self, chemin, depuis_cache, statut, duree, taille):
        """Ajoute une ligne au relevé des requêtes servies, pour les statistiques. Ne retourne rien."""
        self.appels.append({"path": chemin, "cached": depuis_cache, "status": statut,
                           "elapsed_s": duree, "bytes": taille})

    # ------------------------------------------------------------------ réseau

    def _attendre_politesse(self):
        """Attend que le délai minimal depuis le dernier appel réel soit écoulé. Ne retourne rien."""
        reste = self.delai - (time.monotonic() - self._dernier_appel)
        if reste > 0:
            time.sleep(reste)

    def _tenter_appel(self, url, timeout, numero_essai):
        """Fait un appel réseau, le chronomètre et le journalise. Retourne (statut, corps, exception, durée)."""
        self._attendre_politesse()
        debut = time.monotonic()
        statut, corps, exception = executer_requete(url, timeout)
        duree = time.monotonic() - debut
        self._dernier_appel = time.monotonic()
        log.info("GET %s status=%s elapsed=%.3fs bytes=%d attempt=%d%s", url, statut, duree,
                 len(corps), numero_essai, f" exc={exception!r}" if exception else "")
        return statut, corps, exception, duree

    # ------------------------------------------------------------------ requête complète

    def _get(self, path, params=None, timeout=None):
        """Sert une requête : cache d'abord, sinon réseau avec nouvelles tentatives.
        Retourne les données JSON. Lève JDMIntrouvable si le nœud n'existe pas, JDMErreur sinon."""
        paires = normaliser_parametres(params)
        fichier = chemin_cache(self.dossier_cache, path, paires)

        entree = self._lire_cache(fichier)
        if entree is not None:
            self._noter_appel(path, True, entree["status"], entree.get("elapsed_s"),
                              entree.get("bytes"))
            if entree["status"] == "not_found":
                raise JDMIntrouvable(path)
            return entree["data"]

        if self.hors_ligne:
            raise JDMErreur(f"hors-ligne et absent du cache : {path} {paires}")

        url = construire_url(self.url_base, path, paires)
        timeout = timeout or self.timeout
        derniere_erreur = None
        for essai in range(self.essais):
            statut, corps, exception, duree = self._tenter_appel(url, timeout, essai + 1)

            if exception is None and statut is not None:
                if est_introuvable(statut, corps):
                    self._ecrire_cache(fichier, path, paires, "not_found", None, duree, len(corps))
                    self._noter_appel(path, False, "not_found", duree, len(corps))
                    raise JDMIntrouvable(path)
                if 200 <= statut < 300:
                    try:
                        donnees = json.loads(corps)
                    except ValueError as e:
                        exception = e  # réponse illisible : on réessaie comme sur une panne
                    else:
                        self._ecrire_cache(fichier, path, paires, "ok", donnees, duree, len(corps))
                        self._noter_appel(path, False, "ok", duree, len(corps))
                        return donnees
                elif statut < 500:
                    raise JDMErreur(f"HTTP {statut} sur {url} : {corps[:200]!r}")

            derniere_erreur = exception or JDMErreur(f"HTTP {statut} sur {url}")
            if essai + 1 < self.essais:
                attente = self.backoff * 2 ** essai
                log.warning("nouvel essai dans %.1fs (%r)", attente, derniere_erreur)
                time.sleep(attente)

        self._noter_appel(path, False, "error", None, 0)
        raise JDMErreur(f"échec après {self.essais} essais : {url} ({derniere_erreur!r})")

    # ------------------------------------------------------------------ API

    def types_de_relations(self):
        """Récupère la liste des types de relations de JDM. Retourne une liste de dicts."""
        return self._get("/relations_types")

    def types_de_noeuds(self):
        """Récupère la liste des types de nœuds de JDM. Retourne une liste de dicts."""
        return self._get("/nodes_types")

    def noeud_par_nom(self, nom):
        """Récupère le nœud portant ce nom. Retourne le dict du nœud, ou lève JDMIntrouvable."""
        return self._get(f"/node_by_name/{encoder_segment(nom)}")

    def noeud_par_id(self, id_noeud):
        """Récupère le nœud portant cet identifiant. Retourne le dict du nœud."""
        return self._get(f"/node_by_id/{int(id_noeud)}")

    def raffinements(self, nom):
        """Récupère les raffinements d'un terme. Retourne {nodes, refinements}.

        Plante côté serveur quand un raffinement est nommé « terme>glose » : la sonde
        mesure donc la polysémie par r_raff_sem sortant plutôt que par cet endpoint."""
        return self._get(f"/refinements/{encoder_segment(nom)}")

    def relations_sortantes(self, nom, types_ids=None, timeout=None, **parametres):
        """Récupère les relations sortantes d'un terme. Retourne {nodes, relations}."""
        return self._get(f"/relations/from/{encoder_segment(nom)}",
                         {"types_ids": types_ids, **parametres}, timeout)

    def relations_entrantes(self, nom, types_ids=None, timeout=None, **parametres):
        """Récupère les relations entrantes d'un terme. Retourne {nodes, relations}."""
        return self._get(f"/relations/to/{encoder_segment(nom)}",
                         {"types_ids": types_ids, **parametres}, timeout)

    # ------------------------------------------------------------------ utilitaires

    def existe(self, nom):
        """Dit si le terme existe dans JDM sous cette forme exacte. Retourne un booléen."""
        try:
            self.noeud_par_nom(nom)
            return True
        except JDMIntrouvable:
            return False

    def tables_types_relations(self):
        """Construit les tables des types de relations. Retourne (nom -> id, id -> nom)."""
        types = self.types_de_relations()
        return {t["name"]: t["id"] for t in types}, {t["id"]: t["name"] for t in types}
