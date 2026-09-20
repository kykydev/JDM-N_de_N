# Diagnostic du trait TRT, tour 2 : seuil, politique combinée, fusion

Suite de `reports/diagnostic_trt.md`, dont la conclusion est acquise : la saillance interne au terme sélectionne les types universels et échoue, la fréquence documentaire est la bonne direction. Trois questions restaient ouvertes : à quel seuil, sous quelle formulation, et avec quel critère de fusion.

Même banc de mesure qu'au tour 1 : 2000 paires de fond et 200 paires de signal par type, tirées avec `random.Random(42)` et réutilisées à l'identique. Le tour 2C mesure en plus les 750 règles réelles du split train. Rien n'est appliqué : `config.py`, le corpus, la collecte et `data/signatures/` sont inchangés.

## 1. Tour 2A — balayage du seuil de fréquence documentaire

Même banc que le tour 1 : mêmes 2000 paires de fond et 3000 paires de signal, tirées avec `random.Random(42)`, réutilisées telles quelles. Les colonnes sont directement comparables au tableau du tour 1.

| seuil | types retirés | bruit méd. | signal méd. | écart | pire type | fond > 0,5 | signal > 0,5 | taille méd. | `r_lieu` | `r_lieu>origine` |
|---|---|---|---|---|---|---|---|---|---|---|
| **P6@60** | 15 | 0,157 | 0,290 | **0,133** | 0,055 (`r_depict`) | 0,75 % | 6,80 % | 36 | 0,058 | 0,105 |
| **P6@65** | 12 | 0,183 | 0,315 | **0,132** | 0,064 (`r_depict`) | 1,40 % | 8,73 % | 38 | 0,073 | 0,108 |
| **P6@70** | 12 | 0,183 | 0,315 | **0,132** | 0,064 (`r_depict`) | 1,40 % | 8,73 % | 38 | 0,073 | 0,108 |
| **P6@75** | 11 | 0,197 | 0,327 | **0,130** | 0,056 (`r_depict`) | 1,85 % | 9,83 % | 39 | 0,065 | 0,096 |
| **P6@80** | 11 | 0,197 | 0,327 | **0,130** | 0,056 (`r_depict`) | 1,85 % | 9,83 % | 39 | 0,065 | 0,096 |
| **P6@85** | 9 | 0,226 | 0,351 | **0,125** | 0,055 (`r_depict`) | 2,35 % | 11,90 % | 40 | 0,064 | 0,093 |
| **P6@90** | 6 | 0,271 | 0,387 | **0,116** | 0,058 (`r_lieu`) | 4,00 % | 17,03 % | 43 | 0,058 | 0,083 |
| **P6@95** | 2 | 0,335 | 0,433 | **0,098** | 0,055 (`r_lieu`) | 7,25 % | 25,77 % | 47 | 0,055 | 0,071 |

Meilleur écart global : **P6@60 %** (0,133). Meilleur plancher par type : **P6@65 %** (0,064).

Pour mémoire, P6 à 80 % au tour 1 : écart 0,130, plancher 0,056, `r_lieu` 0,065, `r_lieu>origine` 0,096.

## 2. Tour 2B — politiques relatives à la population

Deux formulations du même principe : un type compte pour un terme si ce terme le reçoit beaucoup **par rapport aux autres termes**, pas dans l'absolu.

**P8, par centile.** Pour chaque type, la distribution de ses effectifs sur les termes du corpus, zéros compris. Le type est gardé pour un terme si son effectif dépasse le centile C de cette distribution. Un type rare a un centile nul et survit partout où il apparaît ; un type universel n'est gardé que là où il est vraiment massif.

**P9, par score TF-IDF.** Formulation que je propose en regard, parce qu'elle isole exactement la variable en cause au tour 1 : P1 à P3 gardaient les K premiers types par effectif brut et s'effondraient. P9 garde les K premiers par `(1 + log10 n) × log(N / df)` — même structure, classement différent. Si le diagnostic du tour 1 est juste, P9 doit battre P1 à P3 à K égal.

