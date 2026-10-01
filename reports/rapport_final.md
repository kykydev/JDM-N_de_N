# Évaluation finale : somme · arbre · descente

Configuration figée en validation croisée, évaluée une seule fois sur les 450 exemples de test.

## 1. Configuration et protocole

- **Configuration** : `somme` · `arbre` · `descente`, choisie en validation croisée (`rapport_grille.md`). Aucune configuration de contrôle n'est évaluée ici.
- **Signatures : les BINAIRES**, celles de `data/signatures/` (`H 20 · binaire · T0 · TRT tous · SST toutes`) — chaque symbole présent vaut 1, et le terme lui-même figure dans sa signature, sans préfixe. Ce rapport évalue **cette seule représentation** sur le test. Les **signatures retenues** depuis en validation croisée (`H 20 · jdm · T2 · TRT tous · SST toutes`, `rapport_signatures_variantes.md`) sont évaluées sur le même test dans `rapport_final_signatures.md` ; les deux F1 sont mis en regard au §2.
- **Attention en comparant les deux** : elles diffèrent par **deux** réglages à la fois, les poids (`binaire` → `jdm`) et le symbole du terme (`T0` présent → `T2` retiré). L'écart de test ne s'attribue donc pas à la seule pondération ; sa décomposition est au §2 de `rapport_final_signatures.md`.
- **Arbres** : quinze, un par type, réappris sur les 750 exemples d'entraînement ; un nœud fusionné est la somme des vecteurs de comptes de ses enfants. Lien de construction : minimum des deux côtés.
- **Classification** : descente depuis la racine de chaque arbre, vers le meilleur enfant tant qu'il fait **strictement** mieux ; le meilleur nœud d'arrêt sur les quinze arbres donne le type. Score : formule 3, moyenne des deux côtés.
- **Test** : 450 exemples, 30 par type, **lus une seule fois**. Classement en 0,26 s. Ce rapport se reconstruit depuis `data/resultats/predictions_finales.json` sans relire le test.
- **Références** : article (Tableau 3), méthode à seuil (fusion « les deux » à 0,50, classification exhaustive) et plus proche voisin sur les feuilles, tous trois **relus** de résultats déjà obtenus sur ce même test.

## 2. Résultats

**F1 macro : 0,753** (précision 0,757, rappel 0,756, exactitude 75,6 %, 340 exemples justes sur 450).

|  | F1 macro sur les 450 exemples de test | écart avec ce rapport |
|---|---|---|
| **somme · arbre · descente, signatures binaires** (ce rapport) — `binaire · T0` | **0,753** | — |
| mêmes arbres, **signatures retenues** (`rapport_final_signatures.md`) — `jdm · T2` | 0,778 | −0,025 |
| article | 0,772 | −0,019 |
| méthode à seuil | 0,597 | +0,156 |
| plus proche voisin | 0,585 | +0,168 |

Les deux premières lignes sont la **même méthode** (somme · arbre · descente) sur le **même test**, et ne diffèrent que par la construction des signatures. L'écart de 0,025 n'est pas analysé ici : il mêle deux réglages et n'est pas établi statistiquement. Voir le **§2 de `rapport_final_signatures.md`**, qui le décompose.

### 2.1 Détail par type

Trié par F1. Les trois colonnes de référence sont des F1 ; « prédits » est le nombre de fois où le type est proposé, pour 30 attendus.

