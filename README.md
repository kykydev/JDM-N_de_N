# JDM-N_de_N

Reproduction de **Guenoune & Lafourcade, IC@PFIA 2024**, « Extraction automatique de
règles pour la détermination de types de relations sémantiques dans les constructions
génitives en français ».

Article : [docs/papier.pdf](docs/papier.pdf) · Sujet du projet : [docs/projet.pdf](docs/projet.pdf)

**Le problème.** Dans « A de B », quelle relation sémantique lie A et B ? « vin de
France » porte une origine, « coque du bateau » une holonymie, « photo d'une famille »
une dépiction. L'article retient 15 types et cherche à les prédire automatiquement.

**L'idée.** On ne regarde pas la forme du syntagme mais ce que le réseau lexical
**JeuxDeMots** sait de A et de B. Si A est un *lieu géographique* et B un *pays*, la
relation est probablement une origine. Ce « ce que JDM sait d'un terme » s'appelle une
**signature**, et on apprend des **règles** en fusionnant les signatures d'exemples qui
se ressemblent.

Python 3, **bibliothèque standard uniquement** (`requests` pour les appels JDM). Aucun
modèle neuronal. Tous les scripts se lancent depuis la racine : `py -3 src/<script>.py`.

---

## Où en est-on

Le projet est complet : les sept étapes sont faites, les trois expériences de l'article
aussi, et le split test a été ouvert une seule fois avec des paramètres figés d'avance.

| | article | nous |
|---|---|---|
| H seuls (*baseline*) | 0,653 | 0,443 |
| H+SST | 0,691 | 0,471 |
| H+TRT | 0,767 | 0,514 |
| **H+TRT+SST** | **0,772** | **0,597** |

F1 macro sur 450 exemples de test, 30 par type. **L'ordre des quatre configurations
reproduit exactement celui de l'article**, et nos traits apportent même un peu plus que
les leurs (+0,154 de H à la configuration complète, contre +0,119). Mais nous sommes
0,175 en dessous, et **l'écart est déjà là avec les hyperonymes seuls** — donc ni GRASP,
ni la classification, ni le choix des traits n'en sont responsables.

**Trois différences avec l'article expliquent probablement le reste**, par ordre de
probabilité :

1. **Le corpus n'est pas le leur.** Le leur : généré par GPT-4-0613 puis validé à la
   main, ~10 % d'exemples mal classés ou dupliqués remplacés, plusieurs passes de
   diversification. Le nôtre suit le même protocole (80 par type, 50/30) mais ce ne sont
   pas les mêmes phrases. Le leur est publié : le récupérer transformerait « nos
   résultats sont inférieurs » en « on reproduit ou non ».
2. **La polysémie.** 58 % de nos erreurs en attribution exclusive, 84 % en présence —
   l'article annonce ~75 % pour lui-même. Nous avons collecté 5 222 raffinements de sens
   et **nous n'en utilisons aucun**.
3. **Nos signatures n'ont pas la même forme.** Contre leur exemple publié
   (« véhicule ») : H 20 contre ~10, TRT 28 contre 15, SST **2 contre 5**. Les tags SST
   manquants ne sont pas un défaut de collecte — 15 % de nos termes n'en ont aucun, ce
   qui renvoie au point 1.

## Le pipeline

```
data/corpus/raw/          15 fichiers, 80 syntagmes annotés chacun
   │
   │  corpus_check.py     découpe A / de / B, calcule det + définitude
   ▼
data/corpus/clean/        1200 lignes propres + termes.csv (1867 termes)
   │
   │  jdm_collect.py      interroge l'API JeuxDeMots — ~1 h 40, mis en cache
   ▼
data/collecte/            1 ligne JSON par terme : hyperonymes, relations, annotations
   │
   │  signatures.py       transforme en ensembles de symboles textuels
   ▼
data/signatures/          1867 signatures, une par terme
   │
   │  grasp.py            fusionne les règles qui se ressemblent — l'apprentissage
   ▼
data/modeles/             modele_final.json (+ le balayage, régénérable)
   │
   │  classify.py         choisit le seuil sur le calibrage
   │  evaluate.py         ouvre le test, mène les trois expériences
   ▼
data/resultats/           prédictions du test + matrice de confusion
   │
   │  predire.py          un syntagme quelconque -> sa relation, expliquée
   ▼
                          l'outil de démonstration
```

