# Variantes de construction des signatures

Étude en validation croisée sur l'entraînement seul, méthode figée (somme · arbre · descente). **Le test n'est pas lu.** À montrer avant toute lecture du test.

## 0. Protocole

- **5 plis stratifiés par type**, répétés avec les graines 42, 43, 44 : 15 mesures de F1 par configuration, toutes évaluées sur les mêmes plis.
- **Différences appariées** pli par pli à la référence de chaque étape. Une configuration ne bat la référence que si la différence moyenne dépasse son écart-type.
- **Statistiques tirées des données** (fréquences documentaires, centiles TRT, types trop fréquents) : calculées sur les termes d'entraînement du pli seulement, jamais sur les exemples de validation.
- **Pondération** : un côté est un vecteur de poids réels, un nœud fusionné la somme de ceux de ses enfants, le cosinus se calcule sur les vecteurs. L'exemple à classer utilise les mêmes poids. Un symbole absent des statistiques d'idf reçoit le poids d'un symbole de df = 1 ; un poids nul (symbole présent chez tous les termes) retire le symbole.
- **jdm** : H = poids de l'hyperonyme / poids maximal des H retenus du terme ; SST = poids / poids maximal des SST retenus ; TRT = log(1 + effectif) / log(1 + effectif maximal des types retenus) ; le terme lui-même vaut 1.
- **Règle de choix** : la plus simple parmi les configurations qui ne se distinguent pas de la meilleure (différence appariée moyenne ≤ son écart-type). Complexité : moins d'hyperonymes < plus, puis binaire < idf < jdm < jdm×idf ; pour le terme, absent < sans préfixe < H: ; pour TRT et SST, réglage actuel < aucun < sélections plus élaborées ; sans filtre < avec filtre.
- **Limite** : les 15 mesures ne sont pas indépendantes (les trois répétitions rebattent les mêmes 750 exemples), donc l'écart-type des différences sous-estime l'incertitude réelle. Et choisir la meilleure de plusieurs dizaines de configurations sur ces mêmes mesures est optimiste.
- **Contrôle** : la référence `H 20 · binaire · T0 · TRT tous · SST toutes` reconstruite ici donne, sur la seule graine 42, un F1 moyen de 0,784 (`rapport_grille.md` : 0,784) ; ses signatures sont identiques à `data/signatures/` pour 1244 termes sur 1244.

## 1. Étape 0 — le symbole du terme

Les hyperonymes portent le préfixe `H:`, le terme lui-même est ajouté sans préfixe : la signature de « chêne » contient `H:arbre`, celle d'« arbre » contient `arbre`, et ils ne s'intersectent jamais. Le but du papier (section 3), capturer les hyponymes, n'est alors pas atteint.

**Diagnostic** sur les 1244 termes d'entraînement : le symbole non préfixé d'un terme apparaît **0 fois** dans la signature d'un autre terme. C'est bien « jamais », comme attendu.
Sous la forme `H:<terme>`, en revanche, le symbole de 338 termes (27 %) figure parmi les hyperonymes d'au moins un autre terme, 1181 occurrences en tout, jusqu'à 57 pour « métier ». T1 rend donc l'intersection possible.

Référence de l'étape : `H 20 · binaire · T0 · TRT tous · SST toutes`. « bat » = différence moyenne supérieure à son écart-type, sur 15 différences appariées.

| traitement | F1 moyen ± é.-t. | différence à T0 ± é.-t. | taille médiane | durée |
|---|---|---|---|---|
| T0 — sans préfixe (actuel) | 0,786 ± 0,041 | — | 52 | 16 s |
| T1 — `H:<terme>` | 0,786 ± 0,041 | +0,000 ± 0,004 | 52 | 15 s |
| T2 — absent | 0,789 ± 0,046 ← **retenue** | +0,003 ± 0,011 | 51 | 15 s |

