# Sonde JDM : 30 termes

Généré par `src/jdm_probe.py`. API : `https://jdm-api.demo.lirmm.fr/v0`. Seules les relations de poids ≤ 0 (niées dans JDM) sont écartées ; aucun seuil n'est appliqué. Les latences sont celles des appels réseau réels, conservées dans le cache.

## 0. Endpoints de l'API (lus sur /schema)

| endpoint | paramètres |
|---|---|
| `GET /v0/node_by_name/{node_name}` | — |
| `GET /v0/node_by_id/{node_id}` | — |
| `GET /v0/refinements/{node_name}` | — |
| `GET /v0/nodes_types` | — |
| `GET /v0/relations_types` | — |
| `GET /v0/relations/from/{node1_name}` | types_ids[], not_types_ids[], min_weight, max_weight, relation_fields[], node_fields[], limit, offset, without_nodes |
| `GET /v0/relations/from_by_id/{node1_id}` | idem |
| `GET /v0/relations/to/{node2_name}` | idem (**relations entrantes**) |
| `GET /v0/relations/to_by_id/{node2_id}` | idem (**relations entrantes**) |
| `GET /v0/relations/from/{n1}/to/{n2}` et `from_by_id/{id1}/to_by_id/{id2}` | idem |
| `GET /v0/relations/by_type_id/{type_id}` | min_weight, max_weight, relation_fields[], limit (10000), offset |
| `GET /v0/relations/random` | types_ids[], not_types_ids[], min_weight, max_weight, relation_fields[], limit (100) |

Particularités constatées : `/refinements` plante (500) quand un raffinement est nommé « terme>glose » (ex. « chien ») — la polysémie est donc mesurée par `r_raff_sem` sortant ; nœud absent → HTTP 500 avec `status_code: 404` dans le corps ; `relation_fields` combiné à `types_ids` → erreur 500 serveur ; poids négatifs = relation niée.

## 1. Échantillon

Concrets : liste fixée à la main (fréquence non mesurable hors-ligne). Autres strates : `random.Random(42)` sur des viviers définis par règle — abstraits = A de Caractérisation/Agent/Patient (2 chacun) ; entités nommées = B à majuscule de Lieu/Origine (3 chacun) ; polylexicaux = « terre cuite », « Côte d'Ivoire » + 4 tirés parmi les termes à espace/tiret/apostrophe ; pluriels = B introduits par « des ».