Chaque étape écrit un rapport dans `reports/`. **Les rapports sont le produit principal
du projet** : le code produit des chiffres, les rapports disent ce qu'ils signifient.

---

## Les trois idées à comprendre

### 1. Une signature

Ce que JDM sait d'un terme, réduit à un **ensemble plat d'étiquettes textuelles**. Pas de
vecteur, pas de plongement : des chaînes lisibles.

```
s(véhicule) = { véhicule,                       ← le terme lui-même
                H:transport, H:machine, …       ← ses hyperonymes (relation r_isa)
                TRT:r_lieu, TRT:r_agent, …      ← les types de relations qui pointent vers lui
                SST:PLACE, SST:THING-ARTEFACT }  ← ses types ontologiques standard
```

Trois traits, trois préfixes :

- **H** — les hyperonymes. « Bordeaux *est une* ville ». Les 20 mieux pondérés.
- **TRT** — les types de relations **entrantes**. Si beaucoup de choses pointent vers
  « Bordeaux » par une relation de lieu, c'est que Bordeaux est un lieu. C'est une façon
  indirecte de typer un terme, et elle complète les hyperonymes quand ceux-ci manquent.
- **SST** — les types ontologiques standard de JDM (`_INFO-SEM-*`), une taxonomie fixe.

Le terme lui-même figure dans sa signature : cela permet de capturer ses hyponymes.

### 2. Une règle, et la fusion (GRASP-it)

Une règle est un triplet `< sL, sR, rt >` : la signature attendue à gauche, celle
attendue à droite, et le type de relation.

**Les deux côtés ne sont jamais mélangés.** C'est ce qui fait que « vin de France » n'est
pas « France de vin ».

Au départ, chaque exemple d'entraînement donne une règle de poids 1. **Apprendre, c'est
fusionner** : si deux règles du même type se ressemblent assez, on les remplace par une
seule, dont les signatures sont l'union des deux et dont le poids est la somme.

```
< {vin, H:boisson},  {France, H:pays},  origine >    poids 1
< {café, H:boisson}, {Brésil, H:pays},  origine >    poids 1
                        ↓ fusion
< {vin, café, H:boisson}, {France, Brésil, H:pays}, origine >    poids 2
```

La règle fusionnée est plus générale : elle couvre deux exemples. Le processus est
**itératif** — une règle fusionnée peut refusionner — et s'arrête quand plus aucune paire
ne passe le seuil. Seules deux règles de **même type** peuvent fusionner.

Deux points que l'article laisse ouverts et qu'il a fallu trancher :

- **Le critère.** Faut-il que les *deux* similarités dépassent le seuil, ou leur
  moyenne ? → **les deux**, mesuré.
- **L'ordre.** A+B puis C ne donne pas la même règle que B+C puis A. → **glouton** (à
  chaque tour, on fusionne la meilleure paire), parce qu'il ne dépend pas de l'ordre de
  lecture du corpus. Le séquentiel donne des résultats à 4 % près.

### 3. Classer (formule 3 de l'article)

Pour un « A de B » inconnu, on calcule contre **chaque règle apprise, tous types
confondus** :

```
score = ½ × [ sim( s(A), sL ) + sim( s(B), sR ) ]
```

Le type de la règle la mieux classée est la prédiction. `sim` est un **cosinus sur
ensembles** : `|s₁ ∩ s₂| / √(|s₁| × |s₂|)`.

---

## Les diagnostics : ce qu'on a cherché, ce qu'on a trouvé

Quatre rapports d'enquête, distincts des rapports d'étape. Ils existent parce qu'à chaque
fois une décision était nécessaire et que rien ne la dictait.

### `rapport_sonde_jdm.md` — à quoi ressemblent les données ?

