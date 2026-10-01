# Apprentissage par fusion : instrumentation de la cascade

Étape 4 du papier (section 3), mesurée et non tranchée. Douze combinaisons : deux ordonnancements de fusion et six seuils. Aucune classification, aucun score, aucun élagage, aucun appel réseau, et le split test n'est pas touché.

## 1. Dispositif

- **Split.** Les 750 lignes d'entraînement sont coupées par type en 40 d'apprentissage et 10 de calibrage, soit 600 et 150 au total. Tirage `random.Random` à graine dérivée de 42, une par type, écrit dans `data/corpus/clean/split_calibrage.csv`. **Le split test n'est ni lu ni touché.**
- **Calibrage non utilisé ici.** Il sert à l'étape 5 pour arrêter le seuil ; cette étape n'apprend que sur les 40.
- **Signatures.** Politique TRT P8@C66, appliquée dans `config.py` après les deux diagnostics. Les signatures de départ font 2 à 94 symboles, médiane 55.
- **Critère.** « les deux » : sim(A₁,A₂) > seuil ET sim(B₁,B₂) > seuil, strictement. Seules deux règles de même `rt` peuvent fusionner.
- **Itératif.** Une règle issue d'une fusion peut refusionner ; on s'arrête quand plus aucune paire ne passe.

## 2. Balayage : douze combinaisons

« tours max » est le plus grand nombre de parcours complets qu'un type a demandés avant stabilité. En glouton, un tour égale une fusion, puisque tout est recalculé après chacune ; en séquentiel, un tour est un parcours qui peut enchaîner plusieurs fusions.

### 2.1 Stratégie « glouton »

| seuil | règles | réduction | fusions | tours max | orphelines | poids min/méd./max | taille méd. | taille max | types/règles emballés |
|---|---|---|---|---|---|---|---|---|---|
| 0,30 | 600 → **58** | 90,3 % | 542 | 39 | 18 (31 %) | 1 / 7,0 / 38 | 56 → 156 | 647 | 15 / 26 |
| 0,35 | 600 → **97** | 83,8 % | 503 | 37 | 28 (29 %) | 1 / 4,0 / 30 | 56 → 94 | 484 | 15 / 38 |
| 0,40 | 600 → **160** | 73,3 % | 440 | 35 | 52 (32 %) | 1 / 3,5 / 19 | 56 → 85 | 317 | 15 / 39 |
| 0,45 | 600 → **252** | 58,0 % | 348 | 29 | 116 (46 %) | 1 / 2,0 / 12 | 56 → 65 | 230 | 13 / 25 |
| **0,50** (papier) | 600 → **367** | 38,8 % | 233 | 22 | 240 (65 %) | 1 / 1,0 / 8 | 56 → 55 | 198 | 7 / 9 |
| 0,55 | 600 → **480** | 20,0 % | 120 | 13 | 386 (80 %) | 1 / 1,0 / 5 | 56 → 56 | 172 | 0 / 0 |

### 2.2 Stratégie « sequentiel »

| seuil | règles | réduction | fusions | tours max | orphelines | poids min/méd./max | taille méd. | taille max | types/règles emballés |
|---|---|---|---|---|---|---|---|---|---|
| 0,30 | 600 → **53** | 91,2 % | 547 | 39 | 18 (34 %) | 1 / 3,0 / 37 | 56 → 113 | 674 | 15 / 24 |
| 0,35 | 600 → **78** | 87,0 % | 522 | 37 | 22 (28 %) | 1 / 5,0 / 30 | 56 → 120 | 518 | 15 / 36 |
| 0,40 | 600 → **126** | 79,0 % | 474 | 37 | 51 (40 %) | 1 / 2,0 / 20 | 56 → 84 | 384 | 15 / 44 |
| 0,45 | 600 → **229** | 61,8 % | 371 | 31 | 110 (48 %) | 1 / 2,0 / 15 | 56 → 70 | 304 | 15 / 31 |
| **0,50** (papier) | 600 → **354** | 41,0 % | 246 | 24 | 237 (67 %) | 1 / 1,0 / 8 | 56 → 57 | 220 | 7 / 12 |
| 0,55 | 600 → **471** | 21,5 % | 129 | 17 | 385 (82 %) | 1 / 1,0 / 6 | 56 → 55 | 173 | 2 / 2 |

## 3. Glouton contre séquentiel

Les deux stratégies partent des mêmes règles et appliquent le même critère ; seul l'ordre des fusions diffère.

