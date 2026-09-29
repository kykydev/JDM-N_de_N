# JDM-N_de_N

Reproduction de **Guenoune & Lafourcade, IC@PFIA 2024**, « Extraction automatique de
règles pour la détermination de types de relations sémantiques dans les constructions
génitives en français ».

Article : [docs/papier.pdf](docs/papier.pdf) · Sujet du projet : [docs/projet.pdf](docs/projet.pdf)

**Le problème.** Dans « A de B », quelle relation sémantique lie A et B ? « vin de
France » porte une origine, « coque du bateau » une holonymie, « photo d'une famille »
une dépiction. L'article retient 15 types et cherche à les prédire automatiquement.

**L'idée.** On ne regarde pas la forme du syntagme mais ce que le réseau lexical
**JeuxDeMots** sait de A et de B. Ce « ce que JDM sait d'un terme » s'appelle une
**signature** : un ensemble d'étiquettes textuelles, réunissant les hyperonymes du terme
(`H:`), les types de relations qui pointent vers lui (`TRT:`) et ses types ontologiques
standard (`SST:`). Le côté gauche (A) et le côté droit (B) ne sont jamais mélangés :
« vin de France » n'est pas « France de vin ».

Python 3, **bibliothèque standard uniquement** (`requests` pour les appels JDM). Aucun
modèle neuronal. Tous les scripts se lancent depuis la racine : `py -3 src/<script>.py`.

---

## Où en est-on

Le projet est complet. La méthode retenue, **somme · arbre · descente**, a été choisie en
validation croisée sur l'entraînement, puis évaluée une fois sur le test.

| | F1 macro |
|---|---|
| **somme · arbre · descente — test** | **0,753** |
| somme · arbre · descente — validation croisée (5 plis) | 0,784 ± 0,042 |
| article | 0,772 |
| plus proche voisin sur les feuilles — test | 0,585 |
| apprentissage à seuil + classification exhaustive — test | 0,597 |
| union · arbre · descente — test | 0,219 |

Sur les 450 exemples de test, **340 sont justes (75,6 %)**, contre 270 pour la méthode à
seuil : 110 erreurs au lieu de 180. Nous sommes **0,019 sous l'article**, un écart bien
inférieur à l'écart-type entre plis de la validation croisée. Six types sur quinze
dépassent le F1 de l'article, dont `r_has_property-1` (0,95 contre 0,59), qui est son pire
type ; les plus en retrait sont `r_product_of`, `r_holo` et `r_depict`.

Deux réserves, détaillées dans `reports/rapport_final.md` :

- **Le gain vient de la représentation, pas de l'arbre.** Comparer l'exemple aux seuls
  quinze profils de racine donne le même F1 en validation croisée (0,783). La moitié des
  prédictions se fait à la racine et le nœud gagnant couvre en moyenne 97 % de son type.
- **L'hypothèse de polysémie n'est pas confirmée.** La part des erreurs attribuées à la
  polysémie tombe de 57,8 % à 20,9 %, mais c'est un résidu de l'ordre de priorité des
  causes ; l'écart de taux d'erreur entre exemples polysémiques et autres ne se resserre
  pas (+0,082 contre +0,055).

## La méthode retenue

Chaque type de relation est représenté par un arbre construit par fusions successives des
deux nœuds les plus proches ; un nœud fusionné est la somme des vecteurs de ses enfants,
donc un profil moyen de ses exemples. Un syntagme est classé en descendant chaque arbre
depuis sa racine tant qu'un enfant fait mieux ; le meilleur nœud d'arrêt donne le type.
Détail et exemples : [reports/methode_somme_arbre_descente.md](reports/methode_somme_arbre_descente.md)