Avant de collecter 1867 termes, en sonder quelques-uns. A produit : la coupure à 20
hyperonymes, la liste des 15 types de relations non sémantiques à écarter (`r_aki`,
`r_wiki`, `r_translation`…), et le verdict sur les deux syntagmes à découpage ambigu
(« cacao de Côte d'Ivoire » → A = *cacao*, parce que « cacao de Côte » n'existe pas dans
JDM).

### `diagnostic_trt.md` + `diagnostic_trt_tour2.md` — faut-il filtrer TRT ?

**La question.** En gardant tous les types de relations entrantes, `TRT:r_isa` se
retrouve chez 98,4 % des termes. Deux termes sans aucun rapport partagent alors ~0,36 de
similarité, et **une paire au hasard sur dix dépasse déjà le seuil de fusion de 0,5**.

**Huit politiques mesurées**, puis un second tour. Ce qu'on a appris :

- Garder les N types les plus fournis **d'un terme** échoue, pour une raison
  instructive : les types les plus fournis d'un terme sont justement les types
  universels. Cette sélection garde le banal et jette le rare, donc le discriminant.
- Filtrer sur la fréquence **dans le corpus** marche mieux sur ce critère. La meilleure
  variante, **P8@C66**, ne garde un type que là où le terme en reçoit plus que le 66ᵉ
  centile de ce type sur tout le corpus — « Bordeaux » reçoit 990 relations de lieu,
  « saucisse » en reçoit 3, le centile les sépare.
- Résultat annexe : le filtre de fréquence retrouve seul **9 des 15** types que la sonde
  avait exclus à la main.

**Le verdict, mesuré après coup sur le F1 :**

| seuil de fusion | présence (article) | P8@C66 (le nôtre) |
|---|---|---|
| 0,30 | 0,357 | **0,525** |
| 0,45 | 0,503 | 0,523 |
| **0,50** (article) | **0,520** | 0,485 |
| 0,55 | 0,495 | 0,468 |

**Les deux politiques se valent** (0,520 contre 0,525 — un exemple d'écart). Deux tours
de diagnostic ont optimisé une métrique de substitution qui ne s'est pas traduite sur
l'objectif réel. Leçon de méthode : la séparation signal/bruit sur des paires tirées au
hasard n'est pas le F1.

Le tableau montre autre chose, en revanche : **la représentation et le seuil sont
couplés.** Des signatures plus courtes (P8@C66, médiane 36) donnent des similarités plus
faibles, donc un seuil optimal plus bas. Avec la représentation de l'article (médiane
49), l'optimum retombe exactement sur **le 0,50 de l'article**. Les deux se tiennent.

→ **Décision : lecture fidèle à l'article** (`TRT_POLITIQUE = "presence"`, le défaut).
P8@C66 reste accessible en changeant une ligne de `config.py`, pour nos essais ultérieurs.

### `rapport_classification.md` — critère, mesure, abstention

- **Critère de fusion.** « les deux » bat « moyenne » à tous les seuils, et pas seulement
  en niveau : le pouvoir discriminant de « moyenne » *décroît* quand on serre le seuil,
  parce qu'une paire qui colle très fort à gauche et pas du tout à droite passe la
  moyenne — et c'est la forme typique d'une paire de types différents.