**Retenue : T2.** Meilleur F1 moyen : T2. 3 configurations ne se distinguent pas de la meilleure (différence appariée moyenne ≤ son écart-type) ; on retient la plus simple d'entre elles.

## 2. Nombre d'hyperonymes par terme

Sur les 1244 termes d'entraînement présents dans JDM (0 absents, réduits à eux-mêmes).

| hyperonymes | min | Q1 | médiane | Q3 | max |
|---|---|---|---|---|---|
| bruts | 0 | 12,0 | 29,0 | 66,0 | 396 |
| de poids > 0 | 0 | 12,0 | 29,0 | 66,0 | 396 |
| après fusion des doublons | 0 | 12,0 | 29,0 | 65,0 | 378 |

Nombre de termes qui ont plus de N hyperonymes (après fusion des doublons), c'est-à-dire ceux qu'une coupure à N tronque : N = 20 : **745** (60 %), N = 50 : **421** (34 %), N = 100 : **108** (9 %), N = 200 : **4** (0 %). « tous » ne diffère de « 200 » que pour 4 termes : au-delà de ce nombre, les deux coïncident.

## 3. Étape 1 — hyperonymes × pondération

TRT et SST restent aux réglages actuels ; le terme est traité selon l'étape 0 (T2). 20 configurations.

Référence de l'étape : `H 20 · binaire · T2 · TRT tous · SST toutes`. « bat » = différence moyenne supérieure à son écart-type, sur 15 différences appariées.

| H | pondération | F1 moyen ± é.-t. | différence ± é.-t. | taille médiane | durée |
|---|---|---|---|---|---|
| 20 | binaire | 0,789 ± 0,046 | — | 51 | 15 s |
| 20 | idf | 0,682 ± 0,054 | −0,106 ± 0,051 | 51 | 20 s |
| 20 | jdm | 0,819 ± 0,031 ← **retenue** | +0,030 ± 0,028 **bat** | 51 | 24 s |
| 20 | jdm×idf | 0,660 ± 0,062 | −0,129 ± 0,047 | 51 | 26 s |
| 50 | binaire | 0,725 ± 0,047 | −0,063 ± 0,023 | 67 | 26 s |
| 50 | idf | 0,663 ± 0,040 | −0,125 ± 0,044 | 67 | 28 s |
| 50 | jdm | 0,794 ± 0,030 | +0,006 ± 0,025 | 67 | 26 s |
| 50 | jdm×idf | 0,659 ± 0,062 | −0,129 ± 0,057 | 67 | 30 s |
| 100 | binaire | 0,683 ± 0,045 | −0,106 ± 0,017 | 68 | 29 s |
| 100 | idf | 0,666 ± 0,045 | −0,123 ± 0,043 | 68 | 33 s |
| 100 | jdm | 0,770 ± 0,040 | −0,018 ± 0,024 | 68 | 31 s |
| 100 | jdm×idf | 0,661 ± 0,054 | −0,128 ± 0,049 | 68 | 47 s |
| 200 | binaire | 0,676 ± 0,036 | −0,113 ± 0,019 | 68 | 32 s |
| 200 | idf | 0,667 ± 0,041 | −0,121 ± 0,049 | 68 | 32 s |
| 200 | jdm | 0,764 ± 0,041 | −0,025 ± 0,027 | 68 | 32 s |
| 200 | jdm×idf | 0,660 ± 0,054 | −0,128 ± 0,052 | 68 | 33 s |
| tous | binaire | 0,676 ± 0,038 | −0,112 ± 0,020 | 68 | 29 s |
| tous | idf | 0,667 ± 0,037 | −0,121 ± 0,049 | 68 | 32 s |
| tous | jdm | 0,764 ± 0,042 | −0,025 ± 0,027 | 68 | 31 s |
| tous | jdm×idf | 0,661 ± 0,055 | −0,128 ± 0,052 | 68 | 32 s |