|  | bruit méd. | signal méd. | écart | pire type | fond > 0,5 | signal > 0,5 | taille méd. | `r_lieu` | `r_lieu>origine` |
|---|---|---|---|---|---|---|---|---|---|
| **P8@C50** | 0,176 | 0,331 | **0,155** | 0,071 (`r_lieu`) | 2,55 % | 11,93 % | 42 | 0,071 | 0,115 |
| **P8@C66** | 0,105 | 0,257 | **0,152** | 0,064 (`r_depict`) | 0,65 % | 6,03 % | 36 | 0,108 | 0,139 |
| **P8@C75** | 0,067 | 0,216 | **0,149** | 0,050 (`r_depict`) | 0,35 % | 3,20 % | 33 | 0,114 | 0,142 |
| **P8@C90** | 0,000 | 0,119 | **0,119** | 0,053 (`r_depict`) | 0,35 % | 1,57 % | 27 | 0,138 | 0,168 |
| **P9@K5** | 0,000 | 0,108 | **0,108** | 0,043 (`r_depict`) | 0,40 % | 1,70 % | 28 | 0,184 | 0,165 |
| **P9@K10** | 0,050 | 0,153 | **0,103** | 0,034 (`r_depict`) | 0,45 % | 1,90 % | 33 | 0,178 | 0,143 |
| **P9@K15** | 0,096 | 0,200 | **0,104** | 0,034 (`r_depict`) | 0,60 % | 3,03 % | 38 | 0,191 | 0,146 |

Meilleure du tour 2B : **P8@C50** (écart 0,155, plancher 0,071), contre 0,133 et 0,055 pour la meilleure du tour 2A (P6@60 %).

### 2.1 Le classement change tout, à nombre de types égal

Même règle « garder les K premiers types », deux façons de les classer. C'est le test direct du diagnostic du tour 1.

|  | politique | écart | pire type | signal > 0,5 |
|---|---|---|---|---|
| K = 5 | P1 (effectif brut) | 0,083 | 0,020 | 2,47 % |
|  | P9@K5 (TF-IDF) | 0,108 | 0,043 | 1,70 % |
| K = 10 | P2 (effectif brut) | 0,082 | 0,005 | 4,67 % |
|  | P9@K10 (TF-IDF) | 0,103 | 0,034 | 1,90 % |
| K = 15 | P3 (effectif brut) | 0,081 | 0,024 | 7,60 % |
|  | P9@K15 (TF-IDF) | 0,104 | 0,034 | 3,03 % |

## 3. Tour 2C — critère de fusion

Sur les règles réelles du split train : 50 par type, 750 en tout, soit 18 375 paires de même type et 262 500 paires de types différents. Aucune fusion n'est effectuée, on compte seulement ce qui passerait.

Deux lectures du critère du papier. **« les deux »** exige que la similarité des A ET celle des B dépassent le seuil. **« moyenne »** exige que leur moyenne le dépasse ; elle laisse donc passer une paire très ressemblante à gauche et pas du tout à droite.

Les paires de types différents ne seront jamais fusionnées — le papier ne fusionne que des règles de même `rt` — mais leur taux mesure le risque de confusion à la classification. Le **gain** est le rapport des deux taux : combien de fois plus souvent le critère rapproche deux règles de même type que deux règles de types différents.

### 3.1 Sous P6@60