| terme | strate | existe | id | type | poids nœud | r_isa (bruts) | H (≤50, w>0) | TRT types | TRT relations w>0 | SST | raff. (sens) | raff. (total) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| voiture | concret | oui | 6890 | n_term | 23063 | 174 | 50 | 71 | 40294 | 5 | 4 | 4 |
| maison | concret | oui | 45179 | n_term | 43192 | 119 | 50 | 62 | 47037 | 5 | 10 | 10 |
| pain | concret | oui | 61283 | n_term | 6207 | 59 | 39 | 64 | 27859 | 4 | 6 | 6 |
| chien | concret | oui | 4455 | n_term | 9463 | 264 | 50 | 71 | 33203 | 7 | 10 | 10 |
| vélo | concret | oui | 68256 | n_term | 5538 | 126 | 50 | 62 | 14041 | 4 | 4 | 4 |
| bateau | concret | oui | 107150 | n_term | 11031 | 135 | 50 | 63 | 37237 | 5 | 6 | 6 |
| amertume | abstrait | oui | 126306 | n_term | 462 | 8 | 8 | 36 | 4212 | 2 | 2 | 2 |
| discrétion | abstrait | oui | 68063 | n_term | 1074 | 20 | 14 | 47 | 9944 | 2 | 0 | 0 |
| huées | abstrait | oui | 98599 | n_term | 138 | 0 | 0 | 10 | 81 | 0 | 0 | 0 |
| leçon | abstrait | oui | 20425 | n_term | 3107 | 6 | 4 | 40 | 4908 | 0 | 0 | 0 |
| distillation | abstrait | oui | 64985 | n_term | 320 | 21 | 15 | 48 | 6313 | 1 | 0 | 0 |
| ferrage | abstrait | oui | 77747 | n_term | 72 | 1 | 1 | 17 | 196 | 1 | 0 | 0 |
| Bath | entité nommée | oui | 142441 | n_term | 94 | 17 | 14 | 15 | 1879 | 4 | 2 | 2 |
| Bordeaux | entité nommée | oui | 144632 | n_term | 5200 | 63 | 50 | 34 | 22229 | 7 | 5 | 5 |
| Verdon | entité nommée | oui | 94825 | n_term | 93 | 35 | 30 | 15 | 473 | 5 | 3 | 3 |
| Arabie | entité nommée | oui | 63453 | n_term | 1829 | 6 | 4 | 20 | 4448 | 3 | 1 | 1 |
| Argentine | entité nommée | oui | 12153 | n_term | 4224 | 119 | 50 | 36 | 35636 | 10 | 8 | 8 |
| Perse | entité nommée | oui | 139062 | n_term | 2537 | 87 | 50 | 32 | 7777 | 10 | 3 | 3 |
| terre cuite | polylexical | oui | 103256 | n_term | 171 | 4 | 4 | 38 | 2623 | 1 | 0 | 0 |
| Côte d'Ivoire | polylexical | oui | 159122 | n_term | 551 | 14 | 13 | 29 | 4683 | 6 | 2 | 2 |
| New York | polylexical | oui | 120673 | n_term | 3614 | 191 | 50 | 46 | 62497 | 9 | 8 | 8 |
| Terre-Neuve | polylexical | oui | 64297 | n_term | 118 | 17 | 13 | 21 | 4054 | 4 | 1 | 1 |
| bas-relief | polylexical | oui | 132909 | n_term | 135 | 4 | 4 | 25 | 1689 | 0 | 0 | 0 |
| porte-parole | polylexical | oui | 43055 | n_term | 4303 | 62 | 50 | 41 | 3276 | 2 | 0 | 0 |
| animaux | pluriel | oui | 71539 | n_term | 9278 | 115 | 50 | 58 | 133715 | 1 | 0 | 0 |
| députés | pluriel | oui | 146850 | n_term | 7114 | 9 | 8 | 27 | 3403 | 0 | 0 | 0 |
| orphelins | pluriel | oui | 400414 | n_term | 149 | 1 | 1 | 22 | 498 | 0 | 0 | 0 |
| phares | pluriel | oui | 31610 | n_term | 230 | 1 | 1 | 20 | 1468 | 0 | 0 | 0 |
| pompiers | pluriel | oui | 15478 | n_term | 1385 | 8 | 6 | 35 | 4069 | 1 | 0 | 0 |
| rosiers | pluriel | oui | 129899 | n_term | 104 | 0 | 0 | 10 | 622 | 0 | 0 | 0 |

## 2. Termes introuvables

Aucun : les 30 termes existent dans JDM sous leur forme exacte.

## 3. Trait H : décroissance des poids r_isa

r_isa positifs retenus par terme (nœuds n_term/n_form, hors préfixes « _ » et « : ») : min 0, médiane 14.0, max 198. Relations r_isa de poids ≤ 0 écartées au total : 427.

| rang | termes ayant ce rang | poids médian | min | max | médiane w/w₁ |
|---|---|---|---|---|---|
| 1 | 28 | 119.0 | 10.0 | 5571.0 | 1.00 |
| 5 | 21 | 398.0 | 24.0 | 973.3 | 0.55 |
| 10 | 18 | 504.1 | 25.0 | 948.9 | 0.51 |
| 20 | 13 | 502.3 | 28.0 | 743.6 | 0.50 |
| 30 | 13 | 500.1 | 12.0 | 698.5 | 0.41 |
| 50 | 11 | 143.0 | 25.0 | 504.0 | 0.14 |