**Retenue : H 20, jdm.** Meilleur F1 moyen : H 20, jdm. Aucune autre configuration ne reste à un écart-type de la meilleure : elle est retenue sur son seul score.

## 4. Étape 2 — sélection TRT et SST

Un paramètre à la fois, autour du couple (H, pondération) retenu à l'étape 1. Les deux diagnostics antérieurs avaient été faits en union : ici on mesure sans les supposer.

Référence de l'étape : `H 20 · jdm · T2 · TRT tous · SST toutes`. « bat » = différence moyenne supérieure à son écart-type, sur 15 différences appariées.

| paramètre changé | F1 moyen ± é.-t. | différence ± é.-t. | taille médiane | durée |
|---|---|---|---|---|
| réglage actuel | 0,819 ± 0,031 ← **retenue** | — | 51 | 24 s |
| TRT aucun | 0,642 ± 0,037 | −0,177 ± 0,032 | 22 | 14 s |
| TRT sans_frequents | 0,817 ± 0,028 | −0,002 ± 0,015 | 40 | 18 s |
| TRT centile | 0,813 ± 0,033 | −0,006 ± 0,017 | 37 | 21 s |
| SST aucune | 0,808 ± 0,040 | −0,011 ± 0,021 | 48 | 21 s |
| SST sans_morpho | 0,818 ± 0,032 | −0,000 ± 0,003 | 51 | 24 s |

**Retenue : TRT tous, SST toutes.** Meilleur F1 moyen : TRT tous, SST toutes. 5 configurations ne se distinguent pas de la meilleure (différence appariée moyenne ≤ son écart-type) ; on retient la plus simple d'entre elles.

## 5. Étape 3 — seuil de fréquence minimale

Un symbole porté par un seul terme d'entraînement reçoit le poids idf maximal mais ne peut jamais généraliser à un autre terme. On compare, au meilleur réglage idf, aucun seuil et df ≥ 2.

**La configuration retenue à l'étape 2 n'est pas pondérée par idf** : le test porte donc sur la meilleure configuration idf de l'étape 1 (`H 20 · idf · T2 · TRT tous · SST toutes`) et **ne change pas la configuration finale**.

Référence de l'étape : `H 20 · idf · T2 · TRT tous · SST toutes`. « bat » = différence moyenne supérieure à son écart-type, sur 15 différences appariées.

| filtre | F1 moyen ± é.-t. | différence ± é.-t. | taille médiane | durée |
|---|---|---|---|---|
| aucun seuil | 0,682 ± 0,054 | — | 51 | 20 s |
| df ≥ 2 | 0,734 ± 0,046 ← **retenue** | +0,052 ± 0,039 **bat** | 45 | 21 s |

**Vainqueur du test complémentaire : df ≥ 2.** Meilleur F1 moyen : df ≥ 2. Aucune autre configuration ne reste à un écart-type de la meilleure : elle est retenue sur son seul score. Ce résultat ne modifie pas la configuration finale.

## 6. Configuration finale

**`H 20 · jdm · T2 · TRT tous · SST toutes`**

- F1 moyen : **0,819 ± 0,031**, contre 0,786 ± 0,041 pour la référence actuelle (`H 20 · binaire · T0 · TRT tous · SST toutes`).
- Gain apparié sur la référence actuelle : **+0,033 ± 0,023**, supérieur à son écart-type.

### 6.1 F1 par type, moyenne des 15 mesures