| critère | seuil | paires même type | taux même type | paires autres types | taux autres types | gain |
|---|---|---|---|---|---|---|
| **les deux** | 0,30 | 4 282 | 23,3 % | 13 590 | 5,177 % | 4,5 |
| **les deux** | 0,35 | 2 110 | 11,5 % | 4 857 | 1,850 % | 6,2 |
| **les deux** | 0,40 | 941 | 5,1 % | 1 519 | 0,579 % | 8,8 |
| **les deux** | 0,45 | 326 | 1,8 % | 323 | 0,123 % | 14,4 |
| **les deux** | 0,50 | 84 | 0,5 % | 36 | 0,014 % | 33,3 |
| **les deux** | 0,55 | 12 | 0,1 % | 2 | 0,001 % | 85,7 |
| **les deux** | 0,60 | 0 | 0,0 % | 0 | 0,000 % | — |
| **moyenne** | 0,30 | 9 141 | 49,7 % | 38 255 | 14,573 % | 3,4 |
| **moyenne** | 0,35 | 5 362 | 29,2 % | 15 680 | 5,973 % | 4,9 |
| **moyenne** | 0,40 | 2 566 | 14,0 % | 4 988 | 1,900 % | 7,3 |
| **moyenne** | 0,45 | 1 024 | 5,6 % | 1 319 | 0,502 % | 11,1 |
| **moyenne** | 0,50 | 289 | 1,6 % | 347 | 0,132 % | 11,9 |
| **moyenne** | 0,55 | 54 | 0,3 % | 139 | 0,053 % | 5,5 |
| **moyenne** | 0,60 | 11 | 0,1 % | 77 | 0,029 % | 2,0 |

### 3.2 Sous P8@C50

| critère | seuil | paires même type | taux même type | paires autres types | taux autres types | gain |
|---|---|---|---|---|---|---|
| **les deux** | 0,30 | 6 622 | 36,0 % | 29 398 | 11,199 % | 3,2 |
| **les deux** | 0,35 | 4 097 | 22,3 % | 14 089 | 5,367 % | 4,2 |
| **les deux** | 0,40 | 2 140 | 11,6 % | 5 660 | 2,156 % | 5,4 |
| **les deux** | 0,45 | 898 | 4,9 % | 1 806 | 0,688 % | 7,1 |
| **les deux** | 0,50 | 314 | 1,7 % | 498 | 0,190 % | 9,0 |
| **les deux** | 0,55 | 85 | 0,5 % | 60 | 0,023 % | 20,2 |
| **les deux** | 0,60 | 10 | 0,1 % | 0 | 0,000 % | — |
| **moyenne** | 0,30 | 11 837 | 64,4 % | 71 339 | 27,177 % | 2,4 |
| **moyenne** | 0,35 | 8 246 | 44,9 % | 37 998 | 14,475 % | 3,1 |
| **moyenne** | 0,40 | 4 882 | 26,6 % | 16 860 | 6,423 % | 4,1 |
| **moyenne** | 0,45 | 2 305 | 12,5 % | 5 861 | 2,233 % | 5,6 |
| **moyenne** | 0,50 | 873 | 4,8 % | 1 611 | 0,614 % | 7,7 |
| **moyenne** | 0,55 | 241 | 1,3 % | 366 | 0,139 % | 9,4 |
| **moyenne** | 0,60 | 48 | 0,3 % | 106 | 0,040 % | 6,5 |

### 3.3 Sous P8@C66

