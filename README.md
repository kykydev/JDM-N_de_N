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

## Résultats

Configuration retenue — **somme · arbre · descente**, signatures `H 20 · jdm · T2` — sur
les **450 exemples de test**, 30 par type, lus une seule fois.

### Par type

| type | prédits | P (%) | R (%) | F1 | F1 article | écart |
|---|---|---|---|---|---|---|
| `r_has_property-1` | 29 | 100,0 | 96,7 | **0,98** | 0,59 | +0,39 |
| `r_lieu` | 26 | 100,0 | 86,7 | **0,93** | 0,76 | +0,17 |
| `r_lieu>origine` | 31 | 90,3 | 93,3 | **0,92** | 0,92 | −0,00 |
| `r_social_tie` | 36 | 80,6 | 96,7 | **0,88** | 0,91 | −0,03 |
| `r_objet>matiere` | 23 | 100,0 | 76,7 | **0,87** | 0,80 | +0,07 |
| `r_processus>instr-1` | 31 | 80,6 | 83,3 | **0,82** | 0,78 | +0,04 |
| `r_processus_patient` | 38 | 71,1 | 90,0 | **0,79** | 0,75 | +0,04 |
| `r_has_causatif` | 26 | 84,6 | 73,3 | **0,79** | 0,69 | +0,10 |
| `r_quantificateur` | 34 | 73,5 | 83,3 | **0,78** | 0,81 | −0,03 |
| `r_own-1` | 37 | 64,9 | 80,0 | **0,72** | 0,64 | +0,08 |
| `r_topic` | 29 | 72,4 | 70,0 | **0,71** | 0,76 | −0,05 |
| `r_processus_agent` | 27 | 74,1 | 66,7 | **0,70** | 0,81 | −0,11 |
| `r_holo` | 27 | 70,4 | 63,3 | **0,67** | 0,82 | −0,15 |
| `r_product_of` | 19 | 73,7 | 46,7 | **0,57** | 0,74 | −0,17 |
| `r_depict` | 37 | 48,6 | 60,0 | **0,54** | 0,80 | −0,26 |
| **macro** |  | **79,0** | **77,8** | **0,778** | 0,772 | +0,006 |

Source : [data/resultats/matrice_confusion_finale_jdm.csv](data/resultats/matrice_confusion_finale_jdm.csv) ;
la colonne « F1 article » vient du Tableau 3 de l'article. Détail et analyse des erreurs
dans [rapport_final_signatures.md](reports/rapport_final_signatures.md).

### Matrice de confusion

**1** `r_depict` · **2** `r_has_causatif` · **3** `r_has_property-1` · **4** `r_holo` · **5** `r_lieu` · **6** `r_lieu>origine` · **7** `r_objet>matiere` · **8** `r_own-1` · **9** `r_processus>instr-1` · **10** `r_processus_agent` · **11** `r_processus_patient` · **12** `r_product_of` · **13** `r_quantificateur` · **14** `r_social_tie` · **15** `r_topic`

| attendu \ prédit | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **1.** `r_depict` | **18** | · | · | 2 | · | · | · | 2 | 2 | 1 | 4 | · | · | 1 | · |
| **2.** `r_has_causatif` | 3 | **22** | · | · | · | · | · | · | · | · | 2 | · | 3 | · | · |
| **3.** `r_has_property-1` | · | · | **29** | · | · | · | · | · | · | · | · | · | · | 1 | · |
| **4.** `r_holo` | 7 | · | · | **19** | · | · | · | · | · | · | · | · | 1 | · | 3 |
| **5.** `r_lieu` | 2 | · | · | · | **26** | 1 | · | 1 | · | · | · | · | · | · | · |
| **6.** `r_lieu>origine` | · | · | · | · | · | **28** | · | 1 | · | · | · | · | · | 1 | · |
| **7.** `r_objet>matiere` | 1 | · | · | 2 | · | · | **23** | · | · | · | 1 | 1 | 2 | · | · |
| **8.** `r_own-1` | 1 | · | · | · | · | · | · | **24** | · | · | · | 3 | · | 2 | · |
| **9.** `r_processus>instr-1` | · | · | · | 2 | · | · | · | · | **25** | · | · | · | 1 | · | 2 |
| **10.** `r_processus_agent` | · | 4 | · | · | · | · | · | · | · | **20** | 3 | · | 1 | 1 | 1 |
| **11.** `r_processus_patient` | · | · | · | · | · | · | · | · | · | 3 | **27** | · | · | · | · |
| **12.** `r_product_of` | 4 | · | · | 1 | · | 2 | · | 6 | · | 2 | · | **14** | · | · | 1 |
| **13.** `r_quantificateur` | · | · | · | 1 | · | · | · | 1 | · | 1 | · | 1 | **25** | · | 1 |
| **14.** `r_social_tie` | · | · | · | · | · | · | · | 1 | · | · | · | · | · | **29** | · |
| **15.** `r_topic` | 1 | · | · | · | · | · | · | 1 | 4 | · | 1 | · | 1 | 1 | **21** |

