# Clustering hiérarchique et classification par descente

<!-- partie A -->
## A. Construction des arbres

### A.1 Dispositif

- **15 arbres**, un par type : deux règles de types différents ne fusionnent jamais (note 2 de l'article).
- **750 feuilles**, les 50 exemples d'entraînement de chaque type. Le calibrage n'a plus d'objet : il n'y a plus de seuil à choisir.
- **1485 nœuds** stockés, feuilles comprises, dans `data/modeles/arbres.json`.
- **Lien** : `min( sim(sLi, sLj), sim(sRi, sRj) )`, cosinus sur ensembles. Le minimum exige que les deux côtés se ressemblent.
- **Ex aequo** : départagés par l'ordre d'apparition dans le corpus.
- **Aucun seuil** : on fusionne jusqu'à la racine.
- **Coût** : 36015 liens calculés en tout — la demi-matrice initiale, puis une seule ligne par fusion. Recalculer toute la matrice à chaque fusion en aurait coûté de l'ordre de 312375. Durée : 0,4 s.

### A.2 Les quinze arbres

- **profondeur** : celle de la feuille la plus profonde, la racine étant à 0. Un arbre parfaitement équilibré de 50 feuilles a une profondeur de 6, un peigne pur de 49.
- **hauteur** : valeur du lien au moment de la fusion. Celle de la racine est le lien de la dernière fusion ; médiane et maximum portent sur les 49 fusions du type.
- **inversions** : nœuds dont la hauteur dépasse celle d'un de leurs enfants internes ; « écart max » est le plus grand dépassement.
- **plus gros enfant** : poids du plus lourd des deux enfants de la racine. 25 / 50 est l'équilibre parfait, 49 / 50 le peigne.
- **greffes** : fusions d'une feuille isolée avec un groupe déjà formé, sur les 49 fusions du type.

| type | profondeur | hauteur racine | hauteur méd. | hauteur max | inversions | écart max | \|sL\| / \|sR\| racine | plus gros enfant | greffes |
|---|---|---|---|---|---|---|---|---|---|
| `r_depict` | 9 | 0,049 | 0,440 | 0,650 | 2 | 0,036 | 701 / 860 | 49 / 50 | 8 / 49 |
| `r_has_causatif` | 10 | 0,058 | 0,481 | 0,659 | 6 | 0,050 | 542 / 813 | 48 / 50 | 8 / 49 |
| `r_has_property-1` | 10 | 0,144 | 0,488 | 0,643 | 4 | 0,023 | 530 / 753 | 49 / 50 | 10 / 49 |
| `r_holo` | 9 | 0,207 | 0,458 | 0,617 | 1 | 0,002 | 717 / 759 | 45 / 50 | 12 / 49 |
| `r_lieu` | 9 | 0,217 | 0,460 | 0,658 | 4 | 0,036 | 643 / 479 | 48 / 50 | 12 / 49 |
| `r_lieu>origine` | 8 | 0,226 | 0,471 | 0,646 | 4 | 0,020 | 682 / 442 | 47 / 50 | 10 / 49 |
| `r_objet>matiere` | 8 | 0,188 | 0,483 | 0,640 | 3 | 0,011 | 679 / 615 | 46 / 50 | 8 / 49 |
| `r_own-1` | 10 | 0,189 | 0,498 | 0,662 | 5 | 0,057 | 737 / 469 | 44 / 50 | 12 / 49 |
| `r_processus>instr-1` | 8 | 0,269 | 0,483 | 0,662 | 4 | 0,083 | 680 / 724 | 32 / 50 | 12 / 49 |
| `r_processus_agent` | 10 | 0,028 | 0,483 | 0,676 | 2 | 0,065 | 709 / 659 | 49 / 50 | 12 / 49 |
| `r_processus_patient` | 7 | 0,220 | 0,510 | 0,649 | 0 | — | 647 / 787 | 30 / 50 | 8 / 49 |
| `r_product_of` | 8 | 0,225 | 0,491 | 0,631 | 5 | 0,020 | 806 / 537 | 47 / 50 | 14 / 49 |
| `r_quantificateur` | 9 | 0,101 | 0,483 | 0,652 | 1 | 0,025 | 607 / 766 | 49 / 50 | 16 / 49 |
| `r_social_tie` | 12 | 0,068 | 0,497 | 0,659 | 4 | 0,022 | 490 / 683 | 49 / 50 | 12 / 49 |
| `r_topic` | 7 | 0,269 | 0,470 | 0,622 | 4 | 0,026 | 845 / 822 | 27 / 50 | 10 / 49 |

### A.3 Synthèse

- **Inversions** : 49 nœuds internes sur 735 (6,7 %), dans 14 arbres sur 15. Écart maximal observé : 0,083.
- **Profondeur** : de 7 à 12, médiane 9.
- **Forme** : le plus gros enfant de la racine pèse de 54 % à 98 % des feuilles, et 11 racines sur 15 sont à 90 % ou plus. **Ce n'est pas un peigne** : un peigne de 50 feuilles aurait une profondeur de 49, les nôtres plafonnent à 12, et 164 fusions sur 735 (22,3 %) seulement sont des greffes de feuille. Le déséquilibre vient d'isolats rattachés en tout dernier, détaillés en A.4.
- **Hauteur de la racine** : de 0,028 à 0,269, médiane 0,189. C'est ce que valent, au pire des deux côtés, les deux moitiés d'un type l'une pour l'autre.

### A.4 Isolats de racine

En descendant de la racine vers l'enfant lourd, on détache tant que l'autre enfant pèse au plus 3 exemples. Ce sont les exemples que leur type n'a su rapprocher de personne : ils ne rejoignent l'arbre qu'à la toute fin, par un lien très faible.

| type | lien de rattachement | exemples détachés |
|---|---|---|
| `r_depict` | 0,049 | « échographie d'un fœtus » |
| `r_depict` | 0,174 | « vignette d'une scène », « fusain d'un arbre », « pastel d'une falaise » |
| `r_has_causatif` | 0,058 | « avaries de la tempête », « flaques de la pluie » |
| `r_has_property-1` | 0,144 | « entêtement de la mule » |
| `r_lieu` | 0,217 | « musée du Caire », « nuits de Saint-Pétersbourg » |
| `r_lieu>origine` | 0,226 | « cristal de Bohême », « caviar de la Caspienne », « diamants d'Afrique du Sud » |
| `r_processus_agent` | 0,028 | « grève des cheminots » |
| `r_processus_agent` | 0,177 | « course du sprinteur » |
| `r_product_of` | 0,225 | « fresque du muraliste », « œuf de la poule », « perle de l'huître » |
| `r_quantificateur` | 0,101 | « douzaine d'œufs » |
| `r_social_tie` | 0,068 | « roi des Belges » |
| `r_social_tie` | 0,153 | « syndic de la copropriété », « recteur de l'académie » |

9 arbres sur 15 ont au moins un isolat, 21 exemples en tout sur 750. Une fois détachés, les noyaux pèsent de 46 à 50 exemples et leurs deux enfants sont de vraies branches.
<!-- fin A -->

<!-- partie B -->
## B. Classification par descente

### B.1 Dispositif

- **Jeu évalué** : les 450 exemples de test, 30 par type. La méthode n'a **aucun paramètre libre** — ni seuil de fusion, ni seuil d'arrêt, ni mesure à choisir — donc rien n'a pu être réglé sur ce jeu.
- **Score** : `½ [ sim(s(A), sL) + sim(s(B), sR) ]`, formule 3 de l'article, cosinus sur ensembles.
- **Asymétrie voulue** : la construction fusionne sur le **minimum** des deux côtés, la classification score sur la **moyenne**. Exigeant pour fusionner, fidèle à la formule publiée pour classer. Conséquence à garder en tête : un côté parfait peut porter un côté nul à la classification, ce qu'il ne pouvait pas faire à la construction.
- **Descente** : dans chacun des 15 arbres, de la racine vers le meilleur enfant tant qu'il fait **strictement** mieux que le nœud courant. L'arbre dont la réponse a le meilleur score donne la prédiction.
- **Références**, avec les mêmes arbres : (a) plus proche voisin sur les 750 feuilles ; (b) meilleur des 1485 nœuds ; (c) la descente.

### B.2 Les trois méthodes

| méthode | P macro | R macro | F1 macro | exactitude | prédictions par un nœud interne | calculs / exemple | temps total (s) |
|---|---|---|---|---|---|---|---|
| **(a) feuilles, exhaustif** | 0,589 | 0,591 | **0,585** | 59,1 % | 0,0 % | 750,0 | 2,23 |
| **(b) tous les nœuds, exhaustif** | 0,590 | 0,593 | **0,587** | 59,3 % | 1,3 % | 1485,0 | 6,21 |
| **(c) descente** | 0,310 | 0,276 | **0,219** | 27,6 % | 9,3 % | 89,9 | 0,76 |

Pour situer : article 0,772, méthode à seuil précédente 0,597. La descente fait −0,378 par rapport à la méthode à seuil et −0,553 par rapport à l'article.

**Lecture.**

- (c) contre (a) : −0,366. La descente ne fait pas mieux que le plus proche voisin : l'arbre ne généralise pas, ou sa généralisation ne sert pas.
- (c) contre (b) : −0,368, pour 89,9 calculs par exemple au lieu de 1485 (16,5 fois moins). La descente est **en dessous** de l'exhaustif : elle se trompe de branche, § B.6 dit à quel niveau.
- (b) contre (a) : +0,002. C'est ce que vaudrait la généralisation si on savait toujours trouver le meilleur nœud.

### B.3 Détail par type

- **prédits** : nombre de fois où le type est proposé, pour 30 attendus.
- **arrêts internes (arbre)** : sur les 450 descentes de cet arbre, part qui s'arrêtent sur un nœud interne ; **profondeur moy.** : profondeur moyenne d'arrêt dans cet arbre.
- **prédictions internes** : parmi les prédictions de ce type, part faite par un nœud interne.

| type | prédits | P (%) | R (%) | F1 | F1 seuil | F1 article | arrêts internes (arbre) | profondeur moy. | prédictions internes |
|---|---|---|---|---|---|---|---|---|---|
| `r_lieu` | 34 | 61,8 | 70,0 | **0,66** | 0,67 | 0,76 | 49 % | 1,6 | 24 % (34) |
| `r_lieu>origine` | 13 | 92,3 | 40,0 | **0,56** | 0,72 | 0,92 | 4 % | 2,1 | 23 % (13) |
| `r_processus>instr-1` | 28 | 50,0 | 46,7 | **0,48** | 0,61 | 0,78 | 40 % | 2,8 | 32 % (28) |
| `r_objet>matiere` | 17 | 52,9 | 30,0 | **0,38** | 0,68 | 0,80 | 1 % | 2,0 | 24 % (17) |
| `r_processus_patient` | 103 | 23,3 | 80,0 | **0,36** | 0,69 | 0,75 | 15 % | 5,0 | 4 % (103) |
| `r_own-1` | 95 | 21,1 | 66,7 | **0,32** | 0,54 | 0,64 | 12 % | 3,7 | 12 % (95) |
| `r_topic` | 120 | 15,8 | 63,3 | **0,25** | 0,41 | 0,76 | 3 % | 5,1 | 2 % (120) |
| `r_holo` | 9 | 22,2 | 6,7 | **0,10** | 0,35 | 0,82 | 12 % | 3,0 | 0 % (9) |
| `r_social_tie` | 1 | 100,0 | 3,3 | **0,06** | 0,79 | 0,91 | 0 % | 1,0 | 0 % (1) |
| `r_has_causatif` | 5 | 20,0 | 3,3 | **0,06** | 0,53 | 0,69 | 0 % | 2,1 | 0 % (5) |
| `r_quantificateur` | 17 | 5,9 | 3,3 | **0,04** | 0,57 | 0,81 | 3 % | 2,2 | 0 % (17) |
| `r_depict` | 0 | 0,0 | 0,0 | **0,00** | 0,66 | 0,80 | 0 % | 1,0 | 0 % (0) |
| `r_has_property-1` | 0 | 0,0 | 0,0 | **0,00** | 0,76 | 0,59 | 0 % | 1,0 | 0 % (0) |
| `r_processus_agent` | 1 | 0,0 | 0,0 | **0,00** | 0,50 | 0,81 | 0 % | 1,1 | 0 % (1) |
| `r_product_of` | 7 | 0,0 | 0,0 | **0,00** | 0,48 | 0,74 | 38 % | 1,9 | 14 % (7) |

### B.4 Matrice de confusion

Lignes : type attendu. Colonnes : type prédit, numérotés comme les lignes. Aussi écrite dans `data/resultats/matrice_confusion.csv`.

| attendu \ prédit | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1. `r_depict` | **0** | · | · | · | · | · | 2 | 9 | · | · | 12 | · | · | · | 7 |
| 2. `r_has_causatif` | · | **1** | · | · | · | · | 1 | 3 | · | · | 9 | · | 1 | · | 15 |
| 3. `r_has_property-1` | · | · | **0** | 2 | · | · | 2 | 4 | 2 | · | 11 | · | · | · | 9 |
| 4. `r_holo` | · | · | · | **2** | 1 | · | · | 7 | 2 | · | 8 | · | · | · | 10 |
| 5. `r_lieu` | · | 1 | · | · | **21** | · | · | 4 | · | · | 2 | · | · | · | 2 |
| 6. `r_lieu>origine` | · | 1 | · | · | 11 | **12** | · | 3 | 1 | · | 1 | 1 | · | · | · |
| 7. `r_objet>matiere` | · | · | · | 2 | · | · | **9** | · | 4 | · | 3 | 2 | 4 | · | 6 |
| 8. `r_own-1` | · | · | · | · | · | · | 1 | **20** | 1 | · | 1 | 1 | 1 | · | 5 |
| 9. `r_processus>instr-1` | · | · | · | · | · | · | · | 4 | **14** | · | 2 | 1 | 1 | · | 8 |
| 10. `r_processus_agent` | · | · | · | 1 | · | · | 1 | 5 | · | **0** | 11 | · | 1 | · | 11 |
| 11. `r_processus_patient` | · | · | · | 1 | · | · | · | 1 | · | 1 | **24** | · | · | · | 3 |
| 12. `r_product_of` | · | · | · | 1 | · | 1 | · | 11 | · | · | 1 | **0** | 5 | · | 11 |
| 13. `r_quantificateur` | · | 2 | · | · | · | · | · | 12 | · | · | 7 | 1 | **1** | · | 7 |
| 14. `r_social_tie` | · | · | · | · | · | · | 1 | 9 | 4 | · | 7 | · | 1 | **1** | 7 |
| 15. `r_topic` | · | · | · | · | 1 | · | · | 3 | · | · | 4 | 1 | 2 | · | **19** |

Confusions les plus fréquentes : `r_has_causatif` → `r_topic` (15), `r_depict` → `r_processus_patient` (12), `r_quantificateur` → `r_own-1` (12), `r_has_property-1` → `r_processus_patient` (11), `r_lieu>origine` → `r_lieu` (11), `r_processus_agent` → `r_processus_patient` (11).

### B.5 Généralisation

- **Arrêts internes** : 9,3 % des prédictions (42 sur 450) sont faites par un nœud interne ; sur l'ensemble des 6750 descentes, tous arbres confondus, 11,8 % s'arrêtent sur un nœud interne.
- **Calculs** : 89,9 scores par exemple en moyenne, 127 au plus.

**La généralisation est-elle juste quand elle se produit ?**

| prédiction faite par | exemples | justes (exactitude) | F1 macro |
|---|---|---|---|
| feuille | 408 | 103 (25,2 %) | 0,205 |
| nœud interne | 42 | 21 (50,0 %) | 0,278 |

Le F1 macro d'une partie est calculé sur les types qu'elle contient ; l'exactitude, qui ne dépend pas de cette convention, est le chiffre à comparer.

**Poids du nœud d'arrêt**

| poids | 1 | 2 | 3–5 | 6–10 | 11–25 | 26–50 |
|---|---|---|---|---|---|---|
| prédictions | 408 | 38 | 4 | 0 | 0 | 0 |
| toutes les descentes | 5953 | 568 | 225 | 3 | 0 | 1 |

**Profondeur d'arrêt** (racine = 0)

| profondeur | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|
| prédictions | 11 | 70 | 49 | 48 | 207 | 50 | 15 |
| toutes les descentes | 2462 | 2104 | 630 | 520 | 816 | 192 | 26 |

### B.6 Erreurs de branche : la descente contre l'exhaustif

Pour chaque descente, on compare le nœud d'arrêt au meilleur nœud du même arbre, trouvé par l'exhaustif.

- **optimale** : la descente trouve le maximum de l'arbre ;
- **arrêt prématuré** : le maximum est sous le nœud d'arrêt — aucun des deux enfants ne faisait mieux, mais un descendant plus profond, si ;
- **mauvaise branche** : le maximum est dans l'autre sous-arbre ; le niveau est la profondeur du dernier ancêtre commun, là où la descente a choisi le mauvais enfant.

| descentes | nombre | optimales | arrêts prématurés | mauvaises branches | perte de score méd. | perte max |
|---|---|---|---|---|---|---|
| toutes les descentes | 6750 | 5,5 % | 8 | 6369 | 0,131 | 0,538 |
| arbre du type attendu | 450 | 4,0 % | 0 | 432 | 0,177 | 0,538 |

**Niveau des erreurs**, dans l'arbre du type attendu :

- mauvaise branche, profondeur de l'embranchement → 0 : 393, 1 : 29, 2 : 6, 3 : 3, 4 : 1
- arrêt prématuré, profondeur de l'arrêt → —

Et sur toutes les descentes :

- mauvaise branche → 0 : 5730, 1 : 429, 2 : 109, 3 : 80, 4 : 21
- arrêt prématuré → 1 : 2, 2 : 1, 3 : 4, 5 : 1

**Ce que cela coûte en prédictions.** (b) et (c) prédisent un type différent pour 315 exemples. L'exhaustif réussit et la descente échoue sur 183 exemples ; l'inverse arrive sur 40. Parmi les exemples perdus, la descente de l'arbre attendu était : optimale 0, arrêtée trop tôt 0, dans la mauvaise branche 183. Par construction, un exemple que l'exhaustif réussit a son meilleur nœud absolu dans l'arbre attendu : si la descente de cet arbre le trouvait, elle gagnerait aussi. Toute perte est donc une descente sous-optimale dans l'arbre attendu, sauf égalité exacte de scores.

### B.7 Le mécanisme : le cosinus tire la descente vers l'enfant léger

Le cosinus divise par la racine de la taille de la signature du nœud. Plus un nœud couvre d'exemples, plus sa signature est grande et plus son score baisse, **quel que soit son contenu**. À chaque embranchement, l'enfant le plus léger part donc avantagé.

| embranchement | vers l'enfant léger | vers l'enfant lourd | enfants de même poids | arrêt |
|---|---|---|---|---|
| racine | **6283** (93 %) | 467 | 0 | 0 |
| tous niveaux | 9755 (61 % des descentes effectives) | 2276 | 4023 | 797 |

Les signatures des racines comptent en moyenne 673 symboles par côté, contre une cinquantaine pour un exemple. Or dans 9 arbres sur 15, l'enfant léger de la racine est un **isolat** (partie A.4) : un à trois exemples que le type n'a rapprochés de personne. La descente y entre dès le premier pas et s'y arrête, sur l'exemple le **moins** représentatif du type.

Les arbres où la descente s'arrête en moyenne avant la profondeur 1,5 sont `r_depict` (isolat), `r_has_property-1` (isolat), `r_processus_agent` (isolat), `r_social_tie` (isolat) : 4 sur 4 ont un isolat à la racine. Leurs F1 en B.3 sont parmi les plus bas.

L'exhaustif ne souffre pas de ce biais de la même façon : il compare tous les nœuds entre eux et trouve la feuille qui colle, là où la descente ne compare que deux frères de tailles très différentes. C'est aussi pourquoi (b) ne fait pas mieux que (a) : les nœuds internes, plus gros, ne battent presque jamais la meilleure feuille.

### B.8 Sorties écrites

- `data/resultats/test_predictions.json` : pour chaque exemple, le chemin complet de la descente dans l'arbre gagnant (score de chaque nœud visité et de ses deux enfants), le nœud d'arrêt, la réponse des quinze arbres, et les prédictions des deux références.
- `data/resultats/matrice_confusion.csv` : la matrice de confusion de la descente.
<!-- fin B -->

<!-- partie C -->
## C. Expériences de l'article avec la nouvelle méthode

### C.1 Dispositif

- Chaque configuration est un **pipeline complet** : signatures restreintes aux traits retenus, quinze arbres **reconstruits** sur les 50 exemples d'entraînement de chaque type, puis classement des 450 exemples de test par descente.
- Pour chaque configuration, le **plus proche voisin** sur les 750 feuilles est aussi classé. Il dit ce que valent les traits indépendamment de la descente, dont la phase B a montré le biais.
- Colonnes de référence : la méthode à seuil précédente, sur le même test, et l'article.
- **Expérience 3** (élagage) : n'a plus d'objet telle quelle. La comparaison entre (b), l'exhaustif sur les 1485 nœuds, et (c), la descente, en partie B.2, oppose elle aussi coût et qualité.

### C.2 Expérience 1 — apport de chaque trait (Tableau 2)

| configuration | P (%) | R (%) | F1 descente | prédictions internes | F1 plus proche voisin | F1 méthode à seuil | F1 article | taille moy. d'un côté de racine |
|---|---|---|---|---|---|---|---|---|
| **H** | 24,9 | 25,8 | **0,249** | 8 % | 0,443 | 0,443 | 0,653 | 569 |
| **H+SST** | 25,0 | 25,3 | **0,234** | 7 % | 0,473 | 0,471 | 0,691 | 587 |
| **H+TRT** | 24,1 | 20,2 | **0,140** | 4 % | 0,573 | 0,514 | 0,767 | 655 |
| **H+TRT+SST** | 31,0 | 27,6 | **0,219** | 9 % | 0,585 | 0,597 | 0,772 | 673 |

- De H seul à la configuration complète : descente −0,031, plus proche voisin +0,142, méthode à seuil +0,154, article +0,119.
- L'ordre des configurations de l'article est **reproduit par le plus proche voisin**, et **pas par la descente** : ses écarts entre configurations reflètent le biais de B.7 plus que la valeur des traits.
- La dernière colonne donne la taille moyenne d'un côté de racine : chaque trait ajouté élargit les nœuds lourds, pas les feuilles.

### C.3 Expérience 2 — trait de définitude (Tableau 4)

Deux symboles sont ajoutés à la signature de B : `DEF:Det` ou `DEF:NoDet`, et `DEF:Def` ou `DEF:NoDef`. Ils dépendent de la ligne et non du terme. Les deux lignes « sans morpho » retirent les annotations `DET`/`NODET` que JDM porte déjà, pour isoler ce que notre trait apporte.

| configuration | P (%) | R (%) | F1 descente | prédictions internes | F1 plus proche voisin | F1 méthode à seuil | F1 article | taille moy. d'un côté de racine |
|---|---|---|---|---|---|---|---|---|
| **H+TRT+SST** | 31,0 | 27,6 | **0,219** | 9 % | 0,585 | 0,597 | 0,772 | 673 |
| **H+TRT+SST sans morpho** | 26,1 | 26,2 | **0,201** | 8 % | 0,585 | 0,591 | — | 673 |
| **H+TRT+SST+DEF** | 27,3 | 22,2 | **0,174** | 10 % | 0,621 | 0,570 | 0,795 | 674 |
| **H+TRT+SST sans morpho +DEF** | 30,0 | 24,4 | **0,197** | 8 % | 0,614 | 0,566 | — | 674 |

- Définitude ajoutée aux annotations de JDM : descente −0,045, plus proche voisin +0,036 (article +0,023, méthode à seuil −0,027).
- Annotations morphologiques de JDM retirées : descente −0,017, plus proche voisin =.
- Notre trait seul, annotations de JDM retirées : descente −0,004, plus proche voisin +0,029.

### C.4 Contrôle de cohérence

La configuration H+TRT+SST reconstruit ses signatures depuis la collecte. Elles sont **identiques** à celles du fichier de signatures, et son F1 de descente (0,219) **égale** celui de la phase B.
<!-- fin C -->