- **Trois mesures de similarité comparées** : cosinus, couverture (`|s∩r| / |s|`, sans
  pénalité de taille) et Tversky (le point intermédiaire d'une famille à un paramètre).
  Le F1 décroît régulièrement du cosinus vers la couverture : **pénaliser une règle pour
  sa largeur n'est pas un défaut, c'est nécessaire.** Sans pénalité, 95 % des prédictions
  sont remportées par les 10 % de règles les plus grosses.
- **Abstention.** Inutile ici : le plus faible score gagnant est 0,184, donc tous les
  seuils d'abstention envisagés sont sous le plancher observé.

---

## Les modules

Dix fichiers, tous nécessaires. Les cinq premiers forment le chemin d'exécution de
l'outil de démonstration.

| module | prend | sort |
|---|---|---|
| `config.py` | — | toutes les constantes. N'importe aucun autre module. |
| `jdm_client.py` | — | client HTTP JDM : cache disque, reprises, politesse |
| `corpus_check.py` | `corpus/raw/` | `corpus/clean/`, `termes.csv`, `rapport_corpus.md` |
| `jdm_collect.py` | `termes.csv` | `termes_jdm.jsonl` (1867 termes) |
| `signatures.py` | collecte + corpus | `signatures_termes.json`, `rapport_signatures.md` |
| `grasp.py` | signatures + corpus | modèles fusionnés, split de calibrage, `rapport_grasp.md` |
| `classify.py` | modèles + calibrage | `modele_final.json`, `rapport_classification.md` |
| `evaluate.py` | modèle final + test | `rapport_evaluation.md`, prédictions, matrice |
| `predire.py` | un syntagme quelconque | la prédiction expliquée, à l'écran ou en CSV |
| `rejouer.py` | — | relance la chaîne dans l'ordre après un changement de `config.py` |

Ordre d'exécution : `corpus_check` → `jdm_collect` → `signatures` → `grasp` →
`classify` → `evaluate`. `predire.py` s'utilise à tout moment une fois
`modele_final.json` produit.

**`grasp.py`** découpe aussi le train : sur les 50 exemples par type, **40 pour
l'apprentissage et 10 pour le calibrage** (`split_calibrage.csv`), tirage déterministe.
Il balaie 2 stratégies × 6 seuils = 12 modèles, avec une instrumentation complète —
règles avant/après, nombre de tours, distribution des poids, et une **détection
d'emballement** (une règle qui absorbe plus de la moitié des exemples de son type, ou
dont la signature dépasse le triple de la taille initiale médiane).

**`classify.py`** applique la formule 3, trace pour chaque prédiction **quelle règle a
gagné**, compare les trois mesures de similarité, mesure l'abstention, puis réapprend le
modèle final sur les 50 exemples complets au seuil retenu.

**`evaluate.py`** ouvre le split test et mène les trois expériences de l'article. Chaque
configuration des Expériences 1 et 2 est un pipeline complet : signatures filtrées,
règles **réapprises**, puis classification.

### Scripts retirés

Quatre scripts ponctuels ont été supprimés une fois leur résultat acquis :
`jdm_payload_bench.py` (optimisation du format d'appel, résultat inscrit dans
`config.PARAMS_RELATIONS_ENTRANTES`), `jdm_probe.py` (la sonde, qui a fixé le top 20 et
la liste des types non sémantiques), `corpus_variants.py` (variantes de déterminant,
finalement inutilisées — l'Expérience 2 lit les colonnes `det` et `definitude` du corpus
propre) et `diagnostic_trt.py` (les deux tours de diagnostic TRT). **Leurs rapports
restent dans `reports/`** : ce sont eux qui justifient les valeurs de `config.py`. Les
scripts ne sont plus rejouables.

---

## L'outil de démonstration

```
py -3 src/predire.py "saucisse de Toulouse"
py -3 src/predire.py                      # boucle interactive
py -3 src/predire.py --fichier liste.txt  # un syntagme par ligne, sortie CSV
```

Options : `--top N` (types affichés), `--detail` (signatures complètes), `--sans-api`
(hors ligne, signatures déjà connues seulement).

Il découpe le syntagme, cherche chaque terme dans les signatures connues puis, à défaut,
dans JDM — en mettant le résultat dans un cache à part, `data/cache/signatures_ad_hoc.json`,
qui ne touche jamais aux données du projet. Il affiche le classement des types, la règle
gagnante et les exemples dont elle provient, et les **symboles décisifs** : l'intersection
entre la signature du terme et celle de la règle, les plus rares d'abord, parce qu'un
symbole rare explique mieux une décision qu'un symbole que tout le monde porte.

Trois comportements à connaître pour une démonstration :

- Un écart de moins de 5 % avec le 2ᵉ type affiche **« décision serrée »** — c'est le
  critère d'évaluation indulgente de l'article (§4.3).
- Le déterminant est **affiché mais non utilisé** : l'Expérience 2 a montré que le trait
  de définitude dégradait le F1 chez nous. « photo de famille » et « photo d'une
  famille » reçoivent donc la même prédiction, et l'outil le dit.
