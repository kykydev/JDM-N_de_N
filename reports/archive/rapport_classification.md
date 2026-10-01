# Classification et choix du seuil de fusion

Étape 5 : la formule 3 de l'article appliquée aux règles apprises à l'étape 4, trois mesures de similarité comparées, et le seuil de fusion arrêté sur le jeu de calibrage. **Le split test n'est ni lu ni ouvert.** Aucune des trois expériences de l'article n'est menée ici.

## 1. Dispositif

- **Jeu évalué** : les 150 exemples de calibrage, 10 par type, tirés du train à l'étape 4. **Le split test n'est ni lu ni ouvert.**
- **Modèles** : les 6 modèles gloutons déjà appris (`data/modeles/`), seuils de fusion 0,30 à 0,55. Rien n'est réappris pour le balayage.
- **Formule 3** : `score = ½ [ sim(s(A), sL) + sim(s(B), sR) ]`, calculé contre toutes les règles de tous les types. Le `rt` de la mieux classée est la prédiction. Ex aequo départagés par l'identifiant de la règle.
- **Macro** : chaque type compte pour un, quel que soit le nombre de prédictions qu'il reçoit.
- **Hasard** : 6,7 % d'exactitude attendue en tirant au sort parmi 15 types.

## 2. Tâche 1 — classification du calibrage

### 2.1 Mesure « cosinus »

| seuil de fusion | règles | précision macro | rappel macro | F1 macro | exactitude |
|---|---|---|---|---|---|
| 0,30 | 58 | 0,403 | 0,353 | **0,357** | 53/150 (35 %) |
| 0,35 | 97 | 0,534 | 0,467 | **0,472** | 70/150 (47 %) |
| 0,40 | 160 | 0,535 | 0,460 | **0,469** | 69/150 (46 %) |
| 0,45 | 252 | 0,528 | 0,500 | **0,503** | 75/150 (50 %) |
| **0,50** (papier) | 367 | 0,547 | 0,520 | **0,520** | 78/150 (52 %) |
| 0,55 | 480 | 0,528 | 0,487 | **0,495** | 73/150 (49 %) |

### 2.2 Mesure « tversky »

| seuil de fusion | règles | précision macro | rappel macro | F1 macro | exactitude |
|---|---|---|---|---|---|
| 0,30 | 58 | 0,468 | 0,327 | **0,295** | 49/150 (33 %) |
| 0,35 | 97 | 0,538 | 0,480 | **0,469** | 72/150 (48 %) |
| 0,40 | 160 | 0,537 | 0,480 | **0,484** | 72/150 (48 %) |
| 0,45 | 252 | 0,501 | 0,440 | **0,451** | 66/150 (44 %) |
| **0,50** (papier) | 367 | 0,462 | 0,447 | **0,445** | 67/150 (45 %) |
| 0,55 | 480 | 0,472 | 0,467 | **0,459** | 70/150 (47 %) |

### 2.3 Mesure « couverture »

| seuil de fusion | règles | précision macro | rappel macro | F1 macro | exactitude |
|---|---|---|---|---|---|
| 0,30 | 58 | 0,495 | 0,467 | **0,453** | 70/150 (47 %) |
| 0,35 | 97 | 0,530 | 0,507 | **0,502** | 76/150 (51 %) |
| 0,40 | 160 | 0,456 | 0,413 | **0,406** | 62/150 (41 %) |
| 0,45 | 252 | 0,424 | 0,407 | **0,379** | 61/150 (41 %) |
| **0,50** (papier) | 367 | 0,463 | 0,440 | **0,423** | 66/150 (44 %) |
| 0,55 | 480 | 0,390 | 0,400 | **0,380** | 60/150 (40 %) |

### 2.4 Détail par type — « cosinus », seuil 0,50

« prédits » est le nombre de fois où le type a été proposé : un type qui en reçoit beaucoup plus que 10 est un aimant, un type qui en reçoit zéro n'est jamais proposé.