Le tableau ci-dessus mélange des sous-populations (seuls les termes riches ont un rang 5) : le poids médian n'y décroît donc pas. Décroissance sur les 11 termes ayant ≥ 50 r_isa positifs (voiture, maison, chien, vélo, bateau, Bordeaux, Argentine, Perse, New York, porte-parole, animaux) :

| rang | termes | poids médian | médiane w/w₁ |
|---|---|---|---|
| 1 | 11 | 1000.0 | 1.00 |
| 2 | 11 | 871.2 | 0.91 |
| 3 | 11 | 695.3 | 0.81 |
| 5 | 11 | 559.9 | 0.56 |
| 10 | 11 | 551.6 | 0.54 |
| 20 | 11 | 516.6 | 0.50 |
| 30 | 11 | 500.5 | 0.50 |
| 40 | 11 | 478.0 | 0.33 |
| 50 | 11 | 143.0 | 0.14 |
| 75 | 7 | 42.0 | 0.04 |
| 100 | 4 | 263.6 | 0.06 |

Répartition des 1241 poids r_isa positifs : < 30 (≈ 1 vote) : 291 ; 30–100 : 228 ; 100–300 : 94 ; 300–600 : 516 ; ≥ 600 : 112.


Taille de H selon la coupure (médiane [min–max] sur les termes trouvés, plafonnée à 50) :

- aucune (w > 0) : 14.0 [0–50]
- top 10 : 10.0 [0–10]
- top 20 : 14.0 [0–20]
- w ≥ 50 : 4.5 [0–50]
- w ≥ 100 : 1.5 [0–50]
- w ≥ 25 % de w₁ : 11.5 [0–50]
- w ≥ 50 % de w₁ : 6.0 [0–50]

Détail des 10 premiers hyperonymes par terme :