- Si aucune règle ne partage le moindre symbole, il refuse de répondre au lieu
  d'annoncer un type à score nul.

---

## Résultats

Réglage figé : TRT « presence », critère « les deux », stratégie gloutonne, seuil 0,50,
cosinus, pas d'abstention. **Modèle final : 439 règles** apprises sur les 750 exemples
d'entraînement.

| jeu | F1 macro | exactitude |
|---|---|---|
| entraînement (vu) | 0,973 | 97,3 % |
| calibrage (a servi à choisir le seuil) | 0,520 | 52,0 % |
| **test (jamais vu)** | **0,597** | **60,0 %** |

Très inégal selon les types : `r_social_tie` 0,79 et `r_has_property-1` 0,76 — ce dernier
est le pire type de l'article — contre `r_holo` 0,35 et `r_topic` 0,41. En évaluation
indulgente, 0,684.

**L'écart entraînement/test ne veut pas dire surapprentissage.** 267 des 439 règles sont
des orphelines, c'est-à-dire des exemples d'entraînement recopiés tels quels : leur
présenter un exemple d'entraînement le fait retrouver sa propre règle à similarité 1. Le
terme juste est **sous-généralisation** — la fusion est censée abstraire et elle
n'abstrait pas assez. Sur le test, 65 % des prédictions sont gagnées par une orpheline.

**Les trois expériences de l'article**, toutes menées avec réapprentissage complet :

- *Expérience 1* (traits) : tableau en tête de ce README. Ordre reproduit, niveau
  inférieur.
- *Expérience 2* (définitude) : **résultat négatif**. Le trait nous fait perdre 0,027 là
  où l'article gagne 0,023. La mesure ajoutée montre que ce n'est pas un doublon avec les
  annotations `DET`/`NODET` de JDM.
- *Expérience 3* (élagage) : l'élagage est chez nous **2,3× plus rapide et légèrement
  meilleur** (0,597 contre 0,589). L'article y perdait 0,028.

**Un défaut structurel mis au jour par l'outil de démonstration.** La moyenne
arithmétique de la formule 3 laisse un côté parfait porter un côté nul :
« portrait de Van Gogh » obtient `r_depict` avec ½(1,000 + 0,000), alors que l'article le
classe en Auteur/créateur. Mesuré sur les 450 exemples de test, les prédictions
déséquilibrées (|gauche − droite| > 0,3) sont justes à 44 % contre 66 % pour les
équilibrées. Nous avions corrigé exactement ce défaut pour le critère de *fusion* à
l'étape 5, mais gardé la moyenne pour la *classification*, puisque c'est la formule 3.

---

## Changer un paramètre et tout réévaluer

Tous les réglages sont dans `config.py`, aucun n'est en dur ailleurs. Passer de 20 à 10
hyperonymes, par exemple :

```python
H_TOP = 10        # config.py, une seule ligne
```

puis :

```
py -3 src/rejouer.py
```

Le lanceur enchaîne `signatures.py` → `grasp.py` → `classify.py` → `evaluate.py` dans
cet ordre, affiche les paramètres lus, chronomètre chaque étape et compare les scores
d'avant et d'après. **Environ 30 secondes en tout.**

**La collecte n'est jamais rejouée.** `data/collecte/termes_jdm.jsonl` stocke les traits
bruts — tous les hyperonymes, médiane 26 par terme, jusqu'à 396 — sans aucune coupure.
Les seuils sont appliqués plus tard, dans `signatures.py`. Changer `H_TOP`, la politique
TRT ou les seuils de fusion ne demande donc **aucun appel réseau**. C'était le principe
de l'étape 2, et c'est ce qui rend l'expérience faisable en direct.

L'ordre compte : relancer `evaluate.py` sans avoir relancé `grasp.py` évaluerait des
signatures neuves avec un modèle périmé, sans que rien ne le signale. C'est la raison
d'être du lanceur. `--sans-test` s'arrête avant `evaluate.py`, pour travailler sans
rouvrir le test.

### Le piège, et il est important

Après un changement de paramètre, **deux chiffres** sortent, et ils n'ont pas le même
statut :

