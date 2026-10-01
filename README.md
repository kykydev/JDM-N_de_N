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
standard (`SST:`). Chaque étiquette **porte un poids réel**, repris de la force que JDM
donne à la relation : une signature est donc un vecteur creux `symbole -> poids`, et non
un simple ensemble. Le côté gauche (A) et le côté droit (B) ne sont jamais mélangés :
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
| **somme · arbre · descente, signatures retenues (`jdm · T2`) — test** | **0,778** |
| somme · arbre · descente, signatures binaires (`binaire · T0`) — test | 0,753 |
| article | 0,772 |
| apprentissage à seuil + classification exhaustive — test | 0,597 |
| plus proche voisin sur les feuilles — test | 0,585 |
| union · arbre · descente — test | 0,219 |

Avec les signatures retenues, **350 des 450 exemples de test sont justes (77,8 %)**, contre
270 pour la méthode à seuil. Nous sommes **0,006 au-dessus de l'article**, un écart qui n'est
pas une différence à cette taille de test : on peut dire « au niveau de l'article ». Sept
types sur quinze dépassent son F1, dont `r_has_property-1` (0,98 contre 0,59), qui est son
pire type ; les plus en retrait sont `r_depict`, `r_product_of` et `r_holo`.

Quatre réserves, détaillées dans `reports/rapport_final.md` et
`reports/rapport_final_signatures.md` :

- **Le gain vient de la représentation, pas de l'arbre.** Comparer l'exemple aux seuls
  quinze profils de racine donne le même F1 en validation croisée (0,783). Les prédictions
  se font à la racine dans **50,9 %** des cas avec les signatures binaires et **43,6 %**
  avec les signatures retenues ; dans les deux cas le nœud gagnant couvre en moyenne 97 %
  des exemples de son type. Les arbres sont des peignes, et descendre n'y retire que
  quelques feuilles du profil — voir
  [methode_somme_arbre_descente.md](reports/methode_somme_arbre_descente.md) §3 et §4.
- **Le gain des signatures retenues n'est pas établi, et il mêle deux changements.**
  +0,025 de F1 sur le test, +0,033 annoncé par la validation croisée (0,819 contre 0,786,
  sur les mêmes 15 mesures) ; mais sur les 68 exemples dont la justesse change (39
  corrigés, 29 cassés), un test des signes donne **p = 0,27**. Et ce gain additionne deux
  réglages, car les signatures retenues changent à la fois les poids (`binaire` → `jdm`)
  et le symbole du terme (`T0` présent → `T2` retiré) : le retrait du terme vaut
  **+0,003 ± 0,011**, sous son écart-type, et la pondération **+0,030 ± 0,028** (+0,028 sur
  dix graines, p = 0,002). L'écart de test, lui, ne sépare pas les deux.
- **La pondération casse presque autant qu'elle corrige.** Sur les 450 exemples de test,
  **39 corrigés contre 29 cassés** — solde net de 10. **Cinq types sur quinze reculent**
  (`r_depict`, `r_has_causatif`, `r_social_tie`, `r_own-1`, `r_processus_agent`), et
  `r_depict` devient un **aimant** : 37 prédictions pour 30 attendus, son F1 tombant de
  0,61 à 0,54. Le gain macro de 0,025 est donc un solde, pas une amélioration uniforme.
- **L'hypothèse de polysémie n'est pas confirmée.** La part des erreurs attribuées à la
  polysémie tombe de 57,8 % à 20,9 %, mais c'est un résidu de l'ordre de priorité des
  causes ; l'écart de taux d'erreur entre exemples polysémiques et autres ne se resserre
  pas (+0,082 contre +0,055). **Ces chiffres-là, comme les 74,5 % de « classe multiple »,
  viennent de l'évaluation des signatures BINAIRES** (`rapport_final.md`) : l'analyse des
  causes d'erreur n'a pas été refaite sur les signatures retenues. Et les 74,5 % sont
  gonflés par construction : « classe multiple » se déclenche dès qu'un autre type arrive à
  5 % relatif du score gagnant, or les scores sont très resserrés — le critère attrape donc
  des erreurs ordinaires en plus des vraies ambiguïtés.

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

**Les signatures.** Elles gardent 20 hyperonymes et tous les types TRT et SST sémantiques,
et le terme lui-même n'est plus ajouté. **Les symboles ne valent pas 1** : chacun porte un
poids réel, normalisé par terme pour qu'un terme très documenté dans JDM ne pèse pas plus
qu'un autre dans la somme d'un nœud.

| trait | poids d'un symbole |
|---|---|
| `H:` hyperonymes | poids de la relation ÷ poids du plus fort hyperonyme retenu du terme |
| `TRT:` relations entrantes | `log(1 + effectif)` ÷ `log(1 + plus grand effectif retenu du terme)` |
| `SST:` types ontologiques | poids de l'annotation ÷ poids de la plus forte annotation du terme |

Le logarithme sur `TRT` n'est pas décoratif : les effectifs vont de 1 à plus de 700 000, et
sans lui un seul type écraserait tous les autres dans le cosinus. Une feuille est donc un
vecteur de poids réels ; un nœud fusionné en est la somme, et le cosinus se calcule sur les
vecteurs — la structure décrite plus haut ne change pas pour autant.