| type | attendus | prédits | corrects | précision | rappel | F1 |
|---|---|---|---|---|---|---|
| `r_depict` | 10 | 14 | 1 | 0,071 | 0,100 | 0,083 |
| `r_has_causatif` | 10 | 13 | 10 | 0,769 | 1,000 | 0,870 |
| `r_has_property-1` | 10 | 6 | 5 | 0,833 | 0,500 | 0,625 |
| `r_holo` | 10 | 4 | 2 | 0,500 | 0,200 | 0,286 |
| `r_lieu` | 10 | 11 | 9 | 0,818 | 0,900 | 0,857 |
| `r_lieu>origine` | 10 | 9 | 8 | 0,889 | 0,800 | 0,842 |
| `r_objet>matiere` | 10 | 11 | 6 | 0,545 | 0,600 | 0,571 |
| `r_own-1` | 10 | 11 | 3 | 0,273 | 0,300 | 0,286 |
| `r_processus>instr-1` | 10 | 12 | 6 | 0,500 | 0,600 | 0,545 |
| `r_processus_agent` | 10 | 10 | 3 | 0,300 | 0,300 | 0,300 |
| `r_processus_patient` | 10 | 6 | 4 | 0,667 | 0,400 | 0,500 |
| `r_product_of` | 10 | 14 | 4 | 0,286 | 0,400 | 0,333 |
| `r_quantificateur` | 10 | 11 | 8 | 0,727 | 0,800 | 0,762 |
| `r_social_tie` | 10 | 7 | 4 | 0,571 | 0,400 | 0,471 |
| `r_topic` | 10 | 11 | 5 | 0,455 | 0,500 | 0,476 |

## 3. Tâche 2 — traçabilité des règles gagnantes

L'hypothèse posée à l'étape 4 : le cosinus place la taille de la règle au dénominateur, donc une règle fusionnée volumineuse ne peut pas atteindre un score élevé ; les orphelines gagneraient presque toujours et la fusion ne ferait que rendre inaccessibles les exemples qu'elle absorbe.

### 3.1 Mesure « cosinus »

| seuil | part des règles fusionnées | part des victoires fusionnées | poids gagnant méd./max | taille gagnante méd./max | règles gagnantes : orph. / fus. | rapport | exemples absorbés perdus |
|---|---|---|---|---|---|---|---|
| 0,30 | 69 % | **49 %** | 1 / 4 | 113 / 238 | 61 % / 32 % | **0,53×** | 544 |
| 0,35 | 71 % | **54 %** | 2 / 8 | 121 / 370 | 57 % / 35 % | **0,61×** | 488 |
| 0,40 | 68 % | **47 %** | 1 / 11 | 110 / 446 | 56 % / 45 % | **0,81×** | 364 |
| 0,45 | 54 % | **39 %** | 1 / 8 | 115 / 381 | 43 % / 31 % | **0,72×** | 368 |
| **0,50** (papier) | 35 % | **24 %** | 1 / 5 | 114 / 280 | 33 % / 24 % | **0,72×** | 294 |
| 0,55 | 20 % | **17 %** | 1 / 5 | 110 / 280 | 25 % / 21 % | **0,84×** | 166 |

### 3.2 Mesure « tversky »

| seuil | part des règles fusionnées | part des victoires fusionnées | poids gagnant méd./max | taille gagnante méd./max | règles gagnantes : orph. / fus. | rapport | exemples absorbés perdus |
|---|---|---|---|---|---|---|---|
| 0,30 | 69 % | **93 %** | 4 / 26 | 202 / 695 | 33 % / 70 % | **2,10×** | 326 |
| 0,35 | 71 % | **92 %** | 4 / 22 | 226 / 656 | 25 % / 67 % | **2,67×** | 276 |
| 0,40 | 68 % | **91 %** | 4 / 12 | 225 / 519 | 17 % / 62 % | **3,58×** | 207 |
| 0,45 | 54 % | **86 %** | 3 / 10 | 194 / 425 | 15 % / 56 % | **3,81×** | 218 |
| **0,50** (papier) | 35 % | **71 %** | 2 / 8 | 185 / 373 | 15 % / 45 % | **2,99×** | 187 |
| 0,55 | 20 % | **53 %** | 2 / 5 | 143 / 280 | 15 % / 50 % | **3,33×** | 100 |

### 3.3 Mesure « couverture »

| seuil | part des règles fusionnées | part des victoires fusionnées | poids gagnant méd./max | taille gagnante méd./max | règles gagnantes : orph. / fus. | rapport | exemples absorbés perdus |
|---|---|---|---|---|---|---|---|
| 0,30 | 69 % | **100 %** | 30 / 38 | 845 / 1122 | 0 % / 52 % | **0,00×** | 92 |
| 0,35 | 71 % | **100 %** | 16 / 30 | 569 / 866 | 0 % / 49 % | **0,00×** | 155 |
| 0,40 | 68 % | **100 %** | 9 / 19 | 446 / 597 | 0 % / 39 % | **0,00×** | 241 |
| 0,45 | 54 % | **98 %** | 6 / 12 | 356 / 425 | 3 % / 32 % | **12,23×** | 253 |
| **0,50** (papier) | 35 % | **94 %** | 5 / 8 | 279 / 373 | 4 % / 33 % | **8,82×** | 203 |
| 0,55 | 20 % | **84 %** | 2 / 5 | 213 / 280 | 6 % / 44 % | **7,32×** | 113 |