| terme | |H| | 10 premiers (poids) |
|---|---|---|
| voiture | 50 | mode de transport (1000), Véhicule automobile (551.61), véhicule à roues (551.61), en:aircraft (551.59), véhicule routier (551.59), 2CV (551.58), véhicule (551.58), véhicule automobile (551.58), en:motor vehicle (551.57), véhicule à moteur (551.57) |
| maison | 50 | bâtiment (1000), entreprise (714.08), lignée (695.26), maison mila (543.04), Maison de Schaumbourg (543.02), habitation (543.02), résidence (543), immeuble (542.99), hôtel (542.97), Maison Gourieli (542.96) |
| pain | 39 | aliment de base (422), aliment (407), pâte (403), ingrédient de cuisine (400), féculent (398), nourriture (371), aliment périssable (367), viennoiserie (367), en:staple food (363), Aliment de base (362) |
| chien | 50 | mammifère (5571), pièce d'arme à feu (2931.8), thérien (1000), deutérostomien (691.32), coelomate (604), cordé (598.63), cordé>zoologie (586.5), bilatérien (575.89), chordé (573.18), tétrapode>vertébré (561.09) |
| vélo | 50 | mode de transport (1000), outil (916.05), véhicule (661.58), moyen de locomotion (636.08), cycle (635.52), en:two-wheeler (633.24), deux-roues (633.17), véhicule à roues (633.17), en:two-wheeled vehicle (633.1), véhicule automobile (632.96) |
| bateau | 50 | embarcation (1000), trottoir (770.04), ravier (683.08), dinghee (559.87), véhicule aquatique (559.86), navire de balisage (559.85), bateau à moteur diesel (559.83), en:mass transit (500.29), véhicule motorisé (500.21), en:motor vehicle (500.2) |
| amertume | 8 | saveur (1000), saveur caractéristique (599), propriété>caractéristique (48), propriété (30), déplaisir (29), goût>saveur (28), acrimonie (25), goût (1) |
| discrétion | 14 | qualité (50), propriété>caractéristique (30), comportement (26), comportement prudent (26), activité secrète (25), affaires privées (25), attitude (25), comportements furtifs (25), manigances subtiles (25), méthode subtile (25) |
| huées | 0 | — |
| leçon | 4 | enseignement (40), action (32), expérience passée (26), session (25) |
| distillation | 15 | procédé de purification (83), technique de séparation (83), procédé de séparation (81), Procédé de séparation (78), méthode de séparation (77), procédé (77), technique d'IA (77), technique d'optimisation (77), technique (75), méthode (71) |
| ferrage | 1 | action (36) |
| Bath | 14 | lieu>endroit (119), ville (118), lieu (73), hameau (57), club de rugby à XV (33), village (33), en:dorp (32), lieu géographique (32), localité (30), partie de l'espace (30) |
| Bordeaux | 50 | ville (1000), vin (925.28), couleur (884.49), port de commerce (567.35), ville de France (522.27), préfecture>ville (517.89), port (516.91), commune (516.89), préfecture (516.89), chef-lieu (516.88) |
| Verdon | 30 | commune>circonscription (78), commune (77), parc régional (70), rivière (70), cours d'eau (65), commune française (55), en:stream (38), en:turbojet (38), lieu (34), en:regional park (33) |
| Arabie | 4 | péninsule (330), région (240), lieu (59), en:peninsula (25) |
| Argentine | 50 | pays (1000), femme (908.22), commune française (829.47), ruisseau (808.85), être humain de sexe féminin (519.81), individu féminin (515.23), pays en voie de développement (515.14), pays d'Amérique du Sud (511.27), humain (511.1), Amérique du Sud (507.97) |
| Perse | 50 | habitant (1000), homme>mâle (995.05), homme>être humain de sexe masculin (993.07), être humain de sexe masculin (979.81), personne morte (973.31), individu masculin (961.54), personne décédée (961.54), homme (957.56), en:family name (950.88), en:patronym (948.94) |
| terre cuite | 4 | matériau (54), terre (40), céramique (27), tajine (25) |
| Côte d'Ivoire | 13 | pays (119), pays>nation (105), lieu (65), pays membre (52), nation (51), colonie (46), État (37), lieu géographique (33), lieu>endroit (31), partie de l'espace (29) |
| New York | 50 | ville (1000), État (871.25), navire (811.55), état (796.44), métropole (688.94), état des États-Unis (687.09), en:american state (686.98), État américain (686.87), État des États-Unis (686.87), état américain (686.81) |
| Terre-Neuve | 13 | île (58), lieu (36), localisation géographique (36), aire métropolitaine (30), prédécesseur (30), lieu géographique (29), commune (28), lieu>endroit (28), partie de l'espace (28), continent (26) |
| bas-relief | 4 | sculpture (104), œuvre (49), création (49), ouvrage (49) |
| porte-parole | 50 | personne (81), personne>être humain (79), être humain (78), individu (76), être vivant (66), être humain>personne humaine (55), être vivant>entité (55), être animé (45), synapside (38), acteur politique (36) |
| animaux | 50 | lions (624.35), vertébrés (619.35), animaux stupides (615.35), en:dumb animals (613.35), métazoaires (612.35), choanobiontes (610.35), holozoaires (608.35), opisthocontes (605.35), Opisthocontes (593.9), espèces (593) |
| députés | 8 | liste (34), représentants politiques (33), représentants (27), élus (26), membres de l'assemblée (25), membres de l'assemblée nationale (25), membres de l'assemblée nationale du pays de Galles (25), en:parliament (10) |
| orphelins | 1 | enfants sans famille (26) |
| phares | 1 | sculpture (10) |
| pompiers | 6 | secouristes (75), en:local department (28), sauveteurs (26), services d'urgence (26), en:fire (24), en:department of local government (23) |
| rosiers | 0 | — |

