# Variantes de définitude

Généré par `src/corpus_variants.py` (graine `random.Random(42)`). Source : `data/corpus/raw/` (inchangé). Sortie : `data/corpus/variants/`.

Transformations : `du X` → `d'un X`, `de la X` → `d'une X` ; pour `r_holo` seulement, `du X` peut aussi devenir `de X` (tirage 50/50). Lignes éligibles : découpage non ambigu, préposition `du` ou `de la`, B sans majuscule initiale. `de l'` est exclu (genre non déductible du déterminant), `des` aussi (pluriel).

Cible : 6 lignes en train et 4 en test par type, soit 10/80 = 12.5 %.

Exclusions manuelles (`EXCLUDED`) : 9 — « abattage du bétail », « directeur du personnel », « dommages de la grêle », « inauguration du maire », « obésité de la malbouffe », « patine du temps », « tamisage de la farine », « traite du fermier », « émeutes de la faim ».

Types recopiés sans modification : `r_depict`, `r_lieu`, `r_lieu>origine`, `r_objet>matiere`, `r_quantificateur`, `r_topic`.

## Synthèse

| relation | fichier | éligibles train | éligibles test | modifiées train | modifiées test | total | % |
|---|---|---|---|---|---|---|---|
| r_holo | corpus_r_holonymie | 39 | 28 | 6 | 4 | 10 | 12.5 |
| r_own-1 | corpus_r_own-1 | 42 | 22 | 6 | 4 | 10 | 12.5 |
| r_processus_agent | corpus_r_processus_agent | 28 | 19 | 6 | 4 | 10 | 12.5 |
| r_processus_patient | corpus_r_processus_patient | 31 | 16 | 6 | 4 | 10 | 12.5 |
| r_product_of | corpus_r_product_of | 39 | 24 | 6 | 4 | 10 | 12.5 |
| r_social_tie | corpus_r_social_tie | 30 | 22 | 6 | 4 | 10 | 12.5 |
| r_has_property-1 | corpus_r_has_property-1 | 41 | 23 | 6 | 4 | 10 | 12.5 |
| r_has_causatif | corpus_r_has_causatif | 30 | 18 | 6 | 4 | 10 | 12.5 |

## r_holo

Fichier `corpus_r_holonymie.csv`, 10 ligne(s) modifiée(s).

| ligne | split | avant | après |
|---|---|---|---|
| 3 | train | guidon du vélo | guidon de vélo |
| 13 | train | serrure du coffre | serrure de coffre |
| 14 | train | lame du couteau | lame d'un couteau |
| 21 | train | moteur du bateau | moteur de bateau |
| 22 | train | gouvernail du navire | gouvernail d'un navire |
| 24 | train | voile de la goélette | voile d'une goélette |
| 60 | test | objectif de la caméra | objectif d'une caméra |
| 62 | test | quai de la gare | quai d'une gare |
| 65 | test | arche du viaduc | arche d'un viaduc |
| 78 | test | semelle de la chaussure | semelle d'une chaussure |

## r_own-1

Fichier `corpus_r_own-1.csv`, 10 ligne(s) modifiée(s).

| ligne | split | avant | après |
|---|---|---|---|
| 1 | train | voiture du voisin | voiture d'un voisin |
| 25 | train | casque du motard | casque d'un motard |
| 37 | train | archet du violoniste | archet d'un violoniste |
| 40 | train | four du boulanger | four d'un boulanger |
| 41 | train | couteaux du cuisinier | couteaux d'un cuisinier |
| 45 | train | livres du professeur | livres d'un professeur |
| 56 | test | ordinateur du développeur | ordinateur d'un développeur |
| 58 | test | écouteurs du passager | écouteurs d'un passager |
| 62 | test | bague de la mariée | bague d'une mariée |
| 67 | test | tableaux du mécène | tableaux d'un mécène |

## r_processus_agent

Fichier `corpus_r_processus_agent.csv`, 10 ligne(s) modifiée(s).

| ligne | split | avant | après |
|---|---|---|---|
| 3 | train | opération du chirurgien | opération d'un chirurgien |
| 4 | train | concert du pianiste | concert d'un pianiste |
| 8 | train | sermon du curé | sermon d'un curé |
| 23 | train | numéro du clown | numéro d'un clown |
| 30 | train | diagnostic du médecin | diagnostic d'un médecin |
| 35 | train | livraison du coursier | livraison d'un coursier |
| 59 | test | saut du kangourou | saut d'un kangourou |
| 61 | test | vol du bourdon | vol d'un bourdon |
| 63 | test | attaque du requin | attaque d'un requin |
| 78 | test | signature du notaire | signature d'un notaire |