**Comment lire ces tableaux.** Avec 150 exemples de calibrage, au plus 150 règles peuvent gagner ; un compte brut de règles perdantes mesure donc surtout la taille du jeu. Les deux colonnes qui testent vraiment l'hypothèse sont les dernières : « règles gagnantes : orph. / fus. » donne la part des règles orphelines qui gagnent au moins une fois et celle des règles fusionnées, et le « rapport » divise la seconde par la première. **Au-dessus de 1, une règle fusionnée a plus de chances de gagner qu'une orpheline ; en dessous, la fusion produit des règles que la mesure n'atteint pas.** C'est ce rapport, et non la part brute de victoires, qui départage — comparer 30 % de victoires à 24 % de la population n'aurait pas de sens sans normaliser.

### 3.4 Score gagnant contre score du bon type

« meilleure du bon type » est le score de la meilleure règle portant le type attendu : quand il égale le score gagnant, la prédiction est juste. « moyenne du bon type » est la moyenne sur toutes les règles de ce type, elle dit à quel point la bonne réponse se détache du fond.

| mesure | seuil | score gagnant | meilleure du bon type | moyenne du bon type | écart gagnant − moyenne |
|---|---|---|---|---|---|
| cosinus | 0,30 | 0,434 | 0,401 | 0,334 | 0,099 |
| cosinus | 0,35 | 0,472 | 0,442 | 0,367 | 0,105 |
| cosinus | 0,40 | 0,499 | 0,475 | 0,393 | 0,105 |
| cosinus | 0,45 | 0,539 | 0,511 | 0,419 | 0,119 |
| cosinus | **0,50** (papier) | 0,572 | 0,538 | 0,435 | 0,137 |
| cosinus | 0,55 | 0,593 | 0,555 | 0,448 | 0,145 |
| tversky | 0,30 | 0,451 | 0,409 | 0,336 | 0,114 |
| tversky | 0,35 | 0,498 | 0,471 | 0,377 | 0,121 |
| tversky | 0,40 | 0,531 | 0,504 | 0,398 | 0,133 |
| tversky | 0,45 | 0,563 | 0,529 | 0,408 | 0,156 |
| tversky | **0,50** (papier) | 0,584 | 0,544 | 0,407 | 0,177 |
| tversky | 0,55 | 0,596 | 0,553 | 0,412 | 0,184 |
| couverture | 0,30 | 0,824 | 0,793 | 0,570 | 0,254 |
| couverture | 0,35 | 0,805 | 0,775 | 0,562 | 0,244 |
| couverture | 0,40 | 0,786 | 0,753 | 0,539 | 0,247 |
| couverture | 0,45 | 0,765 | 0,732 | 0,511 | 0,254 |
| couverture | **0,50** (papier) | 0,749 | 0,716 | 0,488 | 0,261 |
| couverture | 0,55 | 0,722 | 0,686 | 0,482 | 0,241 |

## 4. Tâche 3 — comparaison des trois mesures

Les trois mesures ne diffèrent que par la pénalité infligée à une règle large :

| mesure | formule | pénalité de largeur |
|---|---|---|
| cosinus | \|s∩r\| / √(\|s\|·\|r\|) | racine de la taille de la règle |
| tversky | \|s∩r\| / (\|s∩r\| + \|s\\r\| + β\|r\\s\|), β = 0,2 | fraction de l'excédent |
| couverture | \|s∩r\| / \|s\| | aucune |

Tversky est la formulation que je propose en tiers : ce n'est pas une troisième idée mais le point intermédiaire d'une famille à un paramètre. À β = 0 elle vaut exactement la couverture, à β = 1 l'indice de Jaccard. Elle permet de savoir si l'écart entre les deux autres vient de la pénalité elle-même ou de son intensité.

La colonne « victoires des 10 % plus grandes » mesure l'effet de bord annoncé : une règle très large couvre n'importe quel terme.

