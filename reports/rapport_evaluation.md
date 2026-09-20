# Évaluation sur le split test

Étape 6 : première et unique lecture des 450 exemples de test, avec les paramètres figés à l'étape 5. Les trois expériences de l'article suivent, chacune en regard des valeurs publiées.

## 1. Ouverture du split test

**Les 450 exemples de test (30 par type) sont lus pour la première fois.** Tous les réglages ci-dessous ont été arrêtés à l'étape 5 sur le jeu de calibrage, avant toute lecture du test. **Aucun n'est ajusté en fonction des scores de ce rapport.**

| paramètre | valeur figée |
|---|---|
| seuil de fusion | 0,50 |
| stratégie d'ordonnancement | glouton |
| critère de fusion | les deux (sim des A ET sim des B > seuil) |
| mesure de similarité | cosinus |
| seuil d'abstention | aucun — mesuré inutile au calibrage |
| politique de sélection TRT | `presence` (lecture de l'article) |
| hyperonymes gardés | top 20 |
| annotations SST morphologiques | conservées |
| types TRT exclus | 15 types non sémantiques |
| modèle | `modele_final.json`, 439 règles |

Rappel de méthode : le F1 de 0,520 obtenu au calibrage était une valeur de sélection, pas une estimation de généralisation. Les chiffres qui suivent sont la première mesure honnête de ce que vaut le système.

## 2. Évaluation principale (Tableau 3 de l'article)

270/450 exemples correctement classés, soit 60,0 % d'exactitude, contre 6,7 % attendus en tirant au hasard. Types triés par F1 décroissant.

| type | P (%) | R (%) | F1 | F1 article | écart |
|---|---|---|---|---|---|
| `r_social_tie` | 84,6 | 73,3 | **0,79** | 0,91 | −0,12 |
| `r_has_property-1` | 72,7 | 80,0 | **0,76** | 0,59 | +0,17 |
| `r_lieu>origine` | 75,0 | 70,0 | **0,72** | 0,92 | −0,20 |
| `r_processus_patient` | 67,7 | 70,0 | **0,69** | 0,75 | −0,06 |
| `r_objet>matiere` | 73,1 | 63,3 | **0,68** | 0,80 | −0,12 |
| `r_lieu` | 70,4 | 63,3 | **0,67** | 0,76 | −0,09 |
| `r_depict` | 55,8 | 80,0 | **0,66** | 0,80 | −0,14 |
| `r_processus>instr-1` | 59,4 | 63,3 | **0,61** | 0,78 | −0,17 |
| `r_quantificateur` | 61,5 | 53,3 | **0,57** | 0,81 | −0,24 |
| `r_own-1` | 43,8 | 70,0 | **0,54** | 0,64 | −0,10 |
| `r_has_causatif` | 60,9 | 46,7 | **0,53** | 0,69 | −0,16 |
| `r_processus_agent` | 50,0 | 50,0 | **0,50** | 0,81 | −0,31 |
| `r_product_of` | 50,0 | 46,7 | **0,48** | 0,74 | −0,26 |
| `r_topic` | 39,4 | 43,3 | **0,41** | 0,76 | −0,35 |
| `r_holo` | 50,0 | 26,7 | **0,35** | 0,82 | −0,47 |
| **moyenne macro** | **61,0** | **60,0** | **0,597** | **0,772** | **−0,175** |

**Évaluation indulgente** (§4.3 de l'article : le type attendu compte comme correct s'il arrive 2ᵉ à moins de 5 % du 1ᵉʳ) : F1 macro 0,684, soit +0,087 et 40 exemples repêchés sur 180 erreurs. Elle ne remplace pas l'évaluation stricte, elle dit seulement quelle part des erreurs sont des quasi-égalités.

## 3. Matrice de confusion

Lignes : type attendu. Colonnes : type prédit. La diagonale en gras est le nombre de bonnes réponses, sur 30 par type. Le préfixe `r_` est retiré des en-têtes de colonnes pour la lisibilité.

| attendu \ prédit | depict | has_causatif | has_property-1 | holo | lieu | lieu>origine | objet>matiere | own-1 | processus>instr-1 | processus_agent | processus_patient | product_of | quantificateur | social_tie | topic |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `r_depict` | **24** | 1 | · | 2 | · | · | · | 1 | · | · | · | 2 | · | · | · |
| `r_has_causatif` | 2 | **14** | 1 | · | · | · | · | · | 1 | · | · | 1 | 1 | · | 10 |
| `r_has_property-1` | 1 | 1 | **24** | · | · | · | 1 | · | · | · | 1 | 1 | 1 | · | · |
| `r_holo` | 6 | · | 2 | **8** | · | · | 1 | 4 | 2 | · | 4 | · | 2 | · | 1 |
| `r_lieu` | · | · | · | · | **19** | 7 | 1 | 1 | · | 1 | 1 | · | · | · | · |
| `r_lieu>origine` | 1 | · | · | · | 7 | **21** | · | · | · | · | · | · | · | 1 | · |
| `r_objet>matiere` | 1 | · | 1 | 2 | · | · | **19** | 1 | 1 | · | 1 | 3 | 1 | · | · |
| `r_own-1` | 1 | · | · | · | · | · | 1 | **21** | 2 | 2 | · | 2 | · | 1 | · |
| `r_processus>instr-1` | · | 2 | · | · | · | · | · | 2 | **19** | · | · | · | 4 | · | 3 |
| `r_processus_agent` | 1 | 2 | 3 | 2 | · | · | · | 3 | · | **15** | 1 | 1 | · | 1 | 1 |
| `r_processus_patient` | 2 | · | 1 | 1 | · | · | · | · | 1 | 4 | **21** | · | · | · | · |
| `r_product_of` | 2 | · | · | · | · | · | · | 7 | · | 4 | · | **14** | · | · | 3 |
| `r_quantificateur` | · | 1 | 1 | · | · | · | 2 | 3 | 1 | 2 | · | 1 | **16** | 1 | 2 |
| `r_social_tie` | 1 | · | · | 1 | · | · | 1 | 3 | · | 1 | · | 1 | · | **22** | · |
| `r_topic` | 1 | 2 | · | · | 1 | · | · | 2 | 5 | 1 | 2 | 2 | 1 | · | **13** |

### 3.1 Confusions les plus fréquentes

| attendu | prédit à la place | cas | part du type |
|---|---|---|---|
| `r_has_causatif` | `r_topic` | 10 | 33 % |
| `r_lieu` | `r_lieu>origine` | 7 | 23 % |
| `r_lieu>origine` | `r_lieu` | 7 | 23 % |
| `r_product_of` | `r_own-1` | 7 | 23 % |
| `r_holo` | `r_depict` | 6 | 20 % |
| `r_topic` | `r_processus>instr-1` | 5 | 17 % |
| `r_holo` | `r_own-1` | 4 | 13 % |
| `r_holo` | `r_processus_patient` | 4 | 13 % |
| `r_processus>instr-1` | `r_quantificateur` | 4 | 13 % |
| `r_processus_patient` | `r_processus_agent` | 4 | 13 % |

Les types les plus souvent proposés, tous attendus confondus : `r_own-1` (48), `r_depict` (43), `r_has_property-1` (33). Un type qui reçoit nettement plus de 30 prédictions est un aimant : il attire des exemples qui ne lui appartiennent pas.

## 4. Expérience 1 — apport de chaque trait (Tableau 2)

Chaque configuration est un **pipeline complet** : signatures filtrées sur les traits retenus, règles réapprises au même seuil et avec la même stratégie, puis classification. Les règles diffèrent donc d'une configuration à l'autre, ce qui est le point de l'expérience.

| configuration | règles | P (%) | R (%) | F1 | F1 article | écart |
|---|---|---|---|---|---|---|
| **H** | 749 | 45,2 | 45,3 | **0,443** | 0,653 | −0,210 |
| **H+SST** | 749 | 48,1 | 48,4 | **0,471** | 0,691 | −0,220 |
| **H+TRT** | 458 | 53,1 | 52,4 | **0,514** | 0,767 | −0,253 |
| **H+TRT+SST** | 439 | 61,0 | 60,0 | **0,597** | 0,772 | −0,175 |

Chez nous, passer de H seul à la configuration complète fait gagner +0,154 ; l'article gagne +0,119.

## 5. Expérience 2 — trait de définitude (Tableau 4)

Deux symboles sont ajoutés à la signature du terme B : `DEF:Det` ou `DEF:NoDet`, et `DEF:Def` ou `DEF:NoDef`. Ils dépendent de la **ligne** et non du terme — « photo de famille » et « photo d'une famille » partagent le terme B mais pas le déterminant, et c'est justement ce qui les distingue.

**Mesure ajoutée, absente de l'article.** JeuxDeMots porte déjà des annotations `DET` et `NODET` dans le trait SST. Les garder revient à compter deux fois la même information. Les quatre lignes isolent ce que chaque source apporte vraiment.

| configuration | règles | P (%) | R (%) | F1 |
|---|---|---|---|---|
| **H+TRT+SST** | 439 | 61,0 | 60,0 | **0,597** |
| **H+TRT+SST sans morpho** | 440 | 60,3 | 59,3 | **0,591** |
| **H+TRT+SST+DEF** | 421 | 60,1 | 57,1 | **0,570** |
| **H+TRT+SST sans morpho +DEF** | 422 | 59,6 | 56,7 | **0,566** |

- Le trait de définitude ajouté aux annotations de JDM : −0,027 (l'article gagne +0,023).
- Retirer les annotations morphologiques de JDM, sans rien ajouter : −0,007.
- Notre trait seul, les annotations de JDM retirées : −0,025 par rapport à la ligne sans morpho.

## 6. Expérience 3 — élagage des règles (Tableau 5)

**No Trim** : toutes les règles ayant existé pendant l'apprentissage, intermédiaires absorbées comprises. **Trim** : seulement celles qui n'ont pas servi d'entrée à une fusion, c'est-à-dire les règles fusionnées finales et les orphelines. Le temps est mesuré sur les 450 instances de test, mesure de similarité identique.

| configuration | P (%) | R (%) | F1 | règles | temps (s) | F1 article | règles article | temps article (s) |
|---|---|---|---|---|---|---|---|---|
| **Trim** | 61,0 | 60,0 | **0,597** | 439 | 1,12 | 0,770 | 49 | 25,42 |
| **No Trim** | 59,3 | 59,6 | **0,589** | 1061 | 2,67 | 0,798 | 1384 | 92,78 |

Chez nous, l'élagage divise le temps par 2,4 et y gagne même 0,008 de F1 : garder les règles intermédiaires ne sert à rien, elles ne font qu'ajouter des concurrentes moins bonnes que la règle qui les a absorbées. L'article rapporte un facteur 3,6 pour 0,028 de F1.

Les nombres absolus de règles ne sont pas comparables à ceux de l'article : ils dépendent du nombre de fusions, donc du corpus et de la représentation. C'est le rapport temps/qualité qui se compare.

## 7. Analyse des cas d'échec (section 4.5)

180 erreurs sur 450 exemples. Chaque erreur reçoit une cause unique, par ordre de priorité du plus spécifique au plus général :

`défaut de connaissance` → `dispersion morphologique` → `classe multiple` → `polysémie` → `autre`

La polysémie passe en dernier parce qu'elle est très répandue — 61 % des termes du corpus ont au moins un raffinement dans JDM — et absorberait tout le reste si elle venait en tête.

| cause | attribution exclusive | part des erreurs | présence (non exclusive) |
|---|---|---|---|
| défaut de connaissance | 0 | 0,0 % | 0 |
| dispersion morphologique | 6 | 3,3 % | 6 |
| classe multiple | 59 | 32,8 % | 61 |
| polysémie | 104 | 57,8 % | 152 |
| autre | 11 | 6,1 % | 11 |

La dernière colonne compte toutes les erreurs où la cause est présente, sans exclusivité : leur somme dépasse le nombre d'erreurs, puisqu'une même erreur cumule souvent plusieurs faiblesses.

**Comment chaque cause est détectée.** Ce sont des indices mesurables, pas un jugement manuel :

- *défaut de connaissance* — la signature de A ou de B compte moins de 3 symboles ;
- *dispersion morphologique* — le diagnostic de la collecte montre que le singulier du terme existe dans JDM et porte des hyperonymes, alors que la forme du corpus n'en a pas ;
- *classe multiple* — le type attendu est à moins de 5 % du type gagnant : la prédiction est défendable ;
- *polysémie* — A ou B a au moins deux raffinements de sens dans JDM, donc sa signature mélange plusieurs sens. C'est un **indice**, pas une preuve que la confusion vient de là.

### 7.1 Dix erreurs instructives

| syntagme | attendu | prédit | score gagnant | score du bon type | poids de la règle | cause |
|---|---|---|---|---|---|---|
| « poème d'amour » | `r_topic` | `r_product_of` | 0,753 | 0,523 | 1 | polysémie |
| « louche de service » | `r_processus>instr-1` | `r_quantificateur` | 0,747 | 0,538 | 1 | polysémie |
| « badge de l'employé » | `r_own-1` | `r_processus>instr-1` | 0,730 | 0,595 | 1 | polysémie |
| « croissant du boulanger » | `r_product_of` | `r_own-1` | 0,729 | 0,580 | 1 | polysémie |
| « douceur du velours » | `r_has_property-1` | `r_objet>matiere` | 0,728 | 0,494 | 1 | polysémie |
| « permis de chasse » | `r_topic` | `r_processus>instr-1` | 0,728 | 0,513 | 1 | polysémie |
| « allocution de la reine » | `r_processus_agent` | `r_social_tie` | 0,725 | 0,459 | 1 | polysémie |
| « bronzage de l'été » | `r_has_causatif` | `r_topic` | 0,723 | 0,547 | 2 | polysémie |
| « lanterne de papier » | `r_objet>matiere` | `r_quantificateur` | 0,711 | 0,489 | 1 | polysémie |
| « pile de la télécommande » | `r_holo` | `r_quantificateur` | 0,706 | 0,440 | 1 | polysémie |

Ce sont les erreurs les plus **confiantes** : le système s'est trompé avec un score élevé. Ce sont celles qui coûtent le plus cher, et celles qui renseignent le mieux sur ce qui manque à la base de connaissances.

## 8. Traçabilité des règles gagnantes sur le test

Même mesure qu'à l'étape 5, cette fois sur les 450 exemples de test.

| mesure | valeur |
|---|---|
| règles du modèle | 439 |
| dont orphelines / fusionnées | 267 / 172 |
| prédictions gagnées par une orpheline | 65,3 % |
| prédictions gagnées par une fusionnée | 34,7 % |
| part des orphelines qui gagnent au moins une fois | 55,4 % |
| part des fusionnées qui gagnent au moins une fois | 52,9 % |
| rapport des deux taux | 0,95× |
| règles distinctes ayant gagné | 239 |
| exemples d'entraînement absorbés par des règles qui ne gagnent jamais | 250 |
| score gagnant moyen | 0,569 |
| score moyen des règles du bon type | 0,424 |

Un rapport supérieur à 1 signifie qu'une règle fusionnée a plus de chances de gagner qu'une orpheline. Avec 439 règles pour 450 exemples de test, au plus 450 règles peuvent gagner : le compte brut de règles perdantes mesure surtout la taille du jeu, c'est le rapport qui informe.

