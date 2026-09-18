# JDM-N_de_N

Reproduction de Guenoune & Lafourcade (IC@PFIA 2024) : prédire la relation sémantique
entre A et B dans les constructions génitives françaises « A de B »
(*saucisse de Toulouse* → `r_lieu>origine`, *tabouret de bois* → `r_objet>matiere`)
à partir de signatures de termes construites dans JeuxDeMots (JDM).

Article : [docs/papier.pdf](docs/papier.pdf). Sujet du projet : [docs/projet.pdf](docs/projet.pdf).

## Pipeline

```
data/corpus/raw/  ──corpus_check.py──►  data/corpus/clean/  ──jdm_probe.py──►  reports/rapport_sonde_jdm.md
       │                                   (termes.csv)              │
       └──corpus_variants.py──►  data/corpus/variants/               └── via jdm_client.py ──► data/cache/jdm/
                                         │
                                         └──corpus_check.py --raw …──►  data/corpus/variants_clean/
```

Tous les scripts se lancent depuis la racine du dépôt (`python3 src/<script>.py`),
en Python 3 avec la bibliothèque standard seulement.

## Scripts

| script | lit | produit | réseau |
|---|---|---|---|
| [src/corpus_check.py](src/corpus_check.py) | `data/corpus/raw/*.csv` | `data/corpus/clean/<type>.csv`, `data/corpus/clean/termes.csv`, `reports/rapport_corpus.md` | non |
| [src/corpus_variants.py](src/corpus_variants.py) | `data/corpus/raw/*.csv` | `data/corpus/variants/*.csv`, `reports/variantes_definitude.md` | non |
| [src/jdm_client.py](src/jdm_client.py) | API JDM | `data/cache/jdm/*.json`, `logs/jdm_calls.log` | oui |
| [src/jdm_probe.py](src/jdm_probe.py) | `data/corpus/clean/termes.csv`, `data/corpus/clean/corpus_*.csv` | `reports/rapport_sonde_jdm.md` | oui (via le cache) |

- **corpus_check.py** contrôle et prépare le corpus. Il découpe chaque syntagme en A / B,
  calcule les traits de définitude (Det/NoDet, Def/NoDef, §4.4.2), signale les doublons
  et les découpages ambigus, et produit la liste des termes à interroger dans JDM.
  Les options `--raw`, `--clean` et `--report` permettent de l'appliquer à un autre dossier,
  par exemple `--raw data/corpus/variants --clean data/corpus/variants_clean --report reports/rapport_corpus_variants.md`.
- **corpus_variants.py** atténue la régularité artificielle de la définitude. Dans 8 types
  choisis, 10 lignes sur 80 reçoivent une variante de déterminant (« du X » → « d'un X »…),
  sans changer ni A, ni B, ni la relation. Le tirage est déterministe (`random.Random(42)`).
  Les variantes jugées non naturelles sont listées dans `EXCLUDED`.
- **jdm_client.py** est le module d'accès à l'API `https://jdm-api.demo.lirmm.fr/v0` et ne
  s'exécute pas seul. Il fournit un cache disque (un JSON par requête, jamais invalidé),
  un délai de politesse, des nouvelles tentatives avec backoff et un journal des appels.
  Sa docstring d'en-tête décrit les particularités de l'API.
- **jdm_probe.py** interroge JDM pour 30 termes stratifiés et mesure les traits H (`r_isa`),
  TRT (types de relations entrantes) et SST (`_INFO-SEM-*`), la polysémie et la latence.
  Le rapport produit sert à choisir les seuils des signatures. Le script tranche aussi les
  deux découpages ambigus du corpus.

## Données

| dossier | contenu | modifié par |
|---|---|---|
| `data/corpus/raw/` | corpus d'origine : 15 fichiers, 80 lignes `syntagme ; relation` (50 train puis 30 test) | **personne** |
| `data/corpus/clean/` | corpus découpé (A, B, split, définitude, ambiguïté) et `termes.csv` | corpus_check.py |
| `data/corpus/variants/` | corpus avec variantes de déterminant, même format que `raw/` | corpus_variants.py |
| `data/corpus/variants_clean/` | équivalent de `clean/` pour les variantes | corpus_check.py |
| `data/cache/jdm/` | réponses brutes de l'API, une par requête | jdm_client.py |
| `reports/` | rapports Markdown de chaque étape | tous les scripts |

## Conventions

- `data/corpus/raw/` n'est jamais modifié. L'ordre des lignes, qui porte le découpage train/test, non plus.
- Les scripts sont déterministes : une relance produit des sorties identiques octet pour octet.
- Aucune suppression automatique : les scripts signalent dans `reports/`, les décisions restent manuelles.
- Pas de lemmatisation : la morphologie est un indice discriminant (papier, §2.2.3).
- Une signature est un ensemble plat de symboles binaires, chacun étiqueté par sa provenance
  (H, TRT ou SST). Les poids JDM servent seulement à sélectionner les symboles.