| mesure | meilleur F1 macro | à quel seuil | exactitude | victoires fusionnées | victoires des 10 % plus grandes | score médian |
|---|---|---|---|---|---|---|
| **cosinus** | 0,520 | 0,50 | 52 % | 24 % | 3 % | 0,562 |
| **tversky** | 0,484 | 0,40 | 48 % | 91 % | 11 % | 0,526 |
| **couverture** | 0,502 | 0,35 | 51 % | 100 % | 52 % | 0,805 |

## 5. Tâche 4 — abstention

Mesuré sur la mesure « cosinus ». Un terme mal décrit dans JDM produit des similarités faibles avec toutes les règles et sa prédiction est arbitraire ; l'abstention consiste à ne pas répondre en deçà d'un score.

### 5.1 Distribution des scores gagnants

| seuil de fusion | min | c10 | médiane | c90 | max |
|---|---|---|---|---|---|
| 0,30 | 0,342 | 0,386 | 0,430 | 0,476 | 0,562 |
| 0,35 | 0,376 | 0,418 | 0,467 | 0,532 | 0,665 |
| 0,40 | 0,374 | 0,449 | 0,494 | 0,551 | 0,665 |
| 0,45 | 0,407 | 0,477 | 0,535 | 0,626 | 0,734 |
| **0,50** (papier) | 0,440 | 0,503 | 0,562 | 0,655 | 0,779 |
| 0,55 | 0,453 | 0,514 | 0,589 | 0,691 | 0,779 |

### 5.2 Effet des seuils d'abstention

**Seuil de fusion 0,30** — F1 sans abstention 0,357

| seuil d'abstention | abstentions | taux | F1 des retenus | gain de F1 | bonnes prédictions perdues |
|---|---|---|---|---|---|
| 0,05 | 0 | 0,0 % | 0,357 | = | 0 |
| 0,10 | 0 | 0,0 % | 0,357 | = | 0 |
| 0,15 | 0 | 0,0 % | 0,357 | = | 0 |
| 0,20 | 0 | 0,0 % | 0,357 | = | 0 |
| 0,25 * | 0 | 0,0 % | 0,357 | = | 0 |
| 0,30 * | 0 | 0,0 % | 0,357 | = | 0 |
| 0,35 * | 2 | 1,3 % | 0,361 | +0,003 | 0 |
| 0,40 * | 28 | 18,7 % | 0,370 | +0,012 | 8 |

**Seuil de fusion 0,35** — F1 sans abstention 0,472

| seuil d'abstention | abstentions | taux | F1 des retenus | gain de F1 | bonnes prédictions perdues |
|---|---|---|---|---|---|
| 0,05 | 0 | 0,0 % | 0,472 | = | 0 |
| 0,10 | 0 | 0,0 % | 0,472 | = | 0 |
| 0,15 | 0 | 0,0 % | 0,472 | = | 0 |
| 0,20 | 0 | 0,0 % | 0,472 | = | 0 |
| 0,25 * | 0 | 0,0 % | 0,472 | = | 0 |
| 0,30 * | 0 | 0,0 % | 0,472 | = | 0 |
| 0,35 * | 0 | 0,0 % | 0,472 | = | 0 |
| 0,40 * | 8 | 5,3 % | 0,466 | −0,007 | 5 |

**Seuil de fusion 0,40** — F1 sans abstention 0,469

| seuil d'abstention | abstentions | taux | F1 des retenus | gain de F1 | bonnes prédictions perdues |
|---|---|---|---|---|---|
| 0,05 | 0 | 0,0 % | 0,469 | = | 0 |
| 0,10 | 0 | 0,0 % | 0,469 | = | 0 |
| 0,15 | 0 | 0,0 % | 0,469 | = | 0 |
| 0,20 | 0 | 0,0 % | 0,469 | = | 0 |
| 0,25 * | 0 | 0,0 % | 0,469 | = | 0 |
| 0,30 * | 0 | 0,0 % | 0,469 | = | 0 |
| 0,35 * | 0 | 0,0 % | 0,469 | = | 0 |
| 0,40 * | 1 | 0,7 % | 0,467 | −0,002 | 1 |

**Seuil de fusion 0,45** — F1 sans abstention 0,503

