# JDM-N_de_N

Reproduction de Guenoune & Lafourcade (IC@PFIA 2024) : prédire la relation sémantique
entre A et B dans les constructions génitives françaises « A de B »
(*saucisse de Toulouse* → `r_lieu>origine`, *tabouret de bois* → `r_objet>matiere`)
à partir de signatures de termes construites dans JeuxDeMots (JDM).

Article : [docs/papier.pdf](docs/papier.pdf). Sujet du projet : [docs/projet.pdf](docs/projet.pdf).

Python 3, **bibliothèque standard uniquement**. Tous les scripts se lancent depuis la
racine du dépôt : `python3 src/<script>.py`.

## Pipeline

```
étape 1 — corpus (hors ligne, instantané)
  data/corpus/raw/ ──corpus_check.py──► data/corpus/clean/ (dont termes.csv)
         │                              + reports/rapport_corpus.md
         └──corpus_variants.py──► data/corpus/variants/ + reports/variantes_definitude.md
                    │
                    └──corpus_check.py --raw …──► data/corpus/variants_clean/
                                                  + reports/rapport_corpus_variants.md

étape 1 bis — sonde (30 termes, choix des seuils)
  termes.csv ──jdm_probe.py──► reports/rapport_sonde_jdm.md

étape 2 — collecte brute (1871 termes, 1 h 40 mesurées)
  ──jdm_payload_bench.py──► reports/phase1_payload.json   (choix des paramètres réseau)
  termes.csv ──jdm_collect.py──► data/collecte/termes_jdm.jsonl
                               + reports/rapport_collecte.md
                               + reports/remplacements_proposes.csv

  toute requête passe par jdm_client.py ──► data/cache/jdm/ + logs/jdm_calls.log
  tous les réglages viennent de config.py
```

Dépendances entre modules, sans cycle :

```
config.py     ◄── tous les autres
jdm_client.py ◄── jdm_probe.py, jdm_payload_bench.py, jdm_collect.py
corpus_check.py ◄── corpus_variants.py, jdm_probe.py
```

## État d'avancement

| étape | état |
|---|---|
| 1. Corpus contrôlé, découpé, variantes de définitude | fait |
| 1 bis. Sonde sur 30 termes, seuils recommandés | fait |
| 2. Collecte brute des traits des 1871 termes | fait — 99,9 % de couverture |
| 3. Construction des signatures, vocabulaire, similarité | à faire |

## Les modules

| module | entrée | sortie | réseau |
|---|---|---|---|
| `config.py` | — | — (constantes) | non |
| `corpus_check.py` | `data/corpus/raw/*.csv` | `data/corpus/clean/`, `termes.csv`, `reports/rapport_corpus.md` | non |
| `corpus_variants.py` | `data/corpus/raw/*.csv` | `data/corpus/variants/`, `reports/variantes_definitude.md` | non |
| `jdm_client.py` | API JDM | `data/cache/jdm/`, `logs/jdm_calls.log` | oui |
| `jdm_probe.py` | `termes.csv`, `data/corpus/clean/` | `reports/rapport_sonde_jdm.md` | oui (via le cache) |
| `jdm_payload_bench.py` | API JDM (5 termes) | `reports/phase1_payload.json` | oui |
| `jdm_collect.py` | `termes.csv`, `data/corpus/clean/` | `data/collecte/termes_jdm.jsonl`, `reports/rapport_collecte.md`, `reports/remplacements_proposes.csv` | oui (via le cache) |

### `config.py`

Rassemble chemins, réglages réseau et seuils. Aucun autre module ne contient de valeur en
dur, et celui-ci n'importe aucun module du projet.

Deux constantes portent une décision plutôt qu'un réglage :
`PARAMS_RELATIONS_ENTRANTES` (les paramètres réseau validés en phase 1) et
`SST_ANNOTATIONS_MORPHO` (les annotations que l'étape 3 pourra exclure en changeant cette
seule ligne, sans recollecter).

### `corpus_check.py`

