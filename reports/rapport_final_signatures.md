# Évaluation finale des signatures retenues

## 1. Configuration et protocole

- **Méthode figée** : somme · arbre · descente, inchangée.
- **Signatures** : 20 hyperonymes, pondération `jdm` (poids de la collecte normalisés par terme et par trait), traitement du terme `T2` (absent), TRT `tous`, SST `toutes`. Choisies en validation croisée : `rapport_signatures_variantes.md`.
- **Apprentissage** : quinze arbres réappris sur les 750 exemples d'entraînement.
- **Test** : 450 exemples, 30 par type, **lus une seule fois**. Classement en 0,46 s. Ce rapport se reconstruit depuis `data/resultats/predictions_finales_jdm.json` sans relire le test.
- **Configuration actuelle** : son F1 de test est **repris tel quel** de `rapport_final.md` (`data/resultats/predictions_finales.json`), pas recalculé.

## 2. Résultats

**F1 macro : 0,778** (précision 0,790, rappel 0,778, exactitude 77,8 %, 350 exemples justes sur 450).

|  | F1 test | exactitude | F1 validation croisée (15 mesures) |
|---|---|---|---|
| **signatures retenues (jdm, T2)** | **0,778** | 77,8 % | 0,819 ± 0,031 |
| signatures actuelles (binaire, T0) | 0,753 | 75,6 % | 0,786 ± 0,041 |
| article | 0,772 | — | — |
| méthode à seuil | 0,597 | 60,0 % | — |
| plus proche voisin | 0,585 | — | — |

Écart entre les deux jeux de signatures : **+0,025** de F1 sur le test ; la validation croisée annonçait +0,033 ± 0,023.

**Cet écart mêle deux changements.** Les signatures retenues diffèrent des initiales par les poids (`binaire` → `jdm`) *et* par le symbole du terme (`T0` présent → `T2` retiré) : ce n'est donc pas l'effet de la seule pondération, mais celui des signatures retenues dans leur ensemble — poids et retrait du terme confondus. Les deux parts n'ont été séparées qu'en validation croisée : le retrait du terme y vaut +0,003 ± 0,011, sous son écart-type (`rapport_signatures_variantes.md` §1), et les poids seuls, à référence `binaire · T2`, +0,030 ± 0,028 sur 3 graines et +0,028 sur 10 (`rapport_ponderation.md`).

### 2.1 Détail par type

Trié par F1 de la nouvelle configuration. « actuelles » : F1 de test de la configuration précédente, repris de `rapport_final.md`.

| type | prédits | P (%) | R (%) | F1 | F1 actuelles | écart | F1 article | écart article |
|---|---|---|---|---|---|---|---|---|
| `r_has_property-1` | 29 | 100,0 | 96,7 | **0,98** | 0,95 | +0,03 | 0,59 | +0,39 |
| `r_lieu` | 26 | 100,0 | 86,7 | **0,93** | 0,87 | +0,06 | 0,76 | +0,17 |
| `r_lieu>origine` | 31 | 90,3 | 93,3 | **0,92** | 0,80 | +0,12 | 0,92 | −0,00 |
| `r_social_tie` | 36 | 80,6 | 96,7 | **0,88** | 0,91 | −0,03 | 0,91 | −0,03 |
| `r_objet>matiere` | 23 | 100,0 | 76,7 | **0,87** | 0,85 | +0,02 | 0,80 | +0,07 |
| `r_processus>instr-1` | 31 | 80,6 | 83,3 | **0,82** | 0,77 | +0,05 | 0,78 | +0,04 |
| `r_processus_patient` | 38 | 71,1 | 90,0 | **0,79** | 0,79 | +0,01 | 0,75 | +0,04 |
| `r_has_causatif` | 26 | 84,6 | 73,3 | **0,79** | 0,83 | −0,04 | 0,69 | +0,10 |
| `r_quantificateur` | 34 | 73,5 | 83,3 | **0,78** | 0,70 | +0,08 | 0,81 | −0,03 |
| `r_own-1` | 37 | 64,9 | 80,0 | **0,72** | 0,73 | −0,01 | 0,64 | +0,08 |
| `r_topic` | 29 | 72,4 | 70,0 | **0,71** | 0,66 | +0,06 | 0,76 | −0,05 |
| `r_processus_agent` | 27 | 74,1 | 66,7 | **0,70** | 0,71 | −0,01 | 0,81 | −0,11 |
| `r_holo` | 27 | 70,4 | 63,3 | **0,67** | 0,61 | +0,06 | 0,82 | −0,15 |
| `r_product_of` | 19 | 73,7 | 46,7 | **0,57** | 0,52 | +0,05 | 0,74 | −0,17 |
| `r_depict` | 37 | 48,6 | 60,0 | **0,54** | 0,61 | −0,07 | 0,80 | −0,26 |
| **macro** |  | 79,0 | 77,8 | **0,778** | 0,753 | +0,025 | 0,772 | +0,006 |

Le F1 progresse pour 10 types sur 15 par rapport aux signatures actuelles, et dépasse celui de l'article pour 7 types.

## 3. Matrice de confusion

Lignes : type attendu. Colonnes : type prédit, numérotés comme les lignes. Aussi écrite dans `data/resultats/matrice_confusion_finale_jdm.csv`.