| critère | seuil | paires même type | taux même type | paires autres types | taux autres types | gain |
|---|---|---|---|---|---|---|
| **les deux** | 0,30 | 3 086 | 16,8 % | 6 812 | 2,595 % | 6,5 |
| **les deux** | 0,35 | 1 558 | 8,5 % | 2 600 | 0,990 % | 8,6 |
| **les deux** | 0,40 | 664 | 3,6 % | 896 | 0,341 % | 10,6 |
| **les deux** | 0,45 | 228 | 1,2 % | 248 | 0,094 % | 13,1 |
| **les deux** | 0,50 | 71 | 0,4 % | 52 | 0,020 % | 19,5 |
| **les deux** | 0,55 | 10 | 0,1 % | 4 | 0,002 % | 35,7 |
| **les deux** | 0,60 | 0 | 0,0 % | 0 | 0,000 % | — |
| **moyenne** | 0,30 | 6 986 | 38,0 % | 22 654 | 8,630 % | 4,4 |
| **moyenne** | 0,35 | 3 888 | 21,2 % | 9 113 | 3,472 % | 6,1 |
| **moyenne** | 0,40 | 1 831 | 10,0 % | 3 165 | 1,206 % | 8,3 |
| **moyenne** | 0,45 | 717 | 3,9 % | 990 | 0,377 % | 10,3 |
| **moyenne** | 0,50 | 233 | 1,3 % | 338 | 0,129 % | 9,8 |
| **moyenne** | 0,55 | 53 | 0,3 % | 127 | 0,048 % | 6,0 |
| **moyenne** | 0,60 | 9 | 0,0 % | 60 | 0,023 % | 2,1 |

## 4. Recommandation

### 4.1 Seuil de fréquence documentaire

Si l'on reste sur P6 : **60 %**, écart 0,133 contre 0,130 à 80 %, et surtout 0,75 % de fusions parasites contre 1,85 %. Le gain sur l'écart est mince (0,003), le gain sur les fusions parasites ne l'est pas.

Deux choses à savoir sur ce balayage. Le seuil n'est pas un réglage continu : 65 % et 70 % donnent exactement le même résultat, 75 % et 80 % aussi, parce qu'aucun type n'a de fréquence documentaire dans ces intervalles. Et le plancher par type ne suit pas l'écart : il culmine à 0,064 au milieu du balayage (P6@65), pas à ses bornes. Le balayage s'arrête à 60 % par l'énoncé ; l'écart y est encore en train de monter, donc l'optimum pourrait être plus bas. Ce n'est pas mesuré ici.

### 4.2 Politique retenue

|  | écart | pire type | fond > 0,5 | signal > 0,5 | taille méd. | `r_lieu` | `r_lieu>origine` |
|---|---|---|---|---|---|---|---|
| **P6** | 0,130 | 0,056 | 1,85 % | 9,83 % | 39 | 0,065 | 0,096 |
| **P6@60** | 0,133 | 0,055 | 0,75 % | 6,80 % | 36 | 0,058 | 0,105 |
| **P8@C50** | 0,155 | 0,071 | 2,55 % | 11,93 % | 42 | 0,071 | 0,115 |
| **P8@C66** | 0,152 | 0,064 | 0,65 % | 6,03 % | 36 | 0,108 | 0,139 |

**P8@C66 — effectif au-dessus du 66e centile de la distribution du type sur le corpus.**

P8 bat toutes les variantes de P6, sur l'écart comme sur le plancher : 0,155 contre 0,133 pour le meilleur écart de la famille P6, 0,071 contre 0,064 pour son meilleur plancher. La raison est exactement celle que vous aviez avancée : la fréquence documentaire traite Bordeaux et saucisse de la même façon parce que tous deux reçoivent du `r_lieu-1`, alors que l'un en reçoit 990 et l'autre 3. Le centile les sépare.

Entre P8@C50 et P8@C66, l'écart se joue à 0,002 — du bruit d'échantillonnage — mais les fusions parasites vont du simple au 3,9 (2,55 % contre 0,65 %). C'est ce qui départage, et c'est pourquoi je recommande **P8@C66** plutôt que P8@C50.

Sur les deux types surveillés, P8@C66 répare ce que P6 abîmait : `r_lieu` passe de 0,065 à 0,108, `r_lieu>origine` de 0,096 à 0,139. Le décrochage constaté au tour 1 n'était pas le prix à payer, c'était un défaut de la formulation.

La section 2.1 confirme au passage le diagnostic du tour 1 : à nombre de types gardés égal, classer par TF-IDF au lieu de l'effectif brut fait passer l'écart de 0,082 à 0,103 et le plancher de 0,005 à 0,034. P9 reste sous P8 parce qu'un nombre fixe de types par terme reste arbitraire, mais le sens de la correction est le bon.