## r_processus_patient

Fichier `corpus_r_processus_patient.csv`, 10 ligne(s) modifiée(s).

| ligne | split | avant | après |
|---|---|---|---|
| 7 | train | réparation du moteur | réparation d'un moteur |
| 11 | train | tonte de la pelouse | tonte d'une pelouse |
| 42 | train | restauration du tableau | restauration d'un tableau |
| 46 | train | relecture du manuscrit | relecture d'un manuscrit |
| 49 | train | annulation du concert | annulation d'un concert |
| 50 | train | report de la réunion | report d'une réunion |
| 59 | test | écaillage du poisson | écaillage d'un poisson |
| 60 | test | pétrissage de la pâte | pétrissage d'une pâte |
| 66 | test | salage du jambon | salage d'un jambon |
| 76 | test | installation du logiciel | installation d'un logiciel |

## r_product_of

Fichier `corpus_r_product_of.csv`, 10 ligne(s) modifiée(s).

| ligne | split | avant | après |
|---|---|---|---|
| 2 | train | tarte de la pâtissière | tarte d'une pâtissière |
| 3 | train | fromage du fromager | fromage d'un fromager |
| 12 | train | poème du poète | poème d'un poète |
| 16 | train | photographie du reporter | photographie d'un reporter |
| 18 | train | gravure du graveur | gravure d'un graveur |
| 20 | train | vase du potier | vase d'un potier |
| 60 | test | farine du meunier | farine d'un meunier |
| 63 | test | tableau du peintre | tableau d'un peintre |
| 65 | test | affiche du graphiste | affiche d'un graphiste |
| 66 | test | statue du fondeur | statue d'un fondeur |

## r_social_tie

Fichier `corpus_r_social_tie.csv`, 10 ligne(s) modifiée(s).

| ligne | split | avant | après |
|---|---|---|---|
| 1 | train | père de la mariée | père d'une mariée |
| 9 | train | fille du ministre | fille d'un ministre |
| 10 | train | veuve du soldat | veuve d'un soldat |
| 34 | train | délégué de la classe | délégué d'une classe |
| 41 | train | maire de la commune | maire d'une commune |
| 47 | train | bailleur du locataire | bailleur d'un locataire |
| 58 | test | allié du souverain | allié d'un souverain |
| 59 | test | complice du voleur | complice d'un voleur |
| 68 | test | disciple du maître | disciple d'un maître |
| 73 | test | interprète de la délégation | interprète d'une délégation |

## r_has_property-1

Fichier `corpus_r_has_property-1.csv`, 10 ligne(s) modifiée(s).

| ligne | split | avant | après |
|---|---|---|---|
| 10 | train | profondeur du puits | profondeur d'un puits |
| 15 | train | maladresse du stagiaire | maladresse d'un stagiaire |
| 18 | train | hauteur de la tour | hauteur d'une tour |
| 20 | train | souplesse du cuir | souplesse d'un cuir |
| 24 | train | rapidité du guépard | rapidité d'un guépard |
| 25 | train | rigueur du comptable | rigueur d'un comptable |
| 63 | test | docilité de la jument | docilité d'une jument |
| 72 | test | laideur du bâtiment | laideur d'un bâtiment |
| 77 | test | originalité du projet | originalité d'un projet |
| 80 | test | puissance de la machine | puissance d'une machine |

## r_has_causatif

Fichier `corpus_r_has_causatif.csv`, 10 ligne(s) modifiée(s).

| ligne | split | avant | après |
|---|---|---|---|
| 7 | train | fatigue du voyage | fatigue d'un voyage |
| 11 | train | symptômes de la grippe | symptômes d'une grippe |
| 30 | train | euphorie du succès | euphorie d'un succès |
| 32 | train | ampoules de la marche | ampoules d'une marche |
| 41 | train | incendies de la sécheresse | incendies d'une sécheresse |
| 46 | train | odeurs de la cuisson | odeurs d'une cuisson |
| 59 | test | remords de la trahison | remords d'une trahison |
| 63 | test | sanctions de la fraude | sanctions d'une fraude |
| 64 | test | incendie du court-circuit | incendie d'un court-circuit |
| 74 | test | conséquences de la crise | conséquences d'une crise |