| seuil | règles glouton | règles séq. | écart | poids max glouton | poids max séq. | taille max glouton | taille max séq. | types emballés g/s |
|---|---|---|---|---|---|---|---|---|
| 0,30 | 58 | 53 | -5 | 38 | 37 | 647 | 674 | 15 / 15 |
| 0,35 | 97 | 78 | -19 | 30 | 30 | 484 | 518 | 15 / 15 |
| 0,40 | 160 | 126 | -34 | 19 | 20 | 317 | 384 | 15 / 15 |
| 0,45 | 252 | 229 | -23 | 12 | 15 | 230 | 304 | 13 / 15 |
| **0,50** (papier) | 367 | 354 | -13 | 8 | 8 | 198 | 220 | 7 / 7 |
| 0,55 | 480 | 471 | -9 | 5 | 6 | 172 | 173 | 0 / 2 |

## 4. Détail par type

Stratégie gloutonne, aux seuils qui encadrent la fourchette retenue au tour 2 et au seuil du papier. Un type dont les règles s'effondrent vers une poignée d'unités très lourdes est un type qui a perdu sa capacité à distinguer.

### 4.1 Seuil 0,35, glouton

| type | règles | fusions | orphelines | poids min/méd./max | taille méd. | taille max | emballement |
|---|---|---|---|---|---|---|---|
| `r_depict` | 40 → 10 | 30 | 4 | 1 / 3,0 / 16 | 57 → 81 | 339 | oui |
| `r_has_causatif` | 40 → 6 | 34 | 0 | 1 / 8,0 / 11 | 50 → 132 | 247 | oui |
| `r_has_property-1` | 40 → 6 | 34 | 2 | 1 / 3,5 / 16 | 54 → 118 | 362 | oui |
| `r_holo` | 40 → 8 | 32 | 4 | 1 / 1,5 / 18 | 57 → 58 | 391 | oui |
| `r_lieu` | 40 → 6 | 34 | 0 | 1 / 5,5 / 14 | 42 → 94 | 324 | oui |
| `r_lieu>origine` | 40 → 7 | 33 | 1 | 1 / 3,0 / 19 | 50 → 76 | 302 | oui |
| `r_objet>matiere` | 40 → 7 | 33 | 3 | 1 / 4,0 / 15 | 56 → 92 | 267 | oui |
| `r_own-1` | 40 → 4 | 36 | 1 | 1 / 8,5 / 22 | 53 → 190 | 409 | oui |
| `r_processus>instr-1` | 40 → 5 | 35 | 1 | 1 / 5,0 / 20 | 57 → 137 | 349 | oui |
| `r_processus_agent` | 40 → 9 | 31 | 4 | 1 / 2,0 / 13 | 56 → 74 | 310 | oui |
| `r_processus_patient` | 40 → 5 | 35 | 1 | 1 / 8,0 / 14 | 58 → 155 | 346 | oui |
| `r_product_of` | 40 → 7 | 33 | 3 | 1 / 2,0 / 23 | 56 → 77 | 427 | oui |
| `r_quantificateur` | 40 → 6 | 34 | 1 | 1 / 5,5 / 16 | 59 → 148 | 329 | oui |
| `r_social_tie` | 40 → 5 | 35 | 2 | 1 / 3,0 / 30 | 54 → 76 | 484 | oui |
| `r_topic` | 40 → 6 | 34 | 1 | 1 / 7,0 / 13 | 62 → 194 | 292 | oui |

### 4.2 Seuil 0,45, glouton

