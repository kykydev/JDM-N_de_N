# Collecte brute des traits JDM

Généré par `src/jdm_collect.py` le 2026-09-20. API : `https://jdm-api.demo.lirmm.fr/v0`. Sortie : `data/collecte/termes_jdm.jsonl`, un enregistrement JSON par terme.

**Aucun seuil, aucune coupure, aucune exclusion de types n'est appliqué ici.** Seules les relations de poids ≤ 0 (niées dans JDM) sont écartées des traits, et leur nombre est conservé dans chaque enregistrement pour que ce choix même reste réversible. Le top 20 de H et l'exclusion des types TRT non sémantiques appartiennent à l'étape 3. Le corpus n'est modifié par aucun moyen.

## 1. Phase 1 : optimisation du payload de `/relations/to`

Cinq termes de profils contrastés : « animaux », très connecté (133 715 relations entrantes) ; « huées », rare (81) ; « discrétion », moyen (9 944) ; « Bordeaux », entité nommée (22 229) ; « Côte d'Ivoire », polylexical (4 683).

Chaque combinaison est comparée à la référence sur le multi-ensemble `type de relation -> nombre de relations entrantes de poids > 0`, c'est-à-dire exactement le trait TRT. Une combinaison qui change ce résultat est rejetée, même plus rapide.

| combinaison | octets (5 termes) | latence (s) | gain volume | gain latence | TRT identique |
|---|---|---|---|---|---|
| `référence (aucun paramètre)` | 23 661 137 | 38,40 | 0 % | 0 % | oui |
| `without_nodes=true` | 13 717 793 | 5,15 | 42 % | 87 % | oui |
| `relation_fields=[type]` | — | — | — | — | **500** sur 5/5 termes |
| `without_nodes=true + relation_fields=[type]` | — | — | — | — | **500** sur 5/5 termes |
| `without_nodes=true + relation_fields=[type] + min_weight=1` | — | — | — | — | **500** sur 5/5 termes |
| `without_nodes=true + relation_fields=[type,w]` | 4 258 803 | 2,30 | 82 % | 94 % | oui |
| `without_nodes=true + relation_fields=[type,w] + min_weight=1` | 3 522 152 | 2,19 | 85 % | 94 % | oui |

### Cause réelle des erreurs 500

`relation_fields=[type]` échoue **sans aucun `types_ids`**, sur les cinq termes. En isolant les champs un à un : `[w]`, `[type,w]`, `[node1,w]`, `[id,w]` et `[type,w,node1]` passent ; `[type]`, `[node1]`, `[id,type]`, `[type,node1]` et `[type,type]` renvoient 500. La règle n'est donc pas « `relation_fields` combiné à `types_ids` » comme le supposait la sonde, mais : **`relation_fields` doit contenir `w`**. Les trois combinaisons reposant sur `[type]` seul sont inexploitables — ce qui tombe bien, puisque le comptage « poids > 0 » du trait TRT a de toute façon besoin de `w`.

### Combinaison retenue : `without_nodes=true` + `relation_fields=[type,w]`, sans `min_weight`

`min_weight=1` ne rapporte que 3 points de volume et 0,3 % de latence de plus. Écarté pour deux raisons. D'abord, c'est un filtre serveur : il ne perd rien sur ces cinq termes (compteurs TRT strictement identiques), mais une relation de poids 0 < w < 1 ailleurs dans le corpus disparaîtrait silencieusement — vérifié sur cinq termes n'est pas garanti sur 1871. Sans lui, le filtre `w > 0` est appliqué côté client sur la même donnée que la référence : l'identité est acquise par construction, pas par échantillon. Ensuite, le principe de collecte brute : `min_weight=1` jette les relations niées, alors qu'en les gardant on consigne leur nombre par type et l'étape 3 pourra faire varier ce seuil sans recollecte.