### Recommandation H

**Coupure par rang, top 20 par poids décroissant (hors poids ≤ 0), sans seuil absolu.** Alternative : top 30.

- **Pas de seuil absolu.** Les termes pauvres n'ont que des poids de 25 à 50 (un ou deux votes) : `w ≥ 50` ramène H à une médiane de 4.5 symboles et vide presque entièrement les abstraits, les pluriels et les polylexicaux. Or ce sont justement les termes à qui l'hyperonymie fait déjà défaut (papier, §4.4.1).
- **Pas de seuil relatif.** Sur les termes riches, w/w₁ se stabilise vers 0,5 entre les rangs 5 et 30 : un seuil à 50 % de w₁ tomberait au milieu de ce palier, et le nombre de symboles gardés basculerait d'un terme à l'autre sur des écarts de poids insignifiants.
- **Pourquoi 20.** Le palier (poids ≈ 500–550, souvent identiques à 0,01 près) va jusqu'au rang 30 environ, puis chute (0,33 au rang 40, 0,20 au rang 50). Top 20 coupe dans le palier avant la chute ; top 30 en garde la totalité. 17/30 termes ont moins de 20 hyperonymes : pour eux, la coupure ne change rien. Elle ne borne donc que les termes riches.
- **Limite.** Le palier contient du bruit que le poids ne permet pas d'isoler : New York → navire (811), en:american state, doublons de casse (« Procédé » et « procédé de séparation »). Le filtre sur le type de nœud (repris de main.py) écarte déjà les nœuds n_wikipedia aux noms tronqués (« bâtiment d », « véhicule à ») et les n_chunk. Aucune coupure par poids n'élimine le reste.

## 4. Trait TRT : types de relations entrantes

Types entrants distincts (w > 0) par terme : min 10, médiane 35.5, max 71 (sur 180 types existants).
Relations entrantes w > 0 par terme : min 81, médiane 4565.5, max 133715. Relations entrantes de poids ≤ 0 : 139615 au total.

Types entrants les plus répandus (nombre de termes sur 30 qui les reçoivent) :

`r_aki` (30), `r_associated` (30), `r_context` (30), `r_variante` (29), `r_isa` (28), `r_wiki` (28), `r_carac-1` (27), `r_translation` (26), `r_domain-1` (25), `r_has_part` (25), `r_hypo` (25), `r_syn` (25), `r_lemma` (24), `r_meaning/glose` (24), `r_patient` (24), `r_lieu-1` (23), `r_concerning` (21), `r_der_morpho` (21), `r_holo` (21), `r_agent` (20), `r_lieu` (20), `r_accomp` (19), `r_family` (18), `r_interact_with` (16), `r_make` (16), `r_raff_sem-1` (16), `r_sentiment-1` (16), `r_has_conseq` (15), `r_processus>agent` (15), `r_can_eat-1` (14), `r_has_causatif` (14), `r_make_use_of` (14), `r_require` (14), `r_sing_form` (14), `r_symptomes-1` (14), `r_anto` (13), `r_own-1` (12), `r_processus>instr-1` (12), `r_product_of` (12), `r_domain` (11)

Nombre de types entrants retenus selon un effectif minimal par type :

- effectif ≥ 1 : médiane 35.5 [10–71]
- effectif ≥ 2 : médiane 25.0 [6–65]
- effectif ≥ 5 : médiane 17.5 [4–55]
- effectif ≥ 10 : médiane 12.5 [3–44]

### Recommandation TRT

**Borné naturellement : pas de coupure de taille nécessaire. Recommandation : exclure une liste de types non sémantiques, sans seuil d'effectif.**

