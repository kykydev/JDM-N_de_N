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
- combiner `relation_fields` et `types_ids` provoque une erreur 500 côté serveur ;
- les poids de relation peuvent être négatifs (relation niée).

Bibliothèque standard uniquement.
"""

import hashlib
import html
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE_URL = "https://jdm-api.demo.lirmm.fr/v0"
CACHE_DIR = ROOT / "data" / "cache" / "jdm"
LOG_PATH = ROOT / "logs" / "jdm_calls.log"

log = logging.getLogger("jdm")


class JDMNotFound(Exception):
    """Le nœud demandé n'existe pas dans JDM."""


class JDMError(Exception):
    """Échec après tous les essais (réseau, 5xx, réponse illisible)."""


def _setup_logging():
    if log.handlers:
        return
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(handler)
    log.setLevel(logging.INFO)


def _is_not_found(status, body):
    if status == 404:
        return True
    try:
        payload = json.loads(body)
    except (ValueError, TypeError):
        return False
    return isinstance(payload, dict) and (
        payload.get("status_code") == 404 or "not found" in str(payload.get("detail", "")).lower())


class JDMClient:
    def __init__(self, base_url=BASE_URL, cache_dir=CACHE_DIR, delay=0.3, timeout=10.0,
                 retries=3, backoff=1.0, offline=False):
        self.base_url = base_url.rstrip("/")
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.delay = delay
        self.timeout = timeout
        self.retries = retries
        self.backoff = backoff
        self.offline = offline  # True : lève une erreur plutôt que d'appeler le réseau
        self._last_call = 0.0
        self.calls = []  # une entrée par requête servie (cache ou réseau)
        _setup_logging()

    # ------------------------------------------------------------------ bas niveau

    @staticmethod
    def _norm_params(params):
        """Paramètres -> liste triée de paires (les listes deviennent des clés répétées)."""
        pairs = []
        for key, value in (params or {}).items():
            if value is None:
                continue
            values = value if isinstance(value, (list, tuple)) else [value]
            for v in values:
                pairs.append((key, str(v).lower() if isinstance(v, bool) else str(v)))
        return sorted(pairs)

    def _cache_path(self, path, pairs):
        key = json.dumps({"path": path, "params": pairs}, ensure_ascii=False, sort_keys=True)
        return self.cache_dir / (hashlib.sha256(key.encode("utf-8")).hexdigest() + ".json")

    def _get(self, path, params=None, timeout=None):
        pairs = self._norm_params(params)
        cache_file = self._cache_path(path, pairs)
        if cache_file.exists():
            entry = json.loads(cache_file.read_text(encoding="utf-8"))
            self.calls.append({"path": path, "cached": True, "status": entry["status"],
                               "elapsed_s": entry.get("elapsed_s"), "bytes": entry.get("bytes")})
            if entry["status"] == "not_found":
                raise JDMNotFound(path)
            return entry["data"]
        if self.offline:
            raise JDMError(f"hors-ligne et absent du cache : {path} {pairs}")

        url = self.base_url + path + ("?" + urllib.parse.urlencode(pairs) if pairs else "")
        timeout = timeout or self.timeout
        last_exc = None
        for attempt in range(self.retries):
            wait = self.delay - (time.monotonic() - self._last_call)
            if wait > 0:
                time.sleep(wait)
            t0 = time.monotonic()
            status, body, exc = None, b"", None
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers={"Accept": "application/json"}),
                                            timeout=timeout) as resp:
                    status, body = resp.status, resp.read()
            except urllib.error.HTTPError as e:
                status, body = e.code, e.read()
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
                exc = e
            elapsed = time.monotonic() - t0
            self._last_call = time.monotonic()
            log.info("GET %s status=%s elapsed=%.3fs bytes=%d attempt=%d%s", url, status, elapsed,
                     len(body), attempt + 1, f" exc={exc!r}" if exc else "")

            if exc is None and status is not None:
                if _is_not_found(status, body):
                    self._store(cache_file, path, pairs, "not_found", None, elapsed, len(body))
                    self.calls.append({"path": path, "cached": False, "status": "not_found",
                                       "elapsed_s": elapsed, "bytes": len(body)})
                    raise JDMNotFound(path)
                if 200 <= status < 300:
                    try:
                        data = json.loads(body)
                    except ValueError as e:
                        exc = e
                    else:
                        self._store(cache_file, path, pairs, "ok", data, elapsed, len(body))
                        self.calls.append({"path": path, "cached": False, "status": "ok",
                                           "elapsed_s": elapsed, "bytes": len(body)})
                        return data
                elif status < 500:
                    raise JDMError(f"HTTP {status} sur {url} : {body[:200]!r}")
            last_exc = exc or JDMError(f"HTTP {status} sur {url}")
            if attempt + 1 < self.retries:
                pause = self.backoff * 2 ** attempt
                log.warning("nouvel essai dans %.1fs (%r)", pause, last_exc)
                time.sleep(pause)
        self.calls.append({"path": path, "cached": False, "status": "error", "elapsed_s": None, "bytes": 0})
        raise JDMError(f"échec après {self.retries} essais : {url} ({last_exc!r})")

    def _store(self, cache_file, path, pairs, status, data, elapsed, size):
        entry = {"request": {"path": path, "params": pairs}, "status": status,
                 "elapsed_s": round(elapsed, 4), "bytes": size, "data": data}
        tmp = cache_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(entry, ensure_ascii=False), encoding="utf-8")
        tmp.replace(cache_file)

    @staticmethod
    def _q(name):
        return urllib.parse.quote(name, safe="")

    # ------------------------------------------------------------------ API

    def relation_types(self):
        return self._get("/relations_types")

    def node_types(self):
        return self._get("/nodes_types")

    def node_by_name(self, name):
        return self._get(f"/node_by_name/{self._q(name)}")

    def node_by_id(self, node_id):
        return self._get(f"/node_by_id/{int(node_id)}")

    def refinements(self, name):
        """{nodes, refinements} : `refinements` liste les nœuds « terme>id[>id] »."""
        return self._get(f"/refinements/{self._q(name)}")

    def relations_from(self, name, types_ids=None, timeout=None, **params):
        """Relations sortantes {nodes, relations}. Ne pas combiner types_ids et relation_fields."""
        return self._get(f"/relations/from/{self._q(name)}", {"types_ids": types_ids, **params}, timeout)

    def relations_to(self, name, types_ids=None, timeout=None, **params):
        """Relations entrantes {nodes, relations}. Ne pas combiner types_ids et relation_fields."""
        return self._get(f"/relations/to/{self._q(name)}", {"types_ids": types_ids, **params}, timeout)

    # ------------------------------------------------------------------ utilitaires

    def exists(self, name):
        try:
            self.node_by_name(name)
            return True
        except JDMNotFound:
            return False

    def relation_type_maps(self):
        """(nom -> id, id -> nom) pour les types de relations, ex. 'r_isa' <-> 6."""
        types = self.relation_types()
        return {t["name"]: t["id"] for t in types}, {t["id"]: t["name"] for t in types}


def resolve_refinement_name(name, id_to_name, client=None):
    """Nom lisible : entités HTML décodées (« &#339;uvre » -> « œuvre ») et ids de
    raffinement traduits (« chatte>150 » -> « chatte>chat »). Un id absent de
    `id_to_name` est demandé à node_by_id si `client` est fourni, sinon laissé tel quel."""
    name = html.unescape(name)
    if ">" not in name:
        return name
    head, *parts = name.split(">")
    out = [head]
    for part in parts:
        if part.isdigit():
            node_id = int(part)
            if node_id not in id_to_name and client is not None:
                try:
                    id_to_name[node_id] = client.node_by_id(node_id)["name"]
                except (JDMNotFound, JDMError):
                    pass
            part = html.unescape(id_to_name.get(node_id, part))
        out.append(part)
    return ">".join(out)