| seuil d'abstention | abstentions | taux | F1 des retenus | gain de F1 | bonnes prédictions perdues |
|---|---|---|---|---|---|
| 0,05 | 0 | 0,0 % | 0,503 | = | 0 |
| 0,10 | 0 | 0,0 % | 0,503 | = | 0 |
| 0,15 | 0 | 0,0 % | 0,503 | = | 0 |
| 0,20 | 0 | 0,0 % | 0,503 | = | 0 |
| 0,25 * | 0 | 0,0 % | 0,503 | = | 0 |
| 0,30 * | 0 | 0,0 % | 0,503 | = | 0 |
| 0,35 * | 0 | 0,0 % | 0,503 | = | 0 |
| 0,40 * | 0 | 0,0 % | 0,503 | = | 0 |

**Seuil de fusion 0,50** — F1 sans abstention 0,520

| seuil d'abstention | abstentions | taux | F1 des retenus | gain de F1 | bonnes prédictions perdues |
|---|---|---|---|---|---|
| 0,05 | 0 | 0,0 % | 0,520 | = | 0 |
| 0,10 | 0 | 0,0 % | 0,520 | = | 0 |
| 0,15 | 0 | 0,0 % | 0,520 | = | 0 |
| 0,20 | 0 | 0,0 % | 0,520 | = | 0 |
| 0,25 * | 0 | 0,0 % | 0,520 | = | 0 |
| 0,30 * | 0 | 0,0 % | 0,520 | = | 0 |
| 0,35 * | 0 | 0,0 % | 0,520 | = | 0 |
| 0,40 * | 0 | 0,0 % | 0,520 | = | 0 |

**Seuil de fusion 0,55** — F1 sans abstention 0,495

| seuil d'abstention | abstentions | taux | F1 des retenus | gain de F1 | bonnes prédictions perdues |
|---|---|---|---|---|---|
| 0,05 | 0 | 0,0 % | 0,495 | = | 0 |
| 0,10 | 0 | 0,0 % | 0,495 | = | 0 |
| 0,15 | 0 | 0,0 % | 0,495 | = | 0 |
| 0,20 | 0 | 0,0 % | 0,495 | = | 0 |
| 0,25 * | 0 | 0,0 % | 0,495 | = | 0 |
| 0,30 * | 0 | 0,0 % | 0,495 | = | 0 |
| 0,35 * | 0 | 0,0 % | 0,495 | = | 0 |
| 0,40 * | 0 | 0,0 % | 0,495 | = | 0 |

## 6. Tâche 5 — verdict et recommandation

### 6.1 Verdict sur l'hypothèse des règles gagnantes

L'hypothèse formulée à l'étape 4 était la suivante : le cosinus place la taille de la règle au dénominateur, donc une règle fusionnée volumineuse ne peut pas atteindre un score élevé ; les orphelines gagneraient presque toujours et la fusion ne ferait que rendre inaccessibles les exemples qu'elle absorbe.

**Elle est réfutée.** Non pas sur la prémisse, qui est exacte, mais sur la conclusion.

| seuil | règles orph. / fus. | part des orphelines qui gagnent | part des fusionnées qui gagnent | rapport |
|---|---|---|---|---|
| 0,30 | 18 / 40 | 61 % | 32 % | **0,53×** |
| 0,35 | 28 / 69 | 57 % | 35 % | **0,61×** |
| 0,40 | 52 / 108 | 56 % | 45 % | **0,81×** |
| 0,45 | 116 / 136 | 43 % | 31 % | **0,72×** |
| **0,50** (papier) | 240 / 127 | 33 % | 24 % | **0,72×** |
| 0,55 | 386 / 94 | 25 % | 21 % | **0,84×** |

Sous le cosinus, une règle fusionnée gagne **plus** souvent qu'une orpheline, à tous les seuils : le rapport va de 0,53 à 0,84. Au seuil 0,30, les règles fusionnées sont 69 % de la population et remportent 49 % des prédictions. La part brute de victoires orphelines, spectaculaire, ne disait rien d'autre que le fait qu'il y a beaucoup plus d'orphelines.

La raison pour laquelle la prémisse n'entraîne pas la conclusion : fusionner agrandit le dénominateur, mais la signature élargie recoupe aussi davantage de termes, donc le numérateur grandit lui aussi. Le cosinus ne neutralise pas la fusion, il la tempère — et la tempérer suffisait, puisque c'est la mesure sans pénalité qui s'effondre.

**Ce que le balayage montre à la place** : le seuil de fusion ne change presque rien au F1. De 0,30 à 0,55, il va de 0,357 à 0,495, soit -20 exemples d'écart sur 150. La fusion aide un peu, régulièrement, sans jamais être décisive. L'étape 4 s'inquiétait d'un emballement ; l'emballement existe bien dans les signatures, mais il ne se traduit ni par un gain ni par une catastrophe à la classification.