- **Borne.** Le nombre de types distincts ne peut pas dépasser le nombre de types JDM (180) et vaut au plus 71 dans l'échantillon, alors que le nombre de relations entrantes varie de 81 à 133715. La signature est binaire : ce volume n'a donc aucun effet sur sa taille.
- **Types universels.** Présents chez les 30 termes : `r_aki`, `r_associated`, `r_context`. Ces symboles sont constants : ils gonflent toutes les similarités de la même façon, sans rien discriminer.
- **Liste d'exclusion proposée** (types méta, lexicaux ou techniques) : `r_aki`, `r_wiki`, `r_associated`, `r_context`, `r_variante`, `r_translation`, `r_lemma`, `r_meaning/glose`, `r_raff_sem-1`, `r_sing_form`, `r_der_morpho`, `r_masc`, `r_homophone`, `r_locution`, `r_error`. Avec cette exclusion, TRT vaut médiane 25.0 [5–60] ; avec en plus un effectif ≥ 2, 17.5 [3–55].
- **Pas de seuil d'effectif.** L'effectif dépend surtout de la popularité du terme (huées : 81 relations entrantes, animaux : 133 715). Un seuil pénaliserait encore les termes rares.

## 5. Trait SST : _INFO-SEM-*

_INFO-SEM-* (w > 0) par terme : min 0, médiane 2.5, max 10 ; 7 terme(s) sans aucune annotation.

| terme | annotations (poids) |
|---|---|
| voiture | THING-ARTEFACT (76), THING-CONCRETE (63), PLACE (61), PLACE-HUMAN (39), THING-ABSTR (15) |
| maison | PLACE (67), CARAC (57), THING-CONCRETE (51), PLACE-HUMAN (46), THING-ARTEFACT (35) |
| pain | SUBST (60), THING-CONCRETE (51), PLACE (42), THING (25) |
| chien | LIVING-BEING (51), PLACE (44), THING-CONCRETE (38), SUBST (35), THING-ARTEFACT (32), THING (30), PERS (29) |
| vélo | THING-CONCRETE (61), THING-ARTEFACT (51), PLACE-HUMAN (48), PLACE (41) |
| bateau | THING-ARTEFACT (70), PLACE (62), THING-CONCRETE (62), PLACE-HUMAN (48), ISA-CONCEPT (44) |
| amertume | PROPERTY-NAME (48), EMOTION-RELATED (42) |
| discrétion | EMOTION-RELATED (42), PROPERTY-NAME (39) |
| huées | — |
| leçon | — |
| distillation | ACTION (41) |
| ferrage | ACTION (41) |
| Bath | NAMED-ENTITY (85), PLACE-GEO (61), PLACE (57), PLACE-HUMAN (54) |
| Bordeaux | NAMED-ENTITY (70), PLACE (65), PLACE-HUMAN (64), PLACE-GEO (52), SUBST (44), NODET (31), ORGA (28) |
| Verdon | NAMED-ENTITY (121), PLACE-HUMAN (68), PLACE-GEO (59), PLACE (54), NODET (28) |
| Arabie | NAMED-ENTITY (44), PLACE (35), NODET (30) |
| Argentine | PLACE-GEO (65), PLACE (56), PLACE-HUMAN (56), LIVING-BEING (40), PERS (40), PERS-FEM (40), ORGA (32), PLACE-ABSTRACT (32), DET (29), NODET (26) |
| Perse | NAMED-ENTITY (60), LIVING-BEING (40), PERS (40), PLACE (32), PLACE-HUMAN (31), PLACE-GEO (28), DET (27), NODET (26), PERS-MASC (26), THING-ABSTR (25) |
| terre cuite | SUBST (49) |
| Côte d'Ivoire | NAMED-ENTITY (63), PLACE-HUMAN (60), PLACE (58), PLACE-GEO (53), NODET (34), DET (31) |
| New York | PLACE-HUMAN (82), PLACE (79), PLACE-GEO (72), NAMED-ENTITY (55), ORGA (36), DET (34), PLACE-ABSTRACT (30), NODET (27), THING-ARTEFACT (17) |
| Terre-Neuve | PLACE (59), NAMED-ENTITY (58), PLACE-GEO (51), PLACE-HUMAN (40) |
| bas-relief | — |
| porte-parole | LIVING-BEING (40), PERS (40) |
| animaux | LIVING-BEING (47) |
| députés | — |
| orphelins | — |
| phares | — |
| pompiers | PLACE (46) |
| rosiers | — |