Portée du gain : la sonde utilisait **déjà** ces paramètres sur `/relations/to`. Son estimation de 2,2 h et 0,9 Go les intègre donc ; les 82 % mesurés ici disent ce qu'aurait coûté la passe sans eux (≈ 5 Go de cache), ils ne la raccourcissent pas. La latence de cet endpoint est par ailleurs dominée par la charge du serveur, non par le payload : les mêmes paramètres ont donné 2,36 s de moyenne à la sonde et 1,0 s ici sur le terme le plus lourd (« animaux », 150 220 relations entrantes).

## 2. Couverture

Termes du corpus : **1871**. Trouvés dans JDM : **1869** (99,9 %). Absents : **2**.

Termes absents : « cacao de Côte », « diamants d'Afrique ».

Propositions de remplacement dans `reports/remplacements_proposes.csv` (le script propose, il n'applique jamais).

### Par rôle

Un terme jouant les deux rôles compte dans les deux lignes.

| rôle | termes | trouvés | couverture |
|---|---|---|---|
| A | 1034 | 1032 | 99,8 % |
| B | 1030 | 1030 | 100,0 % |

### Par type de relation

Un terme apparaissant sous plusieurs types compte dans chaque ligne.

| relation | termes | trouvés | couverture |
|---|---|---|---|
| `r_depict` | 130 | 130 | 100,0 % |
| `r_has_causatif` | 157 | 157 | 100,0 % |
| `r_has_property-1` | 160 | 160 | 100,0 % |
| `r_holo` | 158 | 158 | 100,0 % |
| `r_lieu` | 157 | 157 | 100,0 % |
| `r_lieu>origine` | 160 | 158 | 98,8 % |
| `r_objet>matiere` | 155 | 155 | 100,0 % |
| `r_own-1` | 159 | 159 | 100,0 % |
| `r_processus>instr-1` | 157 | 157 | 100,0 % |
| `r_processus_agent` | 159 | 159 | 100,0 % |
| `r_processus_patient` | 160 | 160 | 100,0 % |
| `r_product_of` | 158 | 158 | 100,0 % |
| `r_quantificateur` | 154 | 154 | 100,0 % |
| `r_social_tie` | 142 | 142 | 100,0 % |
| `r_topic` | 153 | 153 | 100,0 % |

## 3. Tailles brutes par trait

Sur les termes trouvés, sans aucune coupure.

| trait | min | médiane | max | total |
|---|---|---|---|---|
| \|H\| — hyperonymes r_isa, w > 0 | 0 | 26 | 396 | 76 807 |
| \|TRT\| — types de relations entrantes | 5 | 39 | 77 | — |
| \|SST\| — _INFO-SEM-*, w > 0 | 0 | 2 | 13 | 5 147 |
| \|SST\| hors annotations morphologiques | 0 | 2 | 11 | 5 003 |

Relations entrantes de poids > 0 par terme : min 14, médiane 5 468, max 588 426, total 31 251 965.

### Inventaire des annotations _INFO-SEM-*

Toutes sont conservées dans le JSONL. La colonne `morpho` est le drapeau que l'étape 3 pourra utiliser pour les inclure ou les exclure par configuration, sans recollecte (constante `SST_MORPHO` de `src/jdm_collect.py`).

| annotation | termes concernés | morpho |
|---|---|---|
| `PLACE` | 672 | non |
| `LIVING-BEING` | 615 | non |
| `THING-CONCRETE` | 546 | non |
| `PERS` | 516 | non |
| `ACTION` | 324 | non |
| `THING-ARTEFACT` | 275 | non |
| `PLACE-HUMAN` | 264 | non |
| `SUBST` | 196 | non |
| `PLACE-GEO` | 193 | non |
| `THING` | 162 | non |
| `NAMED-ENTITY` | 157 | non |
| `THING-ABSTR` | 153 | non |
| `PERS-FEM` | 131 | non |
| `PROPERTY-NAME` | 130 | non |
| `NODET` | 100 | **oui** |
| `PLACE-ABSTRACT` | 85 | non |
| `EVENT` | 80 | non |
| `EMOTION-RELATED` | 77 | non |
| `THING-NATURAL` | 68 | non |
| `ORGA` | 59 | non |
| `PERS-MASC` | 53 | non |
| `COLOR-RELATED` | 52 | non |
| `SET` | 51 | non |
| `PLACE-ANATOMICAL` | 45 | non |
| `DET` | 44 | **oui** |
| `QUANTIFIER` | 38 | non |
| `DOMAIN` | 17 | non |
| `TIME` | 11 | non |
| `ISA-CONCEPT` | 9 | non |
| `STATE` | 8 | non |
| `IMAGINARY` | 7 | non |
| `CARAC` | 6 | non |
| `PHENOMENA` | 2 | non |
| `QUANTIFIER+THING` | 1 | non |

## 4. Traits vides et diagnostic morphologique

H vide (aucun hyperonyme de poids > 0) : **47** termes (2,5 % des termes trouvés).

SST vide (aucune annotation _INFO-SEM-*) : **286** termes (15,3 %).

### Diagnostic singulier

Pour chaque terme à H vide, la forme singulière simple (retrait d'un « s »/« x » final) est testée. **C'est un diagnostic : la forme originale reste celle utilisée et le corpus n'est pas modifié.** Le papier décrit ce cas de dispersion en §4.5 (« liste de films »).

- Termes à H vide sans marque de pluriel simple, non testables : 15
- Formes singulières testées : 32 ; existant dans JDM : 32
- **Formes singulières apportant au moins un hyperonyme : 32**

| terme (H vide) | forme singulière | \|H\| du singulier | 3 premiers hyperonymes |
|---|---|---|---|
| melons | melon | 119 | fruit (288), plante potagère (170), cucurbitacée (150) |
| émeraudes | émeraude | 92 | vert (185), pierre précieuse (147), béril (135) |
| caves | cave | 86 | sous-sol (4879.77), coffret (2493.86), personne (2106.95) |
| secouristes | secouriste | 78 | individu (67), personne (61), être humain>189875 (54) |
| vendangeurs | vendangeur | 71 | personne (86), métier>103465 (76), métier (70) |
| Belges | Belge | 62 | personne (65), habitant (64), être vivant>123933 (64) |
| aurores | aurore | 59 | couleur (143), couleur>17226 (130), animal (46) |
| cheminots | cheminot | 59 | personne (77), métier>103465 (76), personne>24956 (75) |
| rosiers | rosier | 41 | rosacée>145941 (153), arbuste (147), arbre (146) |
| chemises | chemise | 31 | vêtement (1000), vêtement haut (601.18), habit (601.14) |
| brûlures | brûlure | 29 | lésion physique (1000), blessure (597.07), douleur (85) |
| vignobles | vignoble | 29 | exploitation agricole (254), agriculture (113), plantation (113) |
| rires | rire | 23 | action (1000), reflex numérique (583.27), en:digital reflex (583.2) |
| émeutes | émeute | 20 | évènement (228), catastrophe (133), événement (109) |
| fantômes | fantôme | 18 | monstre (254), créature imaginaire (140), spectre (69) |
| nuits | nuit | 18 | période (1000), couleur (814.72), moment (566.7) |
| rizières | rizière | 12 | zone cultivée (83), champ (72), terrain (69) |
| estampes | estampe | 9 | représentation d'image (73), représentation d'une image (61), image (34) |
| cendres | cendre | 8 | roche (58), résidu (42), poudre (30) |
| ruches | ruche | 8 | habitat d'élevage (51), rucher (44), structure (29) |
| cloques | cloque | 7 | blessure de la peau (39), en:skin injury (39), lésion cutanée (35) |
| ravages | ravage | 7 | lieu (46), endroit>135190 (41), lieu>134218 (38) |
| oliveraies | oliveraie | 6 | plantation>35925 (59), verger (59), verger>50567 (59) |
| ruelles | ruelle | 6 | rue (1000), impasse (752), chemin (751) |
| troupeaux | troupeau | 6 | groupe d'animaux (109), groupe (104), ensemble (86) |
| courbatures | courbature | 4 | douleur (124), douleur physique (122), douleur musculaire (60) |
| pagodes | pagode | 4 | temple (65), tour bouddhiste (58), architecture asiatique (31) |
| flaques | flaque | 2 | étendue d'eau (95), lieu avec de l'eau (46) |
| gerçures | gerçure | 2 | lésion (56), lésion>102206 (39) |
| huées | huée | 2 | action (25), violence verbale (20) |
| avaries | avarie | 1 | résultat d'un processus (33) |
| bayous | bayou | 1 | étendue d'eau (45) |

<details><summary>Liste complète des termes à H vide (47)</summary>

« Belges », « Plougastel », « aurores », « avaries », « bayous », « brouille », « brûlures », « caves », « cendres », « cheminots », « chemises », « cloques », « courbatures », « douzaine », « délégué », « estampes », « fantômes », « flaques », « férocité », « gerçures », « gorgée », « huées », « lampée », « melons », « moiteur », « muraliste », « nuits », « oliveraies », « pagodes », « préface », « ravages », « rires », « rizières », « rosiers », « rotin », « ruches », « ruelles », « secouristes », « statuette », « stock », « touffe », « troupeaux », « témérité », « vendangeurs », « vignobles », « émeraudes », « émeutes »

</details>

<details><summary>Liste complète des termes à SST vide (286)</summary>

« AVC », « Bagan », « Belges », « Iguazu », « abeilles », « acouphènes », « ampoules », « applaudissements », « arbres », « archives », « aurores », « avaries », « badge », « bananes », « bas-relief », « bayous », « bidonvilles », « bijoux », « bioéthique », « blessures », « bleus », « brassée », « bravoure », « brouille », « brûlure », « brûlures », « but », « buée », « bénéfices », « canaux », « carapace », « cargaison », « caries », « cascades », « cavalerie », « caves », « caviar », « cendres », « cheminots », « chemises », « cigares », « cliché », « clip », « clocher », « cloques », « clés », « code », « colisée », « collines », « conséquences », « copies », « courbatures », « court-circuit », « crin », « cris », « curry », « cécité », « dattes », « dentelle », « dettes », « diagramme », « diamants », « dizaine », « dommages », « données », « douzaine », « déchets », « décombres », « dégâts », « démangeaisons », « députés », « détritus », « dôme », « eaux », « effets », « effigie », « embouteillages », « entonnoir », « estampes », « examens », « exode », « exposé », « falaises », « fantômes », « favelas », « fichiers », « fidèles », « figues », « figurine », « fissures », « fièvre », « fjords », « flaque », « flaques », « fourmis », « fraises », « fruits », « fées », « férocité », « fœtus », « galop », « gendarmes », « gentillesse », « gerçures », « geysers », « glaucome », « gorges », « gorgée », « grille », « grottes », « grévistes », « hallucinations », « hectare », « hirondelles », « huées », « huîtres », « hématome », « icône », « incendies », « inondations », « instruments », « jardins », « jazz », « joueurs », « krach », « lampée », « leçon », « linoléum », « logiciel », « loi », « loups », « loyer », « malentendu », « mangues », « manifestants », « manuel », « manuscrit », « maquette », « marchandises », « marches », « marchés », « marins », « matin », « maçons », « melons », « messages », « midi », « miette », « millier », « mines », « minuit », « monceau », « montres », « mosquées », « mousson », « mue », « muraliste », « méthode », « météorite », « nappe », « nausées », « note », « nuisances », « nuits », « obésité », « odeurs », « oies », « oliveraies », « olives », « oranges », « orphelins », « outils », « ouvriers », « pagodes », « paire », « palan », « paralysie », « patine », « pertes », « perturbations », « phares », « pinceaux », « pipette », « pisé », « pièces », « plaines », « plantes », « pleurs », « plexiglas », « pneus », « podcast », « pommes », « portail », « problème », « projet », « pruneaux », « préface », « public », « pyramides », « pâtes », « pèlerins », « questions », « raisins », « rambarde », « ravages », « refrain », « retards », « retombées », « retraites », « rides », « rires », « rizières », « rosiers », « rotin », « rougeur », « ruban », « ruches », « ruelles », « rues », « récifs », « résultats », « salariés », « sanctions », « scalpel », « schéma », « secouristes », « selle », « silhouette », « skis », « soldes », « somnolence », « souk », « souvenirs », « spectateurs », « stage », « stagiaires », « statuette », « steppes », « stratégie », « supporters », « symphonie », « symptômes », « synonymes », « séquelles », « taches », « tapisserie », « taxis », « thermes », « théorème », « tigres », « toits », « tomates », « torchis », « touffe », « traces », « traité », « traumatisme », « travaux », « tremblements », « troupeaux », « troupes », « tulipes », « tweed », « vaches », « varicelle », « variétés », « vendangeurs », « viaduc », « vibrations », « victimes », « vidéo », « vignobles », « vitres », « vocabulaire », « voracité », « vétusté », « Éducation », « échographie », « écouteurs », « élèves », « émeraudes », « émeutes », « épices », « études », « étudiants », « œufs »

</details>

## 5. Bruit marqué dans H (marqué, jamais supprimé)

- Cibles à préfixe de langue : **5 244** sur 76 807 (6,8 %), touchant 981 termes. Préfixes les plus fréquents : `en:` (5106), `de:` (30), `ko:` (17), `ja:` (16), `ru:` (16), `sv:` (16), `vi:` (15), `zh:` (14), `ar:` (2), `es:` (2).
- Doublons de casse ou d'espaces repérables par `forme_normalisee` : **1 836** cibles redondantes (ex. « Procédé de séparation » et « procédé de séparation »).

Les deux drapeaux sont posés dans le JSONL ; aucune cible n'est retirée. L'étape 3 décidera d'écarter les traductions et de fusionner les doublons.

## 6. Polysémie (raffinements r_raff_sem)

Collectés, non exploités : ils serviront à une expérience de désambiguïsation ultérieure.

Raffinements par terme : min 0, médiane 2, max 19. Termes polysémiques (≥ 1 raffinement) : **1133/1869** (60,6 %).

| relation | termes trouvés | polysémiques | part | raffinements médians |
|---|---|---|---|---|
| `r_depict` | 130 | 104 | 80,0 % | 3 |
| `r_has_causatif` | 157 | 67 | 42,7 % | 0 |
| `r_has_property-1` | 160 | 90 | 56,2 % | 2 |
| `r_holo` | 158 | 131 | 82,9 % | 4 |
| `r_lieu` | 157 | 78 | 49,7 % | 0 |
| `r_lieu>origine` | 158 | 94 | 59,5 % | 2 |
| `r_objet>matiere` | 155 | 124 | 80,0 % | 4 |
| `r_own-1` | 159 | 108 | 67,9 % | 2 |
| `r_processus>instr-1` | 157 | 100 | 63,7 % | 3 |
| `r_processus_agent` | 159 | 107 | 67,3 % | 2 |
| `r_processus_patient` | 160 | 85 | 53,1 % | 2 |
| `r_product_of` | 158 | 124 | 78,5 % | 3 |
| `r_quantificateur` | 154 | 108 | 70,1 % | 3 |
| `r_social_tie` | 142 | 89 | 62,7 % | 2 |
| `r_topic` | 153 | 96 | 62,7 % | 3 |

| rôle | termes trouvés | polysémiques | part |
|---|---|---|---|
| A | 1032 | 624 | 60,5 % |
| B | 1030 | 661 | 64,2 % |

## 7. Coût réel de la passe

| mesure | valeur |
|---|---|
| durée cumulée | 1:41:39 |
| sessions (reprises comprises) | 3 |
| termes sautés par reprise (cumul) | 5 |
| erreurs consignées | 0 |
| requêtes servies | 18 834 |
| dont appels réseau réels | 9 398 |
| volume téléchargé | 801 Mo |
| fichiers de cache | 9 398 |
| volume du cache | 0,95 Go |

## 8. Hors périmètre

Cette étape ne produit ni seuil, ni vecteur, ni vocabulaire global, ni similarité, ni désambiguïsation par raffinement, ni algorithme GRASP-it, et n'applique aucun remplacement. Le corpus est inchangé.