| attendu \ prédit | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1. `r_depict` | **18** | · | · | 2 | · | · | · | 2 | 2 | 1 | 4 | · | · | 1 | · |
| 2. `r_has_causatif` | 3 | **22** | · | · | · | · | · | · | · | · | 2 | · | 3 | · | · |
| 3. `r_has_property-1` | · | · | **29** | · | · | · | · | · | · | · | · | · | · | 1 | · |
| 4. `r_holo` | 7 | · | · | **19** | · | · | · | · | · | · | · | · | 1 | · | 3 |
| 5. `r_lieu` | 2 | · | · | · | **26** | 1 | · | 1 | · | · | · | · | · | · | · |
| 6. `r_lieu>origine` | · | · | · | · | · | **28** | · | 1 | · | · | · | · | · | 1 | · |
| 7. `r_objet>matiere` | 1 | · | · | 2 | · | · | **23** | · | · | · | 1 | 1 | 2 | · | · |
| 8. `r_own-1` | 1 | · | · | · | · | · | · | **24** | · | · | · | 3 | · | 2 | · |
| 9. `r_processus>instr-1` | · | · | · | 2 | · | · | · | · | **25** | · | · | · | 1 | · | 2 |
| 10. `r_processus_agent` | · | 4 | · | · | · | · | · | · | · | **20** | 3 | · | 1 | 1 | 1 |
| 11. `r_processus_patient` | · | · | · | · | · | · | · | · | · | 3 | **27** | · | · | · | · |
| 12. `r_product_of` | 4 | · | · | 1 | · | 2 | · | 6 | · | 2 | · | **14** | · | · | 1 |
| 13. `r_quantificateur` | · | · | · | 1 | · | · | · | 1 | · | 1 | · | 1 | **25** | · | 1 |
| 14. `r_social_tie` | · | · | · | · | · | · | · | 1 | · | · | · | · | · | **29** | · |
| 15. `r_topic` | 1 | · | · | · | · | · | · | 1 | 4 | · | 1 | · | 1 | 1 | **21** |

Confusions les plus fréquentes : `r_holo` → `r_depict` (7), `r_product_of` → `r_own-1` (6), `r_depict` → `r_processus_patient` (4), `r_processus_agent` → `r_has_causatif` (4), `r_product_of` → `r_depict` (4), `r_topic` → `r_processus>instr-1` (4).

## 4. Ce qui change

Sur 450 exemples : **39 corrigés** (faux avant, justes maintenant), **29 cassés** (justes avant, faux maintenant), 14 restent faux mais avec un autre type. Solde net : +10.

| descente | signatures actuelles | signatures retenues |
|---|---|---|
| part des prédictions faites par une racine | 50,9 % | 43,6 % |
| profondeur d'arrêt moyenne (racine = 0) | 1,02 | 1,33 |
| nœuds gagnants internes hors racine | 217 | 251 |
| prédictions faites par une feuille | 4 | 3 |
| poids relatif moyen du nœud gagnant | 0,97 | 0,97 |
| calculs de score par exemple | 66,0 | 70,5 |

**Exemples corrigés** (les 12 premiers par ordre alphabétique) : « absurdité de la situation » (`r_has_property-1`) ; « aiguille de l'horloge » (`r_holo`) ; « alarme d'intrusion » (`r_processus>instr-1`) ; « ambre de la Baltique » (`r_lieu>origine`) ; « banc de poissons » (`r_quantificateur`) ; « chevaux d'Arabie » (`r_lieu>origine`) ; « cigares de La Havane » (`r_lieu>origine`) ; « couverture du livre » (`r_holo`) ; « ferrage du cheval » (`r_processus_patient`) ; « histoire de fantômes » (`r_topic`) ; « incendie du court-circuit » (`r_has_causatif`) ; « inondation des caves » (`r_processus_patient`)

**Exemples cassés** (les 12 premiers par ordre alphabétique) : « bijoux de la comtesse » (`r_own-1`) ; « buée de la douche » (`r_has_causatif`) ; « caries du sucre » (`r_has_causatif`) ; « cascades d'Iguazu » (`r_lieu`) ; « charrette du marchand » (`r_own-1`) ; « chat de Perse » (`r_lieu>origine`) ; « comité d'éthique » (`r_topic`) ; « coque de plexiglas » (`r_objet>matiere`) ; « effets de l'alcool » (`r_has_causatif`) ; « enregistrement d'un concert » (`r_depict`) ; « extincteur d'incendie » (`r_processus>instr-1`) ; « galette de sarrasin » (`r_objet>matiere`)

## 5. Lecture

- La validation croisée annonçait 0,033 de gain moyen : le test donne 0,025. Il est dans le même sens et du même ordre de grandeur.
- **Test des signes sur les exemples dont la justesse change** : 39 corrigés contre 29 cassés, soit 68 exemples discordants sur 450. Probabilité d'un déséquilibre au moins aussi grand sous un simple hasard : **0,27**. Le gain n'est pas établi au sens statistique usuel (seuil de 0,05) : il va dans le sens de la validation croisée sans le prouver.
- Un écart de 0,01 de F1 sur 450 exemples tient à quelques exemples ; le F1 de test de chaque configuration est lui-même une estimation, sans intervalle ici.