Source : [data/resultats/matrice_confusion_finale_jdm.csv](data/resultats/matrice_confusion_finale_jdm.csv).
**Chaque ligne totalise 30 exemples** : la diagonale en gras est le nombre de prédictions
justes du type, et les autres cellules de la ligne disent vers quel type ses erreurs sont
parties. Les zéros sont notés « · ».

**Confusions les plus fréquentes** : `r_holo` → `r_depict` (7), `r_product_of` → `r_own-1` (6), `r_topic` → `r_processus>instr-1` (4), `r_product_of` → `r_depict` (4), `r_processus_agent` → `r_has_causatif` (4), `r_depict` → `r_processus_patient` (4).

**La limite la plus visible** : `r_depict` est un **aimant** — il reçoit 37 prédictions
pour 30 exemples attendus, soit 48,6 % de précision. C'est aussi le type sur lequel
l'article nous dépasse le plus.

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
| Apprentissage à seuil (fusion « les deux » à 0,50) + classification exhaustive | 0,597 (test) | [archive/rapport_grasp.md](reports/archive/rapport_grasp.md), [archive/rapport_classification.md](reports/archive/rapport_classification.md), [archive/rapport_evaluation.md](reports/archive/rapport_evaluation.md) |
| Union · arbre · descente (**écartée**) | 0,219 (test), 0,224 (validation croisée) | [methode_union_arbre_descente.md](reports/methode_union_arbre_descente.md), [archive/rapport_arbres.md](reports/archive/rapport_arbres.md) |
| Plus proche voisin sur les feuilles | 0,585 (test), 0,534 (validation croisée) | [archive/rapport_arbres.md](reports/archive/rapport_arbres.md) |
| Grille de 61 configurations (représentation × structure × classification) | de 0,224 à 0,784 (validation croisée) | [rapport_grille.md](reports/rapport_grille.md) |
| Somme · arbre · descente, signatures binaires `binaire · T0` | 0,753 (test), 0,786 (validation croisée, 3 graines) | [rapport_final.md](reports/rapport_final.md), [methode_somme_arbre_descente.md](reports/methode_somme_arbre_descente.md), [rapport_arbres_somme.md](reports/rapport_arbres_somme.md) |
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
   │                      -> reports/rapport_arbres_somme.md décrit ces quinze arbres
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

## Les rapports, dans quel ordre les lire

### À lire

Cinq rapports suffisent à comprendre ce que fait le projet et ce qu'il vaut, dans cet
ordre : le résultat, puis sa confiance, puis les choix qui y ont mené, puis la mécanique.

| rapport | ce qu'on y trouve |
|---|---|
| [rapport_final_signatures.md](reports/rapport_final_signatures.md) | **Le résultat du projet** : F1 0,778 sur les 450 exemples de test, F1 par type en regard de l'article, matrice de confusion, et les 39 exemples corrigés contre 29 cassés par rapport aux signatures binaires. |
| [rapport_ponderation.md](reports/rapport_ponderation.md) | Ce que vaut la pondération, trait par trait, sur dix graines et en test de Wilcoxon apparié : les trois traits ensemble gagnent +0,028, aucun ne gagne seul, et `TRT` seul dégrade. |
| [rapport_signatures_variantes.md](reports/rapport_signatures_variantes.md) | **Le choix de `jdm · T2`** : 27 configurations de signatures en validation croisée (hyperonymes, pondération, TRT/SST, symbole du terme), différences appariées, et le §3.1 sur la pondération trait par trait. C'est ce rapport que `rapport_ponderation.md` prolonge. |
| [rapport_grille.md](reports/rapport_grille.md) | Le choix de la méthode : 61 configurations (représentation × structure × classification) comparées en validation croisée, sans lire le test. C'est là que « somme · arbre · descente » est retenu. |
| [methode_somme_arbre_descente.md](reports/methode_somme_arbre_descente.md) | La méthode retenue expliquée à la main, avec ses chiffres réels : les arbres sont des peignes, et descendre ne retire que quelques feuilles du profil du type. |
| [methode_union_arbre_descente.md](reports/methode_union_arbre_descente.md) | La méthode écartée, et **pourquoi** : en union le cosinus pénalise un nœud pour sa seule taille, la descente part vers le plus petit enfant, et le F1 tombe à 0,219. |

### Historique

Les étapes antérieures, encore régénérables et toujours justes, mais qu'on ne lit que pour
vérifier un chiffre ou comprendre une décision de construction.

