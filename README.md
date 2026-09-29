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

Le projet est complet. La méthode, **somme · arbre · descente**, et ses signatures ont été
choisies en validation croisée sur l'entraînement, puis évaluées chacune une fois sur le
test.

| | F1 macro |
|---|---|
| **somme · arbre · descente, signatures retenues — test** | **0,778** |
| somme · arbre · descente, signatures initiales — test | 0,753 |
| article | 0,772 |
| apprentissage à seuil + classification exhaustive — test | 0,597 |
| plus proche voisin sur les feuilles — test | 0,585 |
| union · arbre · descente — test | 0,219 |

Avec les signatures retenues, **350 des 450 exemples de test sont justes (77,8 %)**, contre
270 pour la méthode à seuil. Nous sommes **0,006 au-dessus de l'article**, un écart qui n'est
pas une différence à cette taille de test : on peut dire « au niveau de l'article ». Sept
types sur quinze dépassent son F1, dont `r_has_property-1` (0,98 contre 0,59), qui est son
pire type ; les plus en retrait sont `r_depict`, `r_product_of` et `r_holo`.

Trois réserves, détaillées dans `reports/rapport_final.md` et
`reports/rapport_final_signatures.md` :

- **Le gain vient de la représentation, pas de l'arbre.** Comparer l'exemple aux seuls
  quinze profils de racine donne le même F1 en validation croisée (0,783). La moitié des
  prédictions se fait à la racine et le nœud gagnant couvre en moyenne 97 % de son type.
- **Le gain des signatures retenues n'est pas établi.** +0,025 de F1 sur le test, +0,033
  annoncé par la validation croisée ; mais sur les 68 exemples dont la justesse change
  (39 corrigés, 29 cassés), un test des signes donne p = 0,27.
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

**Les signatures.** Elles gardent 20 hyperonymes et tous les types TRT et SST sémantiques ;
chaque symbole est pondéré par le poids que la collecte lui donne (normalisé par terme et
par trait) et le terme lui-même n'est plus ajouté. Ces réglages, `SIGNATURES_RETENUES` dans
`config.py`, n'existent qu'en mémoire : `predire.py` et l'évaluation finale les
reconstruisent à chaque lancement depuis la collecte. `data/signatures/` garde les
signatures initiales (symboles binaires, terme sans préfixe), que lit encore
`evaluation_finale.py`.

## Historique des méthodes testées

| méthode | F1 macro | rapport |
|---|---|---|
| Apprentissage à seuil (fusion « les deux » à 0,50) + classification exhaustive | 0,597 (test) | [rapport_grasp.md](reports/rapport_grasp.md), [rapport_classification.md](reports/rapport_classification.md), [rapport_evaluation.md](reports/rapport_evaluation.md) |
| Union · arbre · descente (**écartée**) | 0,219 (test), 0,224 (validation croisée) | [methode_union_arbre_descente.md](reports/methode_union_arbre_descente.md), [rapport_arbres.md](reports/rapport_arbres.md) |
| Plus proche voisin sur les feuilles | 0,585 (test), 0,534 (validation croisée) | [rapport_arbres.md](reports/rapport_arbres.md) |
| Grille de 61 configurations (représentation × structure × classification) | de 0,224 à 0,784 (validation croisée) | [rapport_grille.md](reports/rapport_grille.md) |
| Somme · arbre · descente, signatures initiales | 0,753 (test), 0,786 (validation croisée) | [rapport_final.md](reports/rapport_final.md), [methode_somme_arbre_descente.md](reports/methode_somme_arbre_descente.md) |
| Variantes de signatures (hyperonymes, pondération, TRT/SST), 27 comparaisons | de 0,642 à 0,819 (validation croisée) | [rapport_signatures_variantes.md](reports/rapport_signatures_variantes.md) |
| **Somme · arbre · descente, signatures retenues** | **0,778** (test), 0,819 (validation croisée) | [rapport_final_signatures.md](reports/rapport_final_signatures.md) |

Les Expériences 1 à 3 de l'article (traits, définitude, élagage) ont été menées avec
l'apprentissage à seuil puis avec l'union · arbre · descente ; elles n'ont pas été
rejouées avec la somme. Le script qui les portait (`evaluate.py`), les arbres en union et
les prédictions de test de cette phase ont été supprimés ; ils restent dans le commit
`8bd078a`.

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
data/modeles/             arbres_somme.json (régénérable par grasp.py, non versionné)
   │  grille.py           compare les configurations en validation croisée, sans test
   │  variantes_signatures.py  compare les signatures en validation croisée, sans test
   │  evaluation_finale.py / evaluation_signatures.py  lisent le test une fois chacun
   ▼
data/resultats/           predictions_finales*.json, matrice_confusion_finale*.csv
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
| `classify.py` | score (formule 3), descente, métriques ; garde du code de la phase union (exhaustifs, diagnostics de branche) qui n'est plus appelé |
| `grille.py` | grille de configurations en validation croisée, ne lit pas le test |
| `evaluation_finale.py` | évaluation de la configuration retenue, lit le test une fois |
| `variantes_signatures.py` | variantes de construction des signatures (hyperonymes, pondération, TRT/SST) en validation croisée, ne lit pas le test |
| `evaluation_signatures.py` | évaluation finale des signatures retenues, lit le test une fois |
| `predire.py` | prédiction expliquée d'un syntagme quelconque, avec les signatures retenues |
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
- **Le test n'est plus vierge pour autant** : il a été lu pour la méthode à seuil, l'union
  · arbre · descente, les signatures initiales puis les signatures retenues. Chaque
  configuration a été choisie sur l'entraînement seul, donc chaque F1 de test est une
  estimation honnête de sa propre généralisation ; mais un réglage ultérieur guidé par ces
  chiffres ne le serait plus. `--rapport-seulement`, sur `evaluation_finale.py` et
  `evaluation_signatures.py`, reconstruit les rapports sans relire le test.
- Tout est **déterministe** : graines fixées, ex aequo départagés par l'ordre du corpus.
- `data/cache/jdm/` (934 Mo, ignoré par git) est **irremplaçable** : 1 h 40 d'appels API.
  La fonction de nommage des fichiers de cache ne doit jamais changer.

## Pistes

1. **Récupérer le corpus de l'article**, publié par les auteurs : la seule action qui
   transforme une comparaison entre deux systèmes sur deux jeux de données en une vraie
   reproduction.
2. **Désambiguïser** par les raffinements de sens déjà collectés (5 222, jamais utilisés).
   La pondération par rareté (idf) a été testée : elle dégrade le F1 à tous les nombres
   d'hyperonymes (jusqu'à −0,129).
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