Les trois choix qui la définissent sont figés dans `src/config.py`
(`REPRESENTATION`, `STRUCTURE`, `CLASSIFICATION`) ; les autres options restent
disponibles en paramètre. Le lien de construction est le minimum des deux côtés, le score
de classification la moyenne (formule 3 de l'article).

## Historique des méthodes testées

| méthode | F1 macro | rapport |
|---|---|---|
| Apprentissage à seuil (fusion « les deux » à 0,50) + classification exhaustive | 0,597 (test) | [rapport_grasp.md](reports/rapport_grasp.md), [rapport_classification.md](reports/rapport_classification.md), [rapport_evaluation.md](reports/rapport_evaluation.md) |
| Union · arbre · descente (**écartée**) | 0,219 (test), 0,224 (validation croisée) | [methode_union_arbre_descente.md](reports/methode_union_arbre_descente.md), [rapport_arbres.md](reports/rapport_arbres.md) |
| Plus proche voisin sur les feuilles | 0,585 (test), 0,534 (validation croisée) | [rapport_arbres.md](reports/rapport_arbres.md) |
| Grille de 61 configurations (représentation × structure × classification) | de 0,224 à 0,784 (validation croisée) | [rapport_grille.md](reports/rapport_grille.md) |
| **Somme · arbre · descente** (retenue) | **0,753** (test), 0,784 (validation croisée) | [rapport_final.md](reports/rapport_final.md), [methode_somme_arbre_descente.md](reports/methode_somme_arbre_descente.md) |

Les Expériences 1 à 3 de l'article (traits, définitude, élagage) ont été menées avec
l'apprentissage à seuil puis avec l'union · arbre · descente ; elles n'ont pas été
rejouées avec la somme.

Les diagnostics qui ont fixé la construction des signatures restent valables quelle que
soit la méthode : [rapport_sonde_jdm.md](reports/rapport_sonde_jdm.md) (coupure à 20
hyperonymes, 15 types de relations non sémantiques écartés) et
[diagnostic_trt.md](reports/diagnostic_trt.md) avec
[diagnostic_trt_tour2.md](reports/diagnostic_trt_tour2.md) (garder tous les types TRT
sémantiques, lecture fidèle à l'article).

## Le pipeline

```
data/corpus/raw/          15 fichiers, 80 syntagmes annotés chacun
   │  corpus_check.py     découpe A / de / B, calcule det + définitude
   ▼
data/corpus/clean/        1200 lignes propres + termes.csv (1867 termes)
   │  jdm_collect.py      interroge l'API JeuxDeMots — ~1 h 40, mis en cache
   ▼
data/collecte/            1 ligne JSON par terme : hyperonymes, relations, annotations
   │  signatures.py       transforme en ensembles de symboles textuels
   ▼
data/signatures/          1867 signatures, une par terme
   │  grasp.py            un arbre par type, fusion des deux nœuds les plus proches
   ▼
data/modeles/             arbres_somme.json (arbres.json : ancienne version en union)
   │  grille.py           compare les configurations en validation croisée, sans test
   │  evaluation_finale.py  réapprend sur les 750 exemples, lit le test une fois
   ▼
data/resultats/           predictions_finales.json, matrice_confusion_finale.csv
   │  predire.py          un syntagme quelconque -> sa relation, expliquée
   ▼
                          l'outil de démonstration
```

Chaque étape écrit un rapport dans `reports/`. **Les rapports sont le produit principal
du projet** : le code produit des chiffres, les rapports disent ce qu'ils signifient.

## Les modules

| module | rôle |
|---|---|
| `config.py` | toutes les constantes, dont la configuration retenue. N'importe aucun autre module. |
| `jdm_client.py` | client HTTP JDM : cache disque, reprises, politesse |
| `corpus_check.py` | contrôle du corpus, découpage A / B |
| `jdm_collect.py` | collecte des traits bruts de 1867 termes |
| `signatures.py` | signatures des termes, similarité cosinus |
| `grasp.py` | construction des arbres, en union ou en somme |
| `classify.py` | score (formule 3), descente, exhaustifs, métriques |
| `evaluate.py` | Expériences 1 et 2 de l'article (traits, définitude) |
| `grille.py` | grille de configurations en validation croisée, ne lit pas le test |
| `evaluation_finale.py` | évaluation de la configuration retenue, lit le test une fois |
| `predire.py` | prédiction expliquée d'un syntagme quelconque |
| `rejouer.py` | relance la chaîne dans l'ordre après un changement de `config.py` |

## L'outil de démonstration

```
py -3 src/predire.py "saucisse de Toulouse"
py -3 src/predire.py                      # boucle interactive
py -3 src/predire.py --fichier liste.txt  # un syntagme par ligne, sortie CSV
```

Options : `--top N` (types affichés), `--detail` (signatures complètes), `--sans-api`
(hors ligne, signatures déjà connues seulement). Pour chaque syntagme, l'outil affiche le
classement des types, le **chemin de descente** dans l'arbre gagnant avec le score à
chaque niveau, le nœud d'arrêt (racine, nœud interne ou feuille), sa part du type et les
exemples d'entraînement qu'il couvre, et les **symboles décisifs** : ceux de
l'intersection qui pèsent le plus dans le profil du nœud. Un écart de moins de 5 % avec
le 2ᵉ type affiche « décision serrée ». Si aucun nœud ne partage le moindre symbole, il
refuse de répondre.

## Changer un paramètre et tout réévaluer

Les réglages sont dans `config.py`. Après un changement (`H_TOP`, `TRT_POLITIQUE`, ou
`REPRESENTATION` pour comparer avec l'union) :

```
py -3 src/rejouer.py --sans-test   # signatures, arbres, validation croisée
py -3 src/rejouer.py               # ajoute l'évaluation qui lit le test
```

La collecte n'est jamais rejouée : elle stocke les traits bruts, sans coupure, et aucun
réglage n'en dépend. Aucun appel réseau, une minute environ en tout.

## Discipline expérimentale

- **Le choix parmi les 61 configurations s'est fait sur l'entraînement seul**, en
  validation croisée (5 plis stratifiés). Le test avait certes montré l'échec de l'union ·
  arbre · descente, ce qui a motivé la grille, mais il n'a départagé aucune configuration.
- **Le test n'est plus vierge pour autant** : il avait déjà été lu pour évaluer la
  méthode à seuil et l'union · arbre · descente. Le 0,753 est une estimation de
  généralisation honnête pour la configuration retenue, mais un réglage ultérieur
  guidé par ce chiffre ne le serait plus. `evaluation_finale.py --rapport-seulement`
  reconstruit le rapport sans relire le test.
- Tout est **déterministe** : graines fixées, ex aequo départagés par l'ordre du corpus.
- `data/cache/jdm/` (934 Mo, ignoré par git) est **irremplaçable** : 1 h 40 d'appels API.
  La fonction de nommage des fichiers de cache ne doit jamais changer.

## Pistes

1. **Récupérer le corpus de l'article**, publié par les auteurs : la seule action qui
   transforme une comparaison entre deux systèmes sur deux jeux de données en une vraie
   reproduction.
2. **Pondérer par la rareté** des symboles dans les profils, et **désambiguïser** par les
   raffinements de sens déjà collectés (5 222, jamais utilisés).
3. **Comprendre pourquoi l'arbre n'apporte rien de plus que les racines** : les arbres en
   somme sont des peignes (profondeur 40 à 49 pour 50 feuilles), sans sous-familles.

## Conventions

- Noms de fonctions et de variables **en français**, une docstring d'une ligne chacune.
- Fonctions courtes, une responsabilité. **Pas de classes, pas de dataclasses.**
  Dictionnaires, listes et ensembles.
- Erreurs attrapées par type précis, **jamais d'`except` nu**.
- Les chemins d'URL de l'API JDM restent **en anglais** : ce sont des littéraux du
  protocole, pas des noms à traduire.
- Rapports en Markdown, chiffres à la française (virgule décimale).