| type | prédits | P (%) | R (%) | F1 | F1 article | F1 seuil | F1 voisin | écart article |
|---|---|---|---|---|---|---|---|---|
| `r_has_property-1` | 29 | 96,6 | 93,3 | **0,95** | 0,59 | 0,76 | 0,70 | +0,36 |
| `r_social_tie` | 34 | 85,3 | 96,7 | **0,91** | 0,91 | 0,79 | 0,75 | −0,00 |
| `r_lieu` | 30 | 86,7 | 86,7 | **0,87** | 0,76 | 0,67 | 0,78 | +0,11 |
| `r_objet>matiere` | 24 | 95,8 | 76,7 | **0,85** | 0,80 | 0,68 | 0,57 | +0,05 |
| `r_has_causatif` | 33 | 78,8 | 86,7 | **0,83** | 0,69 | 0,53 | 0,60 | +0,14 |
| `r_lieu>origine` | 30 | 80,0 | 80,0 | **0,80** | 0,92 | 0,72 | 0,69 | −0,12 |
| `r_processus_patient` | 31 | 77,4 | 80,0 | **0,79** | 0,75 | 0,69 | 0,54 | +0,04 |
| `r_processus>instr-1` | 32 | 75,0 | 80,0 | **0,77** | 0,78 | 0,61 | 0,62 | −0,01 |
| `r_own-1` | 36 | 66,7 | 80,0 | **0,73** | 0,64 | 0,54 | 0,45 | +0,09 |
| `r_processus_agent` | 35 | 65,7 | 76,7 | **0,71** | 0,81 | 0,50 | 0,47 | −0,10 |
| `r_quantificateur` | 27 | 74,1 | 66,7 | **0,70** | 0,81 | 0,57 | 0,47 | −0,11 |
| `r_topic` | 31 | 64,5 | 66,7 | **0,66** | 0,76 | 0,41 | 0,40 | −0,10 |
| `r_depict` | 29 | 62,1 | 60,0 | **0,61** | 0,80 | 0,66 | 0,78 | −0,19 |
| `r_holo` | 29 | 62,1 | 60,0 | **0,61** | 0,82 | 0,35 | 0,45 | −0,21 |
| `r_product_of` | 20 | 65,0 | 43,3 | **0,52** | 0,74 | 0,48 | 0,50 | −0,22 |
| **macro** |  | 75,7 | 75,6 | **0,753** | 0,772 | 0,597 | 0,585 | −0,019 |

Le F1 dépasse celui de l'article pour 6 types sur 15.

## 3. Matrice de confusion

Lignes : type attendu. Colonnes : type prédit, numérotés comme les lignes. Aussi écrite dans `data/resultats/matrice_confusion_finale.csv`.

| attendu \ prédit | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1. `r_depict` | **18** | · | · | 1 | · | · | · | 2 | 2 | 1 | 3 | 1 | · | 1 | 1 |
| 2. `r_has_causatif` | 2 | **26** | · | · | · | · | · | · | · | · | 1 | · | · | · | 1 |
| 3. `r_has_property-1` | · | 2 | **28** | · | · | · | · | · | · | · | · | · | · | · | · |
| 4. `r_holo` | 6 | · | · | **18** | · | · | · | · | 2 | · | · | · | 1 | 1 | 2 |
| 5. `r_lieu` | · | · | · | · | **26** | 3 | · | 1 | · | · | · | · | · | · | · |
| 6. `r_lieu>origine` | 1 | · | · | · | 3 | **24** | · | · | · | · | · | 1 | · | 1 | · |
| 7. `r_objet>matiere` | · | · | · | 2 | · | · | **23** | 1 | 1 | · | · | 1 | 1 | · | 1 |
| 8. `r_own-1` | · | · | · | 1 | · | · | · | **24** | · | · | · | 2 | 2 | 1 | · |
| 9. `r_processus>instr-1` | · | 1 | · | 3 | · | · | · | · | **24** | · | · | · | 2 | · | · |
| 10. `r_processus_agent` | 1 | 2 | 1 | · | · | · | · | · | · | **23** | 2 | · | · | · | 1 |
| 11. `r_processus_patient` | · | · | · | · | · | · | · | · | · | 6 | **24** | · | · | · | · |
| 12. `r_product_of` | 1 | · | · | 1 | · | 3 | · | 7 | · | 3 | · | **13** | · | · | 2 |
| 13. `r_quantificateur` | · | 1 | · | 2 | · | · | 1 | 1 | · | 1 | · | 1 | **20** | · | 3 |
| 14. `r_social_tie` | · | · | · | · | · | · | · | · | · | · | · | 1 | · | **29** | · |
| 15. `r_topic` | · | 1 | · | 1 | 1 | · | · | · | 3 | 1 | 1 | · | 1 | 1 | **20** |