| étape | rapport | ce qu'on y trouve |
|---|---|---|
| corpus | [rapport_corpus.md](reports/rapport_corpus.md) | Contrôle des 15 fichiers du corpus : comptes, découpages A / de / B, déterminant et définitude, doublons signalés. |
| corpus | [remplacements_proposes.csv](reports/remplacements_proposes.csv) | Les deux termes absents de JDM (« cacao de Côte », « diamants d'Afrique ») : des découpages concurrents que cette absence écarte, sans remplacement à faire. |
| collecte | [rapport_sonde_jdm.md](reports/rapport_sonde_jdm.md) | La sonde de 30 termes qui a tout cadré avant la collecte : endpoints de l'API, coupure à 20 hyperonymes, les 15 types TRT non sémantiques à écarter. |
| collecte | [rapport_collecte.md](reports/rapport_collecte.md) | La collecte des 1867 termes : volumes, latences, erreurs, et l'optimisation du payload de `/relations/to` (−82 % de volume à résultat identique). |
| signatures | [rapport_signatures.md](reports/rapport_signatures.md) | Les signatures initiales, **binaires** : vocabulaire, tailles, symboles les plus fréquents, signatures quasi vides. |
| arbres | [rapport_arbres_somme.md](reports/rapport_arbres_somme.md) | Les quinze arbres de la configuration retenue : construction, profondeurs, poids, et statistiques de la descente. |
| évaluation | [rapport_final.md](reports/rapport_final.md) | La même évaluation de test avec les signatures **binaires** : F1 0,753, et l'analyse des 110 erreurs (polysémie, classe multiple). Dépassé par `rapport_final_signatures.md`, mais c'est lui qui porte l'analyse des causes d'erreur. |
| diagnostics TRT | [diagnostic_trt.md](reports/diagnostic_trt.md) | Huit politiques de sélection du trait TRT mesurées : garder les types les plus fournis d'un terme échoue, filtrer sur la fréquence dans le corpus marche mieux. |
| diagnostics TRT | [diagnostic_trt_tour2.md](reports/diagnostic_trt_tour2.md) | Le second tour : seuil, formulation, critère de fusion. Conclusion de méthode — les deux politiques se valent sur le F1, et deux tours avaient optimisé une métrique de substitution. |

### Archive

`reports/archive/` garde les quatre rapports qu'**aucun script ne régénère plus**, parce
que le code qui les écrivait a été retiré au commit `8bd078a`. Ils restent la source des
F1 de 0,597 et 0,585 que le tableau d'historique met en regard.

| rapport | ce qu'on y trouve |
|---|---|
| [archive/rapport_grasp.md](reports/archive/rapport_grasp.md) | L'apprentissage par fusion à seuil (GRASP-it) : douze combinaisons, deux ordonnancements × six seuils, détection d'emballement. |
| [archive/rapport_classification.md](reports/archive/rapport_classification.md) | Le choix du seuil de fusion et de la mesure de similarité : cosinus contre couverture contre Tversky, et la question de l'abstention. |
| [archive/rapport_evaluation.md](reports/archive/rapport_evaluation.md) | L'évaluation de la méthode à seuil sur le test (F1 0,597) et les trois expériences de l'article. Les détecteurs de causes d'erreur viennent de là. |
| [archive/rapport_arbres.md](reports/archive/rapport_arbres.md) | Les arbres en **union** et le plus proche voisin sur les feuilles (F1 0,585) : le biais de taille du cosinus sur ensembles, vu de l'intérieur. |

### Deux annexes, qui ne se lisent pas seules

`reports/rapport_grille_courbes.svg` est la figure de `rapport_grille.md`, régénérée avec
lui par `grille.py`. `reports/phase1_payload.json` n'est pas un rapport mais la **donnée**
que `jdm_collect.py` relit pour écrire le §1 de `rapport_collecte.md` : sans ce fichier, ce
§1 se réduit à « _Mesures absentes_ », et le reconstituer demanderait de relancer la
collecte. Ne pas le supprimer.

## Les modules

| module | rôle |
|---|---|
| `config.py` | toutes les constantes, dont la configuration retenue. N'importe aucun autre module. |
| `jdm_client.py` | client HTTP JDM : cache disque, reprises, politesse |
| `corpus_check.py` | contrôle du corpus, découpage A / B |
| `jdm_collect.py` | collecte des traits bruts de 1867 termes |
| `signatures.py` | signatures des termes, similarité cosinus |
| `grasp.py` | construction des arbres, en union ou en somme |
| `classify.py` | score (formule 3), descente, métriques. Aucun code mort : ses 15 fonctions sont toutes appelées (celui de la phase union a été retiré, il reste dans le commit `8bd078a`) |
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