### 4.3 Critère de fusion

**« les deux » : les deux similarités doivent dépasser le seuil.** Sous P8@C66, aux 6 seuils où les deux critères laissent encore passer quelque chose, « les deux » sépare toujours mieux (gain 6,5 à 35,7, contre 4,4 à 10,3).

| seuil | « les deux » même | « les deux » autres | « les deux » gain | moyenne même | moyenne autres | moyenne gain |
|---|---|---|---|---|---|---|
| 0,30 | 16,8 % | 2,595 % | 6,5 | 38,0 % | 8,630 % | 4,4 |
| 0,35 | 8,5 % | 0,990 % | 8,6 | 21,2 % | 3,472 % | 6,1 |
| 0,40 | 3,6 % | 0,341 % | 10,6 | 10,0 % | 1,206 % | 8,3 |
| 0,45 | 1,2 % | 0,094 % | 13,1 | 3,9 % | 0,377 % | 10,3 |
| 0,50 | 0,4 % | 0,020 % | 19,5 | 1,3 % | 0,129 % | 9,8 |
| 0,55 | 0,1 % | 0,002 % | 35,7 | 0,3 % | 0,048 % | 6,0 |
| 0,60 | 0,0 % | 0,000 % | — | 0,0 % | 0,023 % | 2,1 |

Le tableau montre plus qu'un écart de niveau. Le gain de « les deux » croît avec le seuil, celui de « moyenne » plafonne à 0,45 puis **redescend**. La raison est mécanique : une paire dont les A se ressemblent beaucoup et les B pas du tout passe la moyenne, et c'est précisément la forme qu'ont les paires de types différents. Plus on monte le seuil, plus la moyenne sélectionne ces paires déséquilibrées. Serrer le seuil sous ce critère dégrade la précision au lieu de l'améliorer : c'est disqualifiant.

### 4.4 Fourchette de seuil de fusion pour l'étape 4

**0,35 à 0,45**, critère « les deux », sous P8@C66.

- à 0,35 : 1 558 paires de même type fusionnables (8,5 %), 2 600 paires de types différents franchissent le critère (0,990 %), gain 8,6 ;
- à 0,45 : 228 paires (1,2 %) contre 248 (0,094 %), gain 13,1.

Sous 0,35, plus de 1 % des paires de types différents passent : les classes de règles deviennent poreuses et la classification en pâtira avant même la fusion. Au-dessus de 0,45, il reste moins de 183 paires fusionnables sur l'ensemble du corpus d'entraînement : la généralisation n'a plus de matière.

Le 0,5 du papier tombe hors de cette fourchette, au-dessus. Le problème n'est pas la pureté — à 0,50 seules 0,020 % des paires de types différents passent, c'est excellent — mais le volume : il ne reste que 71 paires de même type fusionnables sur 18 375, soit 0,4 %. À ce régime la fusion ne produirait presque aucune règle générale. Le seuil du papier a été fixé sur des signatures qui ne sont pas les nôtres : c'est le nôtre qu'il faut caler, pas le leur qu'il faut reprendre.

### 4.5 Ce qu'il resterait à mesurer

L'écart décroît de 0,155 au centile 50 à 0,119 au centile 90, sans minimum intérieur : rien ne dit que l'optimum soit dans la plage testée, il est peut-être sous 50. Mais les fusions parasites y montent déjà (2,55 % au centile 50 contre 0,65 % au centile 66), donc descendre n'est pas gratuit. Un balayage plus fin trancherait ; il n'a pas été fait ici, l'énoncé fixait les quatre valeurs.

Toutes ces mesures portent sur le split train : le test n'a pas été touché, il doit rester intact jusqu'à l'évaluation de l'étape 4.

Ce script ne touche pas à `config.py` : les quatre décisions restent à prendre.