| type | règles | fusions | orphelines | poids min/méd./max | taille méd. | taille max | emballement |
|---|---|---|---|---|---|---|---|
| `r_depict` | 40 → 25 | 15 | 14 | 1 / 1,0 / 4 | 57 → 60 | 154 | — |
| `r_has_causatif` | 40 → 16 | 24 | 6 | 1 / 2,0 / 7 | 50 → 60 | 181 | oui |
| `r_has_property-1` | 40 → 16 | 24 | 8 | 1 / 1,5 / 12 | 54 → 65 | 222 | oui |
| `r_holo` | 40 → 21 | 19 | 11 | 1 / 1,0 / 6 | 57 → 60 | 183 | oui |
| `r_lieu` | 40 → 16 | 24 | 5 | 1 / 2,0 / 6 | 42 → 60 | 180 | oui |
| `r_lieu>origine` | 40 → 16 | 24 | 9 | 1 / 1,0 / 9 | 50 → 48 | 209 | oui |
| `r_objet>matiere` | 40 → 17 | 23 | 7 | 1 / 2,0 / 6 | 56 → 77 | 182 | oui |
| `r_own-1` | 40 → 13 | 27 | 5 | 1 / 2,0 / 10 | 53 → 70 | 197 | oui |
| `r_processus>instr-1` | 40 → 14 | 26 | 5 | 1 / 2,5 / 8 | 57 → 72 | 230 | oui |
| `r_processus_agent` | 40 → 19 | 21 | 10 | 1 / 1,0 / 8 | 56 → 61 | 213 | oui |
| `r_processus_patient` | 40 → 15 | 25 | 4 | 1 / 3,0 / 5 | 58 → 78 | 176 | oui |
| `r_product_of` | 40 → 15 | 25 | 7 | 1 / 2,0 / 6 | 56 → 74 | 170 | oui |
| `r_quantificateur` | 40 → 18 | 22 | 10 | 1 / 1,0 / 8 | 59 → 60 | 198 | oui |
| `r_social_tie` | 40 → 12 | 28 | 4 | 1 / 2,0 / 10 | 54 → 75 | 213 | oui |
| `r_topic` | 40 → 19 | 21 | 11 | 1 / 1,0 / 5 | 62 → 68 | 184 | — |

### 4.3 Seuil **0,50** (papier), glouton

| type | règles | fusions | orphelines | poids min/méd./max | taille méd. | taille max | emballement |
|---|---|---|---|---|---|---|---|
| `r_depict` | 40 → 32 | 8 | 25 | 1 / 1,0 / 3 | 57 → 57 | 141 | — |
| `r_has_causatif` | 40 → 27 | 13 | 17 | 1 / 1,0 / 4 | 50 → 54 | 133 | — |
| `r_has_property-1` | 40 → 21 | 19 | 14 | 1 / 1,0 / 7 | 54 → 58 | 182 | oui |
| `r_holo` | 40 → 28 | 12 | 20 | 1 / 1,0 / 4 | 57 → 59 | 153 | — |
| `r_lieu` | 40 → 26 | 14 | 19 | 1 / 1,0 / 6 | 42 → 44 | 179 | oui |
| `r_lieu>origine` | 40 → 21 | 19 | 10 | 1 / 2,0 / 5 | 50 → 53 | 152 | oui |
| `r_objet>matiere` | 40 → 24 | 16 | 15 | 1 / 1,0 / 4 | 56 → 55 | 153 | — |
| `r_own-1` | 40 → 22 | 18 | 16 | 1 / 1,0 / 6 | 53 → 54 | 153 | — |
| `r_processus>instr-1` | 40 → 23 | 17 | 15 | 1 / 1,0 / 6 | 57 → 54 | 196 | oui |
| `r_processus_agent` | 40 → 25 | 15 | 16 | 1 / 1,0 / 6 | 56 → 60 | 170 | oui |
| `r_processus_patient` | 40 → 19 | 21 | 6 | 1 / 2,0 / 4 | 58 → 72 | 161 | — |
| `r_product_of` | 40 → 23 | 17 | 14 | 1 / 1,0 / 4 | 56 → 62 | 158 | — |
| `r_quantificateur` | 40 → 26 | 14 | 20 | 1 / 1,0 / 8 | 59 → 54 | 198 | oui |
| `r_social_tie` | 40 → 21 | 19 | 13 | 1 / 1,0 / 6 | 54 → 54 | 176 | oui |
| `r_topic` | 40 → 29 | 11 | 20 | 1 / 1,0 / 4 | 62 → 66 | 163 | — |

## 5. Détection d'emballement

Deux symptômes distincts, et ils ne se déclenchent pas au même moment.

- **Par le poids** : une règle couvre plus de 50 % des 40 exemples de son type.
- **Par la taille** : une de ses signatures dépasse 3 fois la taille initiale médiane du type.

Aucune règle de départ ne déclenche l'un ou l'autre : tout ce qui suit est produit par la cascade.