## 6. Taille de signature résultante

Terme lui-même (1) + H + TRT + SST, ensemble plat de symboles binaires.

| configuration | H | TRT | SST | total |
|---|---|---|---|---|
| sans coupure (w > 0, H non plafonné) | 14.0 [0–198] | 35.5 [10–71] | 2.5 [0–10] | 50.0 [11–277] |
| recommandée (H top 20, TRT sans types non sémantiques) | 14.0 [0–20] | 25.0 [5–60] | 2.5 [0–10] | 37.0 [6–87] |

## 7. Polysémie (raffinements)

Termes avec au moins un raffinement : 16/30 (53 %) ; avec au moins deux sens de premier niveau : 14/30 (47 %). Sens de premier niveau : médiane 1.0, max 10.

| strate | polysémiques (≥1 raff.) | sens médians |
|---|---|---|
| concret | 6/6 | 6.0 |
| abstrait | 1/6 | 0.0 |
| entité nommée | 6/6 | 3.0 |
| polylexical | 3/6 | 0.5 |
| pluriel | 0/6 | 0.0 |

## 8. Latence et coût d'une passe complète

| endpoint | appels | moyenne (s) | médiane (s) | max (s) | appels / terme |
|---|---|---|---|---|---|
| node_by_name | 30 | 0.05 | 0.04 | 0.16 | 1 |
| relations/from | 90 | 0.14 | 0.04 | 5.10 | 3 |
| relations/to | 30 | 2.36 | 1.19 | 10.25 | 1 |

Latence moyenne par appel, tous endpoints : 0.39 s (223 appels).
Par terme : 2.82 s d'appels + 1.5 s de délai de politesse (5 appels × 0.3 s).
**Passe complète estimée sur 1871 termes : 135 min (2.2 h)**, en séquentiel, sans erreur ni nouvel essai. Les relations entrantes dominent : leur coût croît avec la fréquence du terme (voir max).

Volume téléchargé pour les 30 termes : 14.3 Mo, dont 98 % pour les relations entrantes. Extrapolé à 1871 termes : **≈ 0.9 Go de cache** (un JSON par requête, non compressé). Le timeout de 10 s ne suffit pas pour les relations entrantes : on a mesuré jusqu'à 10.3 s (et 22 s pour « eau » en exploration), d'où un timeout de 60 s sur cet endpoint.

## 9. Test des deux lignes ambiguës (méthode §4.1)

Existence dans JDM de chaque candidat A et B. Le corpus n'est pas modifié.

| syntagme | A | A existe | B | B existe | découpage |
|---|---|---|---|---|---|
| cacao de Côte d'Ivoire | cacao | oui | Côte d'Ivoire | oui | valide |
| cacao de Côte d'Ivoire | cacao de Côte | **non** | Ivoire | oui | rejeté |
| diamants d'Afrique du Sud | diamants | oui | Afrique du Sud | oui | valide |
| diamants d'Afrique du Sud | diamants d'Afrique | **non** | Sud | oui | rejeté |

**Résultat.** Pour les deux syntagmes, un seul découpage a ses deux termes dans JDM : « cacao de Côte d'Ivoire » → A = `cacao`, B = `Côte d'Ivoire` ; « diamants d'Afrique du Sud » → A = `diamants`, B = `Afrique du Sud`. Le critère est suffisant ici parce que le A du découpage concurrent (« cacao de Côte », « diamants d'Afrique ») n'existe pas, alors que les deux B concurrents existent (Ivoire, Sud). Tester B seul n'aurait donc pas suffi. Corpus non modifié.

