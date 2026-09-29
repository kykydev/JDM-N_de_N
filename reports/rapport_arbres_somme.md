# Clustering hiérarchique et classification par descente

<!-- partie A -->
## A. Construction des arbres

### A.1 Dispositif

- **15 arbres**, un par type : deux règles de types différents ne fusionnent jamais (note 2 de l'article).
- **750 feuilles**, les 50 exemples d'entraînement de chaque type. Le calibrage n'a plus d'objet : il n'y a plus de seuil à choisir.
- **1485 nœuds** stockés, feuilles comprises, dans `data/modeles/arbres_somme.json`.
- **Lien** : `min( sim(sLi, sLj), sim(sRi, sRj) )`, cosinus sur ensembles. Le minimum exige que les deux côtés se ressemblent.
- **Ex aequo** : départagés par l'ordre d'apparition dans le corpus.
- **Aucun seuil** : on fusionne jusqu'à la racine.
- **Coût** : 36015 liens calculés en tout — la demi-matrice initiale, puis une seule ligne par fusion. Recalculer toute la matrice à chaque fusion en aurait coûté de l'ordre de 312375. Durée : 0,5 s.

### A.2 Les quinze arbres

- **profondeur** : celle de la feuille la plus profonde, la racine étant à 0. Un arbre parfaitement équilibré de 50 feuilles a une profondeur de 6, un peigne pur de 49.
- **hauteur** : valeur du lien au moment de la fusion. Celle de la racine est le lien de la dernière fusion ; médiane et maximum portent sur les 49 fusions du type.
- **inversions** : nœuds dont la hauteur dépasse celle d'un de leurs enfants internes ; « écart max » est le plus grand dépassement.
- **plus gros enfant** : poids du plus lourd des deux enfants de la racine. 25 / 50 est l'équilibre parfait, 49 / 50 le peigne.
- **greffes** : fusions d'une feuille isolée avec un groupe déjà formé, sur les 49 fusions du type.

| type | profondeur | hauteur racine | hauteur méd. | hauteur max | inversions | écart max | \|sL\| / \|sR\| racine | plus gros enfant | greffes |
|---|---|---|---|---|---|---|---|---|---|
| `r_depict` | 47 | 0,266 | 0,585 | 0,678 | 15 | 0,037 | 701 / 860 | 49 / 50 | 44 / 49 |
| `r_has_causatif` | 47 | 0,467 | 0,641 | 0,691 | 16 | 0,025 | 542 / 813 | 49 / 50 | 46 / 49 |
| `r_has_property-1` | 42 | 0,421 | 0,637 | 0,699 | 16 | 0,048 | 530 / 753 | 49 / 50 | 46 / 49 |
| `r_holo` | 49 | 0,446 | 0,585 | 0,684 | 15 | 0,055 | 717 / 759 | 49 / 50 | 48 / 49 |
| `r_lieu` | 41 | 0,340 | 0,606 | 0,669 | 17 | 0,038 | 643 / 479 | 49 / 50 | 42 / 49 |
| `r_lieu>origine` | 42 | 0,338 | 0,600 | 0,680 | 14 | 0,040 | 682 / 442 | 49 / 50 | 42 / 49 |
| `r_objet>matiere` | 47 | 0,319 | 0,628 | 0,673 | 17 | 0,031 | 679 / 615 | 49 / 50 | 44 / 49 |
| `r_own-1` | 49 | 0,376 | 0,633 | 0,700 | 13 | 0,033 | 737 / 469 | 49 / 50 | 48 / 49 |
| `r_processus>instr-1` | 48 | 0,414 | 0,617 | 0,691 | 15 | 0,037 | 680 / 724 | 49 / 50 | 46 / 49 |
| `r_processus_agent` | 47 | 0,271 | 0,632 | 0,707 | 16 | 0,036 | 709 / 659 | 48 / 50 | 44 / 49 |
| `r_processus_patient` | 47 | 0,394 | 0,665 | 0,714 | 14 | 0,060 | 647 / 787 | 49 / 50 | 44 / 49 |
| `r_product_of` | 47 | 0,449 | 0,628 | 0,708 | 12 | 0,056 | 806 / 537 | 49 / 50 | 46 / 49 |
| `r_quantificateur` | 40 | 0,300 | 0,616 | 0,713 | 15 | 0,051 | 607 / 766 | 49 / 50 | 40 / 49 |
| `r_social_tie` | 48 | 0,328 | 0,640 | 0,685 | 13 | 0,014 | 490 / 683 | 49 / 50 | 46 / 49 |
| `r_topic` | 49 | 0,471 | 0,628 | 0,712 | 16 | 0,049 | 845 / 822 | 49 / 50 | 48 / 49 |

### A.3 Synthèse

- **Inversions** : 224 nœuds internes sur 735 (30,5 %), dans 15 arbres sur 15. Écart maximal observé : 0,060.
- **Profondeur** : de 40 à 49, médiane 47.
- **Forme** : le plus gros enfant de la racine pèse de 96 % à 98 % des feuilles, et 15 racines sur 15 sont à 90 % ou plus. Un peigne pur de 50 feuilles a une profondeur de 49, un arbre équilibré de 6 : les nôtres vont de 40 à 49, et 674 fusions sur 735 (91,7 %) sont des greffes d'une feuille isolée sur un groupe déjà formé. **Ce sont des peignes.**
- **Hauteur de la racine** : de 0,266 à 0,471, médiane 0,376. C'est ce que valent, au pire des deux côtés, les deux moitiés d'un type l'une pour l'autre.

### A.4 Isolats de racine

En descendant de la racine vers l'enfant lourd, on détache tant que l'autre enfant pèse au plus 3 exemples. Ce sont les exemples que leur type n'a su rapprocher de personne : ils ne rejoignent l'arbre qu'à la toute fin, par un lien très faible.

| type | lien de rattachement | exemples détachés |
|---|---|---|
| `r_depict` | 0,266 | « échographie d'un fœtus » |
| `r_depict` | 0,465 | « vignette d'une scène », « fusain d'un arbre » |
| `r_depict` | 0,471 | « totem d'un aigle » |
| `r_depict` | … | 44 autres rattachements, jusqu'au cœur du noyau |
| `r_has_causatif` | 0,467 | « pertes du krach » |
| `r_has_causatif` | 0,488 | « retombées du scandale » |
| `r_has_causatif` | 0,485 | « cloques de la brûlure », « avaries de la tempête », « flaques de la pluie » |
| `r_has_causatif` | … | 44 autres rattachements, jusqu'au cœur du noyau |
| `r_has_property-1` | 0,421 | « entêtement de la mule » |
| `r_has_property-1` | 0,472 | « étroitesse de la ruelle » |
| `r_has_property-1` | 0,482 | « rapidité du guépard » |
| `r_has_property-1` | … | 18 autres rattachements, jusqu'au cœur du noyau |
| `r_holo` | 0,446 | « touche de l'accordéon » |
| `r_holo` | 0,468 | « bosse du chameau » |
| `r_holo` | 0,475 | « voile de la goélette » |
| `r_holo` | … | 46 autres rattachements, jusqu'au cœur du noyau |
| `r_lieu` | 0,340 | « oliveraies de Toscane » |
| `r_lieu` | 0,361 | « forêt de Brocéliande » |
| `r_lieu` | 0,453 | « rizières de Bali » |
| `r_lieu` | … | 30 autres rattachements, jusqu'au cœur du noyau |
| `r_lieu>origine` | 0,338 | « or du Klondike » |
| `r_lieu>origine` | 0,397 | « melons de Cavaillon », « émeraudes de Zambie » |
| `r_lieu>origine` | 0,407 | « caviar de la Caspienne » |
| `r_lieu>origine` | … | 27 autres rattachements, jusqu'au cœur du noyau |
| `r_objet>matiere` | 0,319 | « veste de tweed » |
| `r_objet>matiere` | 0,379 | « bonhomme de neige » |
| `r_objet>matiere` | 0,426 | « pommeau de jade » |
| `r_objet>matiere` | … | 44 autres rattachements, jusqu'au cœur du noyau |
| `r_own-1` | 0,376 | « jardin de la retraitée » |
| `r_own-1` | 0,489 | « couteaux du cuisinier » |
| `r_own-1` | 0,544 | « jumelles de l'ornithologue » |
| `r_own-1` | … | 46 autres rattachements, jusqu'au cœur du noyau |
| `r_processus>instr-1` | 0,414 | « pompe de relevage » |
| `r_processus>instr-1` | 0,460 | « code du coffre » |
| `r_processus>instr-1` | 0,482 | « broyeur de déchets » |
| `r_processus>instr-1` | … | 45 autres rattachements, jusqu'au cœur du noyau |
| `r_processus_agent` | 0,271 | « grève des cheminots », « récolte des vendangeurs » |
| `r_processus_agent` | 0,310 | « migration des hirondelles » |
| `r_processus_agent` | 0,326 | « construction des maçons » |
| `r_processus_agent` | … | 44 autres rattachements, jusqu'au cœur du noyau |
| `r_processus_patient` | 0,394 | « taille des rosiers » |
| `r_processus_patient` | 0,499 | « repassage des chemises » |
| `r_processus_patient` | 0,589 | « nettoyage des vitres », « correction des copies » |
| `r_processus_patient` | … | 44 autres rattachements, jusqu'au cœur du noyau |
| `r_product_of` | 0,449 | « œuf de la poule » |
| `r_product_of` | 0,454 | « fresque du muraliste » |
| `r_product_of` | 0,467 | « perle de l'huître » |
| `r_product_of` | … | 44 autres rattachements, jusqu'au cœur du noyau |
| `r_quantificateur` | 0,300 | « douzaine d'œufs » |
| `r_quantificateur` | 0,465 | « botte de radis » |
| `r_quantificateur` | 0,485 | « bouquet de persil » |
| `r_quantificateur` | … | 25 autres rattachements, jusqu'au cœur du noyau |
| `r_social_tie` | 0,328 | « roi des Belges » |
| `r_social_tie` | 0,508 | « recteur de l'académie » |
| `r_social_tie` | 0,517 | « syndic de la copropriété » |
| `r_social_tie` | … | 45 autres rattachements, jusqu'au cœur du noyau |
| `r_topic` | 0,471 | « réforme des retraites » |
| `r_topic` | 0,475 | « dictionnaire de synonymes » |
| `r_topic` | 0,493 | « festival de jazz » |
| `r_topic` | … | 46 autres rattachements, jusqu'au cœur du noyau |

15 arbres sur 15 ont au moins un isolat, 657 exemples en tout sur 750. Une fois détachés, les noyaux pèsent de 1 à 29 exemples.
<!-- fin A -->