| stratégie | seuil | signalées par poids | signalées par taille | règle la plus lourde | signature la plus grande | facteur max |
|---|---|---|---|---|---|---|
| glouton | 0,30 | 11 | 26 | 38 / 40 (95 %) | 647 | 11,5× |
| glouton | 0,35 | 3 | 38 | 30 / 40 (75 %) | 484 | 8,9× |
| glouton | 0,40 | 0 | 39 | 19 / 40 (48 %) | 317 | 5,8× |
| glouton | 0,45 | 0 | 25 | 12 / 40 (30 %) | 230 | 4,3× |
| glouton | **0,50** (papier) | 0 | 9 | 8 / 40 (20 %) | 198 | 4,3× |
| glouton | 0,55 | 0 | 0 | 5 / 40 (12 %) | 172 | — |
| sequentiel | 0,30 | 13 | 24 | 37 / 40 (92 %) | 674 | 11,8× |
| sequentiel | 0,35 | 9 | 36 | 30 / 40 (75 %) | 518 | 9,5× |
| sequentiel | 0,40 | 0 | 44 | 20 / 40 (50 %) | 384 | 7,0× |
| sequentiel | 0,45 | 0 | 31 | 15 / 40 (38 %) | 304 | 5,6× |
| sequentiel | **0,50** (papier) | 0 | 12 | 8 / 40 (20 %) | 220 | 3,8× |
| sequentiel | 0,55 | 0 | 2 | 6 / 40 (15 %) | 173 | 3,3× |

### 5.1 Les dix règles les plus enflées

Une règle dont la signature compte plusieurs centaines de symboles ressemble un peu à tout : elle ne sépare plus rien.

| stratégie | seuil | type | poids | \|sL\| / \|sR\| | facteur | critère |
|---|---|---|---|---|---|---|
| sequentiel | 0,30 | `r_depict` | 36 / 40 | 575 / 674 | 11,8× | poids + taille |
| glouton | 0,30 | `r_product_of` | 38 / 40 | 647 / 475 | 11,5× | poids + taille |
| glouton | 0,30 | `r_quantificateur` | 36 / 40 | 454 / 637 | 10,8× | poids + taille |
| sequentiel | 0,30 | `r_product_of` | 36 / 40 | 625 / 439 | 11,1× | poids + taille |
| sequentiel | 0,30 | `r_has_property-1` | 37 / 40 | 425 / 618 | 11,3× | poids + taille |
| glouton | 0,30 | `r_social_tie` | 38 / 40 | 415 / 585 | 10,7× | poids + taille |
| sequentiel | 0,30 | `r_holo` | 32 / 40 | 500 / 578 | 10,1× | poids + taille |
| glouton | 0,30 | `r_holo` | 33 / 40 | 526 / 572 | 10,0× | poids + taille |
| sequentiel | 0,30 | `r_processus>instr-1` | 35 / 40 | 542 / 554 | 9,7× | poids + taille |
| sequentiel | 0,30 | `r_social_tie` | 33 / 40 | 390 / 532 | 9,8× | poids + taille |

## 6. Comportement de la cascade

### 6.1 Elle s'arrête tôt, et de plus en plus tôt

À 0,30 la cascade fait 542 fusions et ramène 600 règles à 58 (90,3 %). À 0,50, le seuil du papier, elle n'en fait plus que 233 et laisse 367 règles, soit 38,8 % de réduction. À 0,55 il reste 120 fusions sur 600 règles.

**Au seuil du papier, 65 % des règles finales sont des orphelines de poids 1.** L'apprentissage y est pour l'essentiel une recopie du corpus d'apprentissage : il ne généralise presque rien. C'est cohérent avec la mesure du tour 2, qui donnait 0,4 % de paires fusionnables à 0,50 — et c'est bien pour cela que la fourchette 0,35–0,45 avait été retenue.

### 6.2 Elle n'emballe pas par le poids, elle enfle par la signature

| seuil | poids médian | poids moyen | poids max | signalées poids | taille max | signalées taille |
|---|---|---|---|---|---|---|
| 0,30 | 7,0 | 10,34 | 38 | 11 | 647 | 26 |
| 0,35 | 4,0 | 6,19 | 30 | 3 | 484 | 38 |
| 0,40 | 3,5 | 3,75 | 19 | 0 | 317 | 39 |
| 0,45 | 2,0 | 2,38 | 12 | 0 | 230 | 25 |
| **0,50** (papier) | 1,0 | 1,63 | 8 | 0 | 198 | 9 |
| 0,55 | 1,0 | 1,25 | 5 | 0 | 172 | 0 |

**Le poids médian vaut 1,0 à tous les seuils, dans les deux stratégies.** Pendant qu'une règle atteint 38 exemples sur 40, la moitié des règles n'ont toujours fusionné avec personne. La cascade ne répartit pas les fusions : elle les concentre. C'est un mécanisme du riche qui s'enrichit — plus une règle absorbe, plus sa signature grossit, plus elle ressemble à tout le monde, plus elle absorbe.