Confusions les plus fréquentes : `r_product_of` → `r_own-1` (7), `r_holo` → `r_depict` (6), `r_processus_patient` → `r_processus_agent` (6), `r_depict` → `r_processus_patient` (3), `r_lieu` → `r_lieu>origine` (3), `r_lieu>origine` → `r_lieu` (3).

## 4. La descente

- **Part des prédictions faites par une racine** : 50,9 %.
- **Poids relatif moyen du nœud gagnant** : 0,97 (poids du nœud divisé par le nombre d'exemples de son type ; 1 = tout le type, 0,02 = une feuille). Sur les 6750 descentes, tous arbres confondus : 0,98.
- **Profondeur d'arrêt moyenne** (racine = 0) : 1,0 pour les prédictions.
- **Calculs de score par exemple** : 66,0 en moyenne, 113 au plus.

### 4.1 Où la descente s'arrête

| nœud d'arrêt de la prédiction | prédictions | part | justes (exactitude) |
|---|---|---|---|
| racine | 229 | 50,9 % | 182 (79,5 %) |
| nœud interne | 217 | 48,2 % | 156 (71,9 %) |
| feuille | 4 | 0,9 % | 2 (50,0 %) |

**Profondeur d'arrêt** (racine = 0) :

| profondeur | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 11 | 12 | 14 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| prédictions | 229 | 115 | 47 | 33 | 9 | 4 | 6 | 4 | 1 | 0 | 1 | 0 | 1 |
| toutes les descentes | 4120 | 1565 | 581 | 258 | 84 | 45 | 45 | 34 | 8 | 6 | 1 | 1 | 2 |

### 4.2 Les types où la descente dépasse la racine

Une prédiction est comptée dans le type qu'elle **propose**. « justes » : parmi les prédictions de ce type qui s'arrêtent sous la racine, celles où le type attendu était bien celui-là. Les exemples sont les plus profonds (jusqu'à 4 par type).

| type prédit | prédictions | dont sous la racine | justes | profondeur max |
|---|---|---|---|---|
| `r_social_tie` | 34 | 26 | 22 (85 %) | 4 |
| `r_own-1` | 36 | 20 | 14 (70 %) | 4 |
| `r_has_property-1` | 29 | 20 | 19 (95 %) | 6 |
| `r_depict` | 29 | 17 | 12 (71 %) | 11 |
| `r_lieu>origine` | 30 | 17 | 11 (65 %) | 3 |
| `r_processus_agent` | 35 | 16 | 7 (44 %) | 8 |
| `r_processus_patient` | 31 | 14 | 13 (93 %) | 3 |
| `r_topic` | 31 | 14 | 10 (71 %) | 7 |
| `r_lieu` | 30 | 14 | 14 (100 %) | 5 |
| `r_holo` | 29 | 13 | 5 (38 %) | 14 |
| `r_processus>instr-1` | 32 | 12 | 7 (58 %) | 3 |
| `r_has_causatif` | 33 | 12 | 10 (83 %) | 7 |
| `r_product_of` | 20 | 12 | 7 (58 %) | 6 |
| `r_quantificateur` | 27 | 8 | 2 (25 %) | 4 |
| `r_objet>matiere` | 24 | 6 | 5 (83 %) | 2 |

- `r_social_tie` : « uniforme du pilote » (poids 46, prof. 4, attendu `r_own-1`) ; « berger d'Anatolie » (poids 47, prof. 3, attendu `r_lieu>origine`) ; « marchand de journaux » (poids 47, prof. 3, attendu `r_topic`) ; « secrétaire du notaire » (poids 47, prof. 3)
- `r_own-1` : « passeport du diplomate » (poids 46, prof. 4) ; « matelas de mousse » (poids 47, prof. 3, attendu `r_objet>matiere`) ; « barque du passeur » (poids 48, prof. 2) ; « manteau de l'invité » (poids 48, prof. 2)
- `r_has_property-1` : « franchise de l'ami » (poids 44, prof. 6) ; « simplicité de la méthode » (poids 45, prof. 5) ; « impatience du client » (poids 46, prof. 4) ; « rires des enfants » (poids 46, prof. 4, attendu `r_processus_agent`)
- `r_depict` : « plan d'un quartier » (poids 38, prof. 11) ; « dessin d'une maison » (poids 44, prof. 5) ; « gravure de l'éruption » (poids 45, prof. 4) ; « carte d'un archipel » (poids 46, prof. 3)
- `r_lieu>origine` : « maté d'Argentine » (poids 46, prof. 3) ; « muraille de Chine » (poids 46, prof. 3, attendu `r_lieu`) ; « yaourt de la laiterie » (poids 46, prof. 3, attendu `r_product_of`) ; « ananas de Hawaï » (poids 47, prof. 2)
- `r_processus_agent` : « ferrage du cheval » (feuille, prof. 8, attendu `r_processus_patient`) ; « commentaire du journaliste » (poids 42, prof. 7) ; « sauvegarde des données » (poids 42, prof. 7, attendu `r_processus_patient`) ; « creusement de la taupe » (poids 45, prof. 4)
- `r_processus_patient` : « amarrage du bateau » (poids 46, prof. 3) ; « embouteillage du vin » (poids 46, prof. 3) ; « moulage d'une statue » (poids 46, prof. 3, attendu `r_depict`) ; « écaillage du poisson » (poids 46, prof. 3)
- `r_topic` : « poème d'amour » (poids 43, prof. 7) ; « album du groupe » (poids 44, prof. 6, attendu `r_product_of`) ; « couverture du livre » (poids 44, prof. 6, attendu `r_holo`) ; « agence de publicité » (poids 47, prof. 3)
- `r_lieu` : « abbaye du Mont-Saint-Michel » (poids 45, prof. 5) ; « jardins de Villandry » (poids 47, prof. 3) ; « bidonvilles de Nairobi » (poids 48, prof. 2) ; « collines du Rwanda » (poids 48, prof. 2)
- `r_holo` : « salon de l'automobile » (poids 36, prof. 14, attendu `r_topic`) ; « essoreuse de salade » (poids 44, prof. 6, attendu `r_processus>instr-1`) ; « manche d'os » (poids 46, prof. 4, attendu `r_objet>matiere`) ; « maquette d'un avion » (poids 47, prof. 3, attendu `r_depict`)
- `r_processus>instr-1` : « film d'une évasion » (poids 47, prof. 3, attendu `r_depict`) ; « verre de dégustation » (poids 47, prof. 3) ; « vis d'assemblage » (poids 47, prof. 3) ; « brochure de prévention » (poids 48, prof. 2, attendu `r_topic`)
- `r_has_causatif` : « ennui du confinement » (poids 41, prof. 7) ; « cicatrice de l'opération » (poids 44, prof. 4) ; « sanctions de la fraude » (poids 45, prof. 3) ; « absurdité de la situation » (poids 48, prof. 2, attendu `r_has_property-1`)
- `r_product_of` : « chocolat du chocolatier » (poids 44, prof. 6) ; « ordinateur du développeur » (poids 44, prof. 6, attendu `r_own-1`) ; « dessin de l'illustrateur » (poids 45, prof. 5) ; « farine du meunier » (poids 47, prof. 3)
- `r_quantificateur` : « louche de service » (poids 46, prof. 4, attendu `r_processus>instr-1`) ; « lanterne de papier » (poids 47, prof. 3, attendu `r_objet>matiere`) ; « sacoche du médecin » (poids 47, prof. 3, attendu `r_own-1`) ; « sonde de température » (poids 47, prof. 3, attendu `r_processus>instr-1`)
- `r_objet>matiere` : « monture de titane » (poids 48, prof. 2) ; « bijou de corail » (poids 49, prof. 1) ; « galette de sarrasin » (poids 49, prof. 1) ; « mosaïque de céramique » (poids 49, prof. 1)

## 5. Analyse des cas d'échec

110 erreurs sur 450 exemples (méthode à seuil : 180). Mêmes détecteurs que `rapport_evaluation.md` ; chaque erreur reçoit une cause unique par ordre de priorité, du plus spécifique au plus général :

`défaut de connaissance` → `dispersion morphologique` → `classe multiple` → `polysémie` → `autre`

| cause | attribution exclusive | part des erreurs | présence (non exclusive) |
|---|---|---|---|
| défaut de connaissance | 0 | 0,0 % | 0 |
| dispersion morphologique | 4 | 3,6 % | 4 |
| classe multiple | 82 | 74,5 % | 85 |
| polysémie | 23 | 20,9 % | 96 |
| autre | 1 | 0,9 % | 1 |

### 5.1 Hypothèse : le profil moyen d'un type dilue la polysémie

**Part de la polysémie parmi les erreurs** : 20,9 % (23 sur 110) contre 57,8 % pour la méthode à seuil. Elle baisse.

Cette part est fragile : la polysémie est la dernière cause dans l'ordre de priorité, donc sa part est un **résidu** — elle change dès que les autres causes changent, sans que la polysémie y soit pour rien. Le test direct est le taux d'erreur selon que l'exemple contient ou non un terme polysémique (A ou B avec au moins deux raffinements de sens dans JDM) :

|  | exemples polysémiques | exemples sans terme polysémique | écart |
|---|---|---|---|
| somme · arbre · descente | 96 / 371 (25,9 %) | 14 / 79 (17,7 %) | +0,082 |
| méthode à seuil | 152 / 371 (41,0 %) | 28 / 79 (35,4 %) | +0,055 |

Lecture : l'écart entre exemples polysémiques et autres **ne se resserre pas** (+0,082 contre +0,055) : l'hypothèse n'est pas confirmée par ce test. Le détecteur reste un indice, pas une preuve : un terme à raffinements peut être bien classé, et un terme sans raffinement peut être ambigu. Les effectifs sont faibles côté « sans terme polysémique » (79 exemples), ce qui rend l'écart peu précis.

## 6. Les dix erreurs les plus confiantes

Erreurs au score gagnant le plus élevé : le système s'est trompé avec assurance. Ce sont celles qui coûtent le plus cher, et celles qui renseignent le mieux sur ce qui manque à la base de connaissances.

**Attention à ce que « confiant » veut dire ici.** Le score absolu est haut quand les signatures sont riches, pas quand un type se détache : les scores des trois premiers types tiennent le plus souvent dans quelques centièmes. Pour 8 de ces dix erreurs le type attendu est à moins de 5 % du gagnant, et il est 2ᵉ pour 4. Ce sont donc surtout des égalités perdues, pas des erreurs assurées.

| syntagme | attendu | prédit | score gagnant | score du bon type | nœud d'arrêt | cause |
|---|---|---|---|---|---|---|
| « ordinateur du développeur » | `r_own-1` | `r_product_of` | 0,783 | 0,778 | poids 44, prof. 6 | classe multiple |
| « article du journaliste » | `r_product_of` | `r_own-1` | 0,766 | 0,754 | poids 50, prof. 0 | classe multiple |
| « rapport de l'expert » | `r_product_of` | `r_processus_agent` | 0,757 | 0,727 | poids 47, prof. 2 | classe multiple |
| « traduction de l'interprète » | `r_product_of` | `r_processus_agent` | 0,755 | 0,691 | poids 48, prof. 1 | polysémie |
| « plat du cuisinier » | `r_product_of` | `r_own-1` | 0,746 | 0,743 | poids 49, prof. 1 | classe multiple |
| « couverture du livre » | `r_holo` | `r_topic` | 0,737 | 0,719 | poids 44, prof. 6 | classe multiple |
| « bronzage de l'été » | `r_has_causatif` | `r_processus_patient` | 0,736 | 0,716 | poids 50, prof. 0 | classe multiple |
| « album du groupe » | `r_product_of` | `r_topic` | 0,732 | 0,667 | poids 44, prof. 6 | polysémie |
| « scène du film » | `r_holo` | `r_topic` | 0,725 | 0,695 | poids 49, prof. 1 | classe multiple |
| « salon de thé » | `r_topic` | `r_quantificateur` | 0,725 | 0,719 | poids 48, prof. 2 | classe multiple |

1. **« ordinateur du développeur »** — `r_own-1` contre `r_product_of`, 0,6 % d'écart, le bon type est 2ᵉ. Le B est une profession, et l'entraînement en donne aux deux types (`musicien`, `banquier` possèdent ; `boulanger`, `écrivain` produisent). Le profil de B ne départage pas ; un développeur possède un ordinateur et en écrit les programmes, seul le A (2 raffinements) pourrait trancher, et il ne le fait pas.
2. **« article du journaliste »** — La même paire, à l'envers : `r_product_of` attendu, `r_own-1` prédit, 1,7 % d'écart. « article » a 6 raffinements de sens (écrit de presse, pièce de marchandise…) : son profil mélange des choses produites et des choses possédées. Confusion la plus fréquente du test (`r_product_of` → `r_own-1`, 7 cas).
3. **« rapport de l'expert »** — `r_product_of` est 3ᵉ, à égalité avec `r_own-1` (0,727) derrière `r_processus_agent` (3,9 % d'écart). « rapport » a 14 raffinements de sens, le record de la liste. Lecture défendable : « le rapport de l'expert » comme acte de rapporter est un processus dont l'expert est l'agent ; le corpus retient le résultat, le texte.
4. **« traduction de l'interprète »** — Ici l'écart est net (8,5 %, le bon type est 4ᵉ) et pas du tout un quasi-ex aequo. Nom d'action : « traduction » désigne le geste autant que son résultat, et sa signature est celle d'un processus. Ambiguïté classique action/résultat, que le corpus tranche du côté résultat.
5. **« plat du cuisinier »** — 0,3 % d'écart entre `r_own-1` et `r_product_of` : une égalité quasi parfaite. « plat » a 12 raffinements (mets, ustensile, adjectif…) et « cuisinier » est une profession, comme dans « ordinateur du développeur ». Le plat que cuisine le cuisinier et le plat qu'il possède sont deux lectures que le texte ne distingue pas.
6. **« couverture du livre »** — `r_holo` attendu, `r_topic` prédit, le bon type est 3ᵉ à 2,4 %. « couverture » a 12 raffinements (celle d'un livre, d'un lit, médiatique, d'assurance…) et le côté B porte 88 symboles, l'une des signatures les plus riches. Les deux exemples `r_holo` → `r_topic` de cette liste ont pour B une œuvre (livre, film).
7. **« bronzage de l'été »** — Trois types à moins de 3 % : `r_processus_patient` (gagnant), `r_processus_agent`, `r_has_causatif` (attendu). Les signatures sont les plus petites de la liste (41 et 51 symboles) et « bronzage » n'a aucun raffinement : peu de matière pour trancher. La descente s'arrête à la racine de `r_processus_patient` (poids 50).
8. **« album du groupe »** — La plus nette des dix erreurs de sens : le bon type est **6ᵉ**, à 9,0 % du gagnant. « groupe » a 10 raffinements de sens (ensemble musical, groupe de personnes, groupe chimique…), et la signature qui en résulte ne ressemble pas au créateur que suppose `r_product_of` (`boulanger`, `écrivain`). Vraisemblablement un cas de polysémie du B, la cause que le détecteur lui attribue.
9. **« scène du film »** — `r_holo` attendu, `r_topic` prédit, 4,1 % d'écart, même schéma que « couverture du livre » : le B est une œuvre, et dans l'entraînement `r_topic` a des B de genre ou de discipline (`roman de science-fiction`, `film d'aventure`). Une scène est une partie du film, mais la signature de « film » attire vers le thème.
10. **« salon de thé »** — Composé lexicalisé, étiqueté `r_topic` (comme `salon de coiffure` à l'entraînement). Le B « thé » est une boisson, le B typique de `r_quantificateur` (`tasse de café`, `verre de lait`), et l'écart est de 0,9 %. Seule une entrée JDM du syntagme entier lèverait l'ambiguïté ; les signatures de A et de B, séparément, ne le peuvent pas.

## 7. Sorties écrites

- `data/resultats/predictions_finales.json` : pour chaque exemple, le chemin complet de la descente dans l'arbre gagnant, la réponse des quinze arbres et le nœud d'arrêt.
- `data/resultats/matrice_confusion_finale.csv` : la matrice de confusion.
- `data/modeles/arbres_somme.json` : les quinze arbres, 1485 nœuds.