Ces réglages, `SIGNATURES_RETENUES` dans `config.py`, n'existent qu'en mémoire :
`predire.py` et l'évaluation finale les reconstruisent à chaque lancement depuis la
collecte. `data/signatures/` garde les signatures **initiales** — celles-là binaires, terme
sans préfixe — que lit encore `evaluation_finale.py`.

Ce que la pondération apporte, trait par trait, et avec quelle confiance :
[rapport_ponderation.md](reports/rapport_ponderation.md). En résumé, sur dix graines et en
test de Wilcoxon apparié : les trois traits ensemble gagnent **+0,028** de F1 (p = 0,002,
dix graines favorables sur dix), mais **pris séparément aucun ne vaut cela** — `H` seul
−0,001, `SST` seul +0,003 (un gain *nominal* : p = 0,049, qui ne survit pas au seuil de
Bonferroni de 0,0125 pour quatre comparaisons), et `TRT` seul **−0,016**, c'est-à-dire une
dégradation franche. La somme des
trois effets séparés est négative quand leur conjonction est positive : pondérer un seul
trait déséquilibre la norme du vecteur face aux deux autres restés à 1. Il n'y a donc pas
de version allégée de la pondération à en tirer.

## Historique des méthodes testées

| méthode | F1 macro | rapport |
|---|---|---|
| Apprentissage à seuil (fusion « les deux » à 0,50) + classification exhaustive | 0,597 (test) | [rapport_grasp.md](reports/rapport_grasp.md), [rapport_classification.md](reports/rapport_classification.md), [rapport_evaluation.md](reports/rapport_evaluation.md) |
| Union · arbre · descente (**écartée**) | 0,219 (test), 0,224 (validation croisée) | [methode_union_arbre_descente.md](reports/methode_union_arbre_descente.md), [rapport_arbres.md](reports/rapport_arbres.md) |
| Plus proche voisin sur les feuilles | 0,585 (test), 0,534 (validation croisée) | [rapport_arbres.md](reports/rapport_arbres.md) |
| Grille de 61 configurations (représentation × structure × classification) | de 0,224 à 0,784 (validation croisée) | [rapport_grille.md](reports/rapport_grille.md) |
| Somme · arbre · descente, signatures binaires `binaire · T0` | 0,753 (test), 0,786 (validation croisée, 3 graines) | [rapport_final.md](reports/rapport_final.md), [methode_somme_arbre_descente.md](reports/methode_somme_arbre_descente.md) |
| Variantes de signatures (hyperonymes, pondération, TRT/SST), 27 comparaisons | de 0,642 à 0,819 (validation croisée, 3 graines) | [rapport_signatures_variantes.md](reports/rapport_signatures_variantes.md) |
| Pondération trait par trait, Wilcoxon apparié | de 0,769 à 0,814 (validation croisée, 10 graines) | [rapport_ponderation.md](reports/rapport_ponderation.md) |
| **Somme · arbre · descente, signatures retenues `jdm · T2`** | **0,778** (test), 0,819 (validation croisée, 3 graines) | [rapport_final_signatures.md](reports/rapport_final_signatures.md) |

Les F1 de validation croisée ne se comparent qu'à **nombre de graines égal**, et seuls les
**écarts appariés** à l'intérieur d'une même étude ont un sens : 0,819 contre 0,786 sur les
mêmes 15 mesures donne +0,033, et c'est cet écart-là qui se lit, pas la différence de deux
moyennes prises dans deux tableaux différents.

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
   │  signatures.py       transforme en symboles textuels (binaires, versionnés)
   ▼
data/signatures/          1867 signatures, une par terme
   │                      les signatures RETENUES, elles, sont pondérées et reconstruites
   │                      en mémoire à chaque lancement (variantes_signatures.py)
   │  grasp.py            un arbre par type, fusion des deux nœuds les plus proches
   ▼
data/modeles/             arbres_somme.json (régénérable par grasp.py, non versionné)
   │  grille.py           compare les configurations en validation croisée, sans test
   │  variantes_signatures.py  compare les signatures en validation croisée, sans test
   │  ponderation_traits.py    la pondération trait par trait, 10 graines, sans test
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
| `ponderation_traits.py` | ce que chaque trait pondéré apporte seul : 10 graines, test de Wilcoxon apparié, ne lit pas le test. Éclairage, pas règle de choix |
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
py -3 src/rejouer.py --sans-test   # signatures, arbres, et les trois études en
                                   # validation croisée — ne lit pas le test
py -3 src/rejouer.py               # ajoute les DEUX évaluations qui lisent le test
```

Les sept étapes, dans l'ordre : `signatures.py`, `grasp.py`, `grille.py`,
`variantes_signatures.py`, `ponderation_traits.py`, puis les deux qui lisent le test —
`evaluation_finale.py` (signatures binaires) et `evaluation_signatures.py` (signatures
retenues). `--sans-test` saute exactement ces deux dernières.

La collecte n'est jamais rejouée : elle stocke les traits bruts, sans coupure, et aucun
réglage n'en dépend. Aucun appel réseau. **Compter une dizaine de minutes**, et non une :
`variantes_signatures.py` et `ponderation_traits.py` mettent leurs mesures en cache sous
une clé qui contient les paramètres de représentation, donc changer `H_TOP` ou
`TRT_POLITIQUE` les oblige à tout recalculer. C'est voulu — un rapport de validation
croisée périmé nuit plus qu'une attente.

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