**Prend** les 15 fichiers bruts, 80 lignes `syntagme ; relation` chacun.
**Traite** : lit en octets pour signaler ce qu'un décodage tolérant masquerait (UTF-8
invalide, BOM, champs manquants) ; découpe chaque syntagme en A / B sur la préposition ;
calcule les traits de définitude Det/NoDet et Def/NoDef selon les règles du §4.4.2, avec
la règle « B à majuscule initiale ⇒ Def forcé » ; détecte les doublons et les syntagmes à
plusieurs prépositions.
**Sort** un CSV par type avec les colonnes découpées, `termes.csv` (les couples terme/rôle
dédupliqués, entrée de l'étape 2), et un rapport de contrôle en 9 sections.

Un syntagme à plusieurs prépositions n'est **pas tranché** ici : A et B restent vides et
les découpages concurrents sont listés dans la colonne `candidats`. L'arbitrage se fait à
l'étape 2, par existence dans JDM.

Les options `--raw`, `--clean` et `--report` permettent de l'appliquer à un autre dossier,
ce qui sert à produire `variants_clean/`.

### `corpus_variants.py`

**Prend** les mêmes fichiers bruts.
**Traite** : dans 8 types sur 15, réécrit 10 lignes sur 80 (6 en train, 4 en test) pour
casser la régularité artificielle de la définitude — `du X` → `d'un X`, `de la X` →
`d'une X`, et pour `r_holo` seulement `du X` → `de X`. Le genre est lu sur le déterminant
d'origine, sans dictionnaire. A, B et la relation sont vérifiés inchangés après chaque
réécriture.
**Sort** un corpus au même format, même ordre et même nombre de lignes que la source, plus
un rapport listant chaque ligne modifiée.

Le tirage est déterministe (`random.Random(42)`) et construit pour qu'ajouter une exclusion
manuelle ne décale aucun autre tirage.

### `jdm_client.py`

Module d'accès à l'API, il ne s'exécute pas seul et ne fait aucun appel à l'import.

**Traite** chaque requête ainsi : une clé SHA-256 est calculée à partir du chemin et des
paramètres normalisés, et le cache disque est consulté avant tout appel — y compris pour
les réponses négatives, si bien qu'un terme absent n'est jamais redemandé. En cas de manque,
il attend le délai de politesse (0,3 s depuis le dernier appel réel), fait le GET, et
réessaie jusqu'à trois fois avec attente exponentielle sur panne réseau ou 5xx. Une réponse
4xx échoue immédiatement, sans nouvel essai.

Deux particularités de JDM sont absorbées ici : un nœud absent renvoie un **500** dont le
corps contient `status_code: 404`, et `relation_fields` doit contenir `w` sous peine de 500.

Chaque appel est chronométré et journalisé, et sa durée est conservée dans le fichier de
cache : les statistiques de latence restent donc reproductibles après relance.

⚠️ Le calcul du nom des fichiers de cache ne doit pas changer. Les 9 435 fichiers existants
représentent 1 h 40 de requêtes et deviendraient introuvables.

### `jdm_probe.py`

**Prend** 30 termes tirés de `termes.csv` en 5 strates de 6 (concrets, abstraits, entités
nommées, polylexicaux, pluriels), avec une graine fixe.
**Traite** : mesure pour chacun les trois traits — H (`r_isa` sortants), TRT (types de
relations entrantes), SST (`_INFO-SEM-*`) — la polysémie et la latence de chaque appel.
**Sort** un rapport qui chiffre les coupures possibles pour chaque trait.

Le script ne décide rien, il documente les options. Ses deux conclusions :

- **H** : couper au **top 20 par poids décroissant**, sans seuil absolu. Les poids forment
  un palier (≈ 500–550) jusqu'au rang 30 puis chutent ; un seuil absolu viderait les termes
  pauvres, un seuil relatif tomberait au milieu du palier.
- **TRT** : pas de coupure de taille nécessaire, mais exclure une liste de types non
  sémantiques — trois types sont présents chez les 30 termes, donc constants, donc sans
  pouvoir discriminant.

Ces coupures sont des **recommandations pour l'étape 3**. Elles ne sont appliquées nulle
part aujourd'hui.

### `jdm_payload_bench.py`

Mesure ponctuelle, faite avant la collecte, parce que les relations entrantes portent 98 %
du volume téléchargé.

**Prend** 5 termes de profils contrastés (de 197 à 150 220 relations entrantes).
**Traite** : compare 7 jeux de paramètres de `/relations/to`, et ne retient une optimisation
que si le trait TRT obtenu est **strictement identique** à la référence sans paramètre.
**Sort** le détail des mesures en JSON, relu ensuite par le rapport de collecte.

Résultat : `without_nodes=true` + `relation_fields=[type,w]` retire 82 % du volume et 94 %
de la latence, à résultat identique. `min_weight=1` gagnerait 3 points de plus mais est
écarté : c'est un filtre serveur, donc une relation de poids 0 < w < 1 ailleurs dans le
corpus disparaîtrait sans qu'on le sache.

Le script établit aussi la vraie cause des erreurs 500 : `relation_fields` doit contenir
`w`, et non « ne pas être combiné à `types_ids` » comme le supposait la sonde.

### `jdm_collect.py`

Le cœur de l'étape 2.

**Prend** les 1871 termes de `termes.csv`.
**Traite** : cinq requêtes par terme (existence du nœud, puis H, TRT, SST et raffinements),
plus deux de diagnostic si H est vide.
**Sort** une ligne JSON par terme dans `termes_jdm.jsonl`, un rapport de collecte, et un
CSV de propositions pour les termes absents de JDM.

**Le principe est de collecter brut.** Aucun seuil, aucune coupure, aucune exclusion : ni
le top 20 de H, ni l'exclusion des types TRT non sémantiques. Ces décisions appartiennent à
l'étape 3, pour qu'elles puissent varier sans relancer 1 h 40 de requêtes. H contient donc
**tous** les hyperonymes de poids > 0 — médiane 26, max 396 — et pas les 20 premiers. Le
seul filtre appliqué est `poids > 0`, qui écarte les relations *niées* dans JDM.

Le bruit connu est **marqué, jamais supprimé** : chaque hyperonyme porte un drapeau
`lang_prefix` (les traductions `en:`, `de:`…) et une `forme_normalisee` qui permettra de
fusionner les doublons de casse. Les annotations morphologiques `DET` et `NODET` sont
conservées et marquées `morpho: true`.

Pour les 47 termes sans aucun hyperonyme, le script teste la forme singulière et consigne
le résultat dans `diagnostic_singulier`. **C'est un diagnostic** : la forme originale reste
celle utilisée et le corpus n'est pas modifié. Sur les 32 formes testables, 32 existent et
32 apportent des hyperonymes — `melons` → `melon` en donne 119.

Pour les termes absents de JDM, le script **propose** une variante morphologique dans
`remplacements_proposes.csv` et n'en applique jamais aucune. Aucune proposition par
similarité sémantique : on n'a pas encore les signatures qui la justifieraient.

La passe est interruptible et reprenable : un terme déjà écrit est sauté, chaque ligne est
vidée sur disque immédiatement, et les erreurs sont consignées à part pour être réessayées
au lancement suivant. `--report-only` régénère le rapport sans aucun appel réseau.

## Données

| dossier | contenu | modifié par |
|---|---|---|
| `data/corpus/raw/` | corpus d'origine : 15 fichiers, 80 lignes `syntagme ; relation` (50 train puis 30 test) | **personne** |
| `data/corpus/clean/` | corpus découpé (A, B, split, définitude, ambiguïté) et `termes.csv` | corpus_check.py |
| `data/corpus/variants/` | corpus avec variantes de déterminant, même format que `raw/` | corpus_variants.py |
| `data/corpus/variants_clean/` | équivalent de `clean/` pour les variantes | corpus_check.py |
| `data/jdm_relations_types.csv` | référence des types de relations JDM (id, nom, description) | manuel |
| `data/cache/jdm/` | réponses brutes de l'API, une par requête — 9 435 fichiers, 928 Mo, **hors dépôt** | jdm_client.py |
| `data/collecte/` | `termes_jdm.jsonl`, `sessions.json`, et `erreurs.jsonl` seulement en cas d'échec | jdm_collect.py |
| `reports/` | rapports Markdown de chaque étape | tous les scripts |

### Format d'un enregistrement de `termes_jdm.jsonl`

Ces noms de champs sont l'interface de l'étape 3 : les changer oblige à tout recollecter.

```json
{"terme": "voiture", "collecte_utc": "2026-09-20T12:31:44+00:00", "existe": true,
 "noeud": {"id": 6890, "type": "n_term", "poids": 23063},
 "H":   [{"nom": "mode de transport", "poids": 1000.0, "type_noeud": 1,
          "lang_prefix": false, "forme_normalisee": "mode de transport"}],
 "TRT": [{"type": "r_aki", "n": 14279}],
 "SST": [{"tag": "NODET", "poids": 34.0, "morpho": true}],
 "raffinements": [{"nom": "voiture>95706", "poids": 389.0}],
 "diagnostic_singulier": null}
```

Un terme absent de JDM n'a que `terme`, `collecte_utc` et `existe: false`.

### Chiffres de la collecte

| mesure | valeur |
|---|---|
| Termes trouvés | 1869 / 1871 (99,9 %) |
| \|H\| | min 0, médiane 26, max 396 |
| \|TRT\| | min 5, médiane 39, max 77 |
| \|SST\| | min 0, médiane 2, max 13 |
| Termes à H vide | 47 (2,5 %) — 32 récupérables par le singulier |
| Termes à SST vide | 286 (15,3 %) |
| Termes polysémiques | 60,6 % |
| Durée, cache | 1 h 40, 9 435 fichiers, 928 Mo |

Les deux seuls termes absents sont « cacao de Côte » et « diamants d'Afrique », les A de
découpages ambigus concurrents. Leur absence n'est pas un manque : c'est elle qui tranche
le découpage en faveur de l'autre candidat.

## Conventions

- `data/corpus/raw/` n'est jamais modifié. L'ordre des lignes, qui porte le découpage
  train/test, non plus.
- Les scripts sont déterministes : une relance produit des sorties identiques octet pour
  octet. Les tirages aléatoires passent tous par `random.Random(42)`.
- Aucune suppression automatique : les scripts signalent dans `reports/`, les décisions
  restent manuelles.
- Pas de lemmatisation : la morphologie est un indice discriminant (papier, §2.2.3).
- Une signature est un ensemble plat de symboles binaires, chacun étiqueté par sa provenance
  (H, TRT ou SST). Les poids JDM servent seulement à sélectionner les symboles.

## Style du code

- Fonctions courtes, une responsabilité chacune, une docstring d'une ligne disant ce que la
  fonction fait et ce qu'elle retourne. Code linéaire, lisible de haut en bas.
- Noms en français. Trois exceptions, volontaires et commentées dans le code : les clés du
  **format de cache**, les **noms de paramètres de l'API JDM** et les **champs du JSONL et
  colonnes CSV**, qui sont des interfaces figées.
- Dictionnaires et listes de dictionnaires comme structures de données. Pas de dataclasses,
  pas d'héritage ; la seule classe du projet est le client HTTP, qui porte un état.
- Chaque erreur est attrapée par type précis, journalisée avec le terme concerné et comptée
  dans le rapport final. Aucun `except:` nu, aucune réponse HTTP non vérifiée, aucun appel
  réseau à l'import d'un module.

## Limite connue

`reports/rapport_sonde_jdm.md`, section 0, affirme encore que « `relation_fields` combiné à
`types_ids` provoque une erreur 500 ». La phase 1 a montré que la vraie règle est
« `relation_fields` doit contenir `w` ». Le rapport n'a pas été régénéré pour ne pas
modifier un livrable après coup ; `jdm_client.py` et `jdm_payload_bench.py` portent la
version correcte.