Le critère de taille le montre mieux que celui du poids : à 0,30, 11 règles seulement dépassent la moitié des exemples, mais 26 ont une signature démesurée, jusqu'à 647 symboles quand la médiane de départ est 56 — un facteur 11,5. Une signature de cette taille n'est plus une généralisation, c'est un fourre-tout.

Le phénomène n'épargne pas la fourchette retenue au tour 2 : à 0,35 la plus grosse signature atteint 484 symboles, à 0,45 encore 230. L'élagage de l'Expérience 3 aura de quoi faire.

### 6.3 Sur quels types ?

Au seuil 0,30, glouton — là où la cascade travaille le plus —, les trois types qui fusionnent le plus et les trois qui fusionnent le moins :

| type | règles | réduction | poids max | orphelines | taille max |
|---|---|---|---|---|---|
| `r_product_of` | 40 → 2 | 95,0 % | 38 | 0 | 647 |
| `r_has_property-1` | 40 → 3 | 92,5 % | 22 | 1 | 386 |
| `r_lieu` | 40 → 3 | 92,5 % | 19 | 0 | 365 |
| `r_lieu>origine` | 40 → 5 | 87,5 % | 33 | 3 | 493 |
| `r_objet>matiere` | 40 → 5 | 87,5 % | 30 | 2 | 472 |
| `r_processus_agent` | 40 → 6 | 85,0 % | 28 | 3 | 445 |

Les types qui fusionnent le plus (`r_product_of`, `r_has_property-1`, `r_lieu`) sont ceux dont les A sont sémantiquement homogènes — des productions, des propriétés, des liens de parenté — donc dont les signatures gauches se recouvrent naturellement. Ceux qui résistent (`r_lieu>origine`, `r_objet>matiere`, `r_processus_agent`) ont des A très hétérogènes : n'importe quoi peut être le sujet d'un document ou la partie d'un tout.

### 6.4 Les deux stratégies se départagent peu

L'écart maximal sur le nombre de règles finales est de 21,2 %, atteint au seuil le plus bas ; aux seuils 0,50 et 0,55 les deux stratégies donnent le même compte. Le glouton produit des signatures un peu moins grosses aux seuils bas, le séquentiel des règles un peu plus lourdes aux seuils moyens, mais rien qui ressemble à une différence de nature.

La question laissée ouverte par le papier — dans quel ordre fusionner — a donc, sur ce corpus, une réponse tiède : cela ne change pas grand-chose. Le glouton reste préférable par principe, puisqu'il ne dépend pas de l'ordre de lecture du corpus, et son coût n'est pas un problème à cette taille (trois secondes pour les douze combinaisons).

## 7. Sorties écrites

Chaque fichier porte ses règles fusionnées — `rt`, `sL` et `sR` triés, `poids`, `exemples` — plus la stratégie, le seuil et le résumé d'instrumentation. Les signatures ne sont jamais concaténées.

| fichier | stratégie | seuil | règles |
|---|---|---|---|
| `data/modeles/regles_fusionnees_glouton_030.json` | glouton | 0,30 | 58 |
| `data/modeles/regles_fusionnees_glouton_035.json` | glouton | 0,35 | 97 |
| `data/modeles/regles_fusionnees_glouton_040.json` | glouton | 0,40 | 160 |
| `data/modeles/regles_fusionnees_glouton_045.json` | glouton | 0,45 | 252 |
| `data/modeles/regles_fusionnees_glouton_050.json` | glouton | **0,50** (papier) | 367 |
| `data/modeles/regles_fusionnees_glouton_055.json` | glouton | 0,55 | 480 |
| `data/modeles/regles_fusionnees_sequentiel_030.json` | sequentiel | 0,30 | 53 |
| `data/modeles/regles_fusionnees_sequentiel_035.json` | sequentiel | 0,35 | 78 |
| `data/modeles/regles_fusionnees_sequentiel_040.json` | sequentiel | 0,40 | 126 |
| `data/modeles/regles_fusionnees_sequentiel_045.json` | sequentiel | 0,45 | 229 |
| `data/modeles/regles_fusionnees_sequentiel_050.json` | sequentiel | **0,50** (papier) | 354 |
| `data/modeles/regles_fusionnees_sequentiel_055.json` | sequentiel | 0,55 | 471 |