- le **F1 de calibrage** (150 exemples) a le droit de guider un choix ;
- le **F1 de test** (450 exemples) n'estime la généralisation **que s'il n'a servi à
  rien décider**. Choisir un paramètre au vu du test, c'est régler sur le test, et le
  chiffre ne veut plus rien dire.

Le lanceur affiche les deux côte à côte et rappelle cette distinction à chaque
exécution.

### Le cas H_TOP = 10, déjà mesuré

| | H_TOP = 20 (référence) | H_TOP = 10 |
|---|---|---|
| F1 **calibrage** | 0,520 | **0,543** |
| F1 **test** | **0,597** | 0,520 |
| règles du modèle final | 439 | 294 |

**Le calibrage dit que 10 est meilleur, le test dit le contraire.** C'est l'illustration
exacte du piège ci-dessus : sur 150 exemples, un écart de 0,023 tient à trois exemples.
Suivre le calibrage aurait fait perdre 0,077 en généralisation.

Deux leçons à en tirer, et elles sont défendables devant un jury :

1. Notre jeu de calibrage est trop petit pour arbitrer des écarts de cette taille. Une
   validation croisée sur le train aurait été plus solide qu'une coupe 40/10.
2. Cela ne remet pas en cause `H_TOP = 20`, qui vient d'une mesure indépendante — la
   décroissance des poids des hyperonymes observée par la sonde, avant toute
   classification. Un réglage choisi sur une propriété des données résiste mieux qu'un
   réglage choisi sur un score bruité.

Les autres paramètres se changent de la même façon : `TRT_POLITIQUE = "centile"` rebascule
sur notre P8@C66, `SST_EXCLURE_MORPHO = True` retire les annotations morphologiques,
`GRASP_SEUILS` modifie le balayage, `MESURE_FIGEE` passe à `"tversky"` ou `"couverture"`.

---

## Discipline expérimentale

- **Le split test n'a été ouvert qu'une fois, à l'étape 6**, après affichage des
  paramètres figés. Aucun réglage n'a été touché ensuite. Vérifié programmatiquement :
  aucun de ses 450 syntagmes n'apparaît dans une sortie antérieure, ni parmi les 750
  exemples qui ont servi aux règles.
- Le seuil a été choisi sur le **calibrage**, qui ne peut donc pas estimer la
  performance : le 0,520 est une valeur de sélection. **Le 0,597 du test est le seul
  chiffre de généralisation du projet**, et il ne doit pas être réutilisé pour régler
  quoi que ce soit.
- Tout est **déterministe** : graines fixées, tris totaux, sorties identiques sous
  plusieurs `PYTHONHASHSEED`.
- `data/cache/jdm/` (934 Mo, ignoré par git) est **irremplaçable** : 1 h 40 d'appels API. La fonction de
  nommage des fichiers de cache ne doit jamais changer.

---

## Pistes, si le projet reprend

Par ordre de rendement attendu :

1. **Récupérer le corpus de l'article**, publié par les auteurs. C'est la seule action
   qui transforme une comparaison entre deux systèmes sur deux jeux de données en une
   vraie reproduction.
2. **Désambiguïser par les raffinements.** 5 222 raffinements déjà collectés, jamais
   utilisés, pour la cause n° 1 de nos erreurs comme de celles de l'article.
3. **Remplacer la moyenne de la formule 3** par un minimum ou une moyenne géométrique :
   les deux annulent le score quand un côté est nul. À mesurer sur le calibrage, pas sur
   le test, et en sachant que c'est une sortie de la fidélité à l'article.

---

## Conventions

- Noms de fonctions et de variables **en français**, une docstring d'une ligne chacune.
- Fonctions courtes, une responsabilité. **Pas de classes, pas de dataclasses.**
  Dictionnaires, listes et ensembles.
- Erreurs attrapées par type précis, **jamais d'`except` nu**.
- Les chemins d'URL de l'API JDM restent **en anglais** : ce sont des littéraux du
  protocole, pas des noms à traduire.
- Rapports en Markdown, chiffres à la française (virgule décimale).