| type | référence actuelle | configuration finale | écart |
|---|---|---|---|
| `r_holo` | 0,716 | 0,807 | +0,091 |
| `r_product_of` | 0,593 | 0,663 | +0,070 |
| `r_topic` | 0,672 | 0,730 | +0,058 |
| `r_objet>matiere` | 0,860 | 0,915 | +0,055 |
| `r_own-1` | 0,730 | 0,777 | +0,047 |
| `r_has_causatif` | 0,897 | 0,939 | +0,042 |
| `r_depict` | 0,535 | 0,567 | +0,033 |
| `r_processus>instr-1` | 0,811 | 0,838 | +0,027 |
| `r_social_tie` | 0,849 | 0,873 | +0,025 |
| `r_lieu` | 0,918 | 0,942 | +0,024 |
| `r_has_property-1` | 0,912 | 0,936 | +0,024 |
| `r_processus_patient` | 0,812 | 0,833 | +0,021 |
| `r_lieu>origine` | 0,919 | 0,927 | +0,008 |
| `r_quantificateur` | 0,838 | 0,829 | −0,010 |
| `r_processus_agent` | 0,725 | 0,703 | −0,022 |

### 6.2 La descente

|  | référence actuelle | configuration finale |
|---|---|---|
| part des prédictions faites par une racine | 50,1 % | 46,5 % |
| profondeur d'arrêt moyenne (racine = 0) | 1,09 | 1,28 |
| prédictions faites par un nœud interne, racines comprises (par pli de 150) | 149,1 | 149,3 |
| nœuds gagnants internes **hors racine**, total sur 15 plis | 1110 | 1192 |
| prédictions faites par une feuille, total sur 15 plis | 13 | 11 |

## 7. Lecture

- **2 configurations sur 27** comparées à la référence de leur étape la battent au sens de la règle (différence moyenne > son écart-type).
- La configuration finale gagne 0,033 de F1 en moyenne sur la référence actuelle, pour un écart-type de 0,023 : le gain dépasse le bruit selon la règle fixée, de 1,41 écart-type seulement.
- **Le traitement du terme ne change rien de mesurable.** T1 et T2 s'écartent de T0 d'au plus 0,003 de F1, sous leur écart-type. T2 est retenu par la règle de simplicité, non parce qu'il gagnerait.
- **La rareté (idf) dégrade le F1 à tous les nombres d'hyperonymes**, avec ou sans poids de la collecte. Écart à binaire, à même H : H 20 : idf −0,106, jdm×idf −0,129 ; H 50 : idf −0,062, jdm×idf −0,066 ; H 100 : idf −0,017, jdm×idf −0,022 ; H 200 : idf −0,008, jdm×idf −0,016 ; H tous : idf −0,009, jdm×idf −0,016.
- **Plus d'hyperonymes n'aide pas.** En binaire, de H 20 à « tous » le F1 passe de 0,789 à 0,676 ; avec les poids de la collecte, de 0,819 à 0,764. Les poids de la collecte amortissent la chute sans l'annuler, et le meilleur réglage reste à H 20.
- **Le gain de la pondération de la collecte est mince** : +0,030 de F1 pour un écart-type de 0,028, soit 1,06 écart-type. Il franchit la règle fixée de peu.
- **TRT est indispensable, sa sélection ne l'est pas.** Retirer tout TRT coûte 0,177 de F1. Les 4 autres variantes de TRT ou de SST s'écartent d'au plus 0,011, dans le bruit : les conclusions des diagnostics en union ne se transposent pas, mais ne sont pas non plus renversées.
- **Le seuil de fréquence répare l'idf sans le rendre utile.** df ≥ 2 gagne 0,052 sur l'idf sans seuil, mais reste sous le binaire à même H (0,734 contre 0,789).
- **Réserves** : la règle « moyenne > écart-type » est indulgente ; les 15 mesures ne sont pas indépendantes ; et la configuration finale est la meilleure d'un balayage, donc son F1 de validation croisée est optimiste. Seule l'évaluation sur le test, qui n'a pas été lue, dira ce qui reste.

## 8. Sorties

- `data/signatures_variantes/mesures_cv.json` : les 15 mesures de chaque configuration (F1, F1 par type, statistiques de descente, durée), qui permettent de reconstruire ce rapport sans rien recalculer (`--rapport-seulement`).
- `data/signatures/` n'est pas touché ; les signatures variantes n'existent qu'en mémoire.