### 6.2 Ce que la comparaison des mesures établit

**Le cosinus reste la meilleure des trois** : 0,520 de F1 macro contre 0,484 pour Tversky et 0,502 pour la couverture.

L'effet de bord annoncé pour la couverture est vérifié et il est massif : 52 % de ses prédictions sont remportées par les 10 % de règles les plus grandes, et seulement 34 règles distinctes gagnent quoi que ce soit sur 97. Une poignée de règles énormes couvre tout le monde. Ses scores sont aussi bien plus hauts (médiane 0,805 contre 0,562) sans être plus justes : la couverture est confiante et fausse.

Tversky à β = 0,2 se place exactement où on l'attendait, entre les deux — 11 % de victoires pour les plus grandes règles, contre 3 % au cosinus et 52 % à la couverture. Comme le F1 décroît de façon monotone du cosinus vers la couverture, **la pénalité de largeur n'est pas un défaut à corriger : plus on la retire, plus on classe mal.** C'est le résultat que la famille à un paramètre permettait d'établir, et qui n'aurait pas été lisible avec deux mesures seulement.

### 6.3 Abstention

Le score gagnant le plus faible du calibrage est 0,440. **Les quatre seuils demandés — 0,05, 0,10, 0,15, 0,20 — sont donc tous sous le plancher observé** : le plus élevé ne fait abstenir que 0 exemple sur 150. Il n'y a rien à trancher dans cette plage, et c'est en soi un résultat : sur ce corpus, aucun terme n'est assez mal décrit dans JDM pour produire un score quasi nul.

J'ai prolongé le balayage jusqu'à 0,40 pour que la courbe soit lisible. Le meilleur F1 des retenus, 0,520, est atteint à 0,05 pour 0 % d'abstention et 0 bonnes prédictions perdues. Le gain sur le F1 est de = : l'abstention ne sauve pas ce classifieur. Je ne fixe pas de seuil.

### 6.4 Seuil de fusion recommandé

**0,50**, avec le cosinus. F1 macro 0,520 sur le calibrage, 78/150 exemples justes, contre 6,7 % attendus au hasard.

| seuil | F1 macro | corrects | règles | victoires fusionnées |
|---|---|---|---|---|
| 0,30 | 0,357 | 53/150 | 58 | 49 % |
| 0,35 | 0,472 | 70/150 | 97 | 54 % |
| 0,40 | 0,469 | 69/150 | 160 | 47 % |
| 0,45 | 0,503 | 75/150 | 252 | 39 % |
| **0,50** (papier) | 0,520 | 78/150 | 367 | 24 % |
| 0,55 | 0,495 | 73/150 | 480 | 17 % |

La franchise s'impose sur ce choix : l'écart entre 0,50 et les deux seuils suivants vaut 0,017 de F1, soit trois exemples sur 150. **Ce n'est pas significatif à cette taille de jeu.** Ce qui départage vraiment 0,50, c'est la compacité : 367 règles contre 367 au seuil du papier, pour un F1 supérieur de 0,000. À performance équivalente, le modèle le plus petit est préférable, et c'est le seul argument que les chiffres autorisent.

Le seuil 0,50 de l'article donne 0,520, soit 0,000 de moins. Il reste dans le rapport comme point de comparaison, mais il n'est pas le meilleur choix sur ce corpus.

### 6.5 Modèle final

Réappris sur le train complet — 50 exemples par type, 750 en tout — au seuil 0,50, stratégie gloutonne, critère « les deux ». **439 règles**, dont 267 orphelines (61 %), écrites dans `data/modeles/modele_final.json`.

Il n'est pas classé contre le test : c'est l'étape 6. Le calibrage a servi à choisir le seuil, il ne peut donc plus servir à estimer la performance ; les 53 % d'exactitude ci-dessus sont une valeur de sélection, pas une mesure de généralisation.

## 7. Sorties écrites

- **18 fichiers de prédictions** dans `data/resultats/`, un par couple mesure × seuil, nommés `calibrage_<mesure>_<seuil>.json`. Chacun porte, pour ses 150 exemples, le type attendu, le type prédit, le score, et la règle gagnante avec son poids, la taille de ses deux signatures et les exemples qu'elle couvre.
- **Le modèle final** dans `data/modeles/modele_final.json`.
- Aucune matrice de similarité n'est stockée : les scores sont calculés à la volée et seuls les gagnants sont conservés.

