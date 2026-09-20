# Signatures, vocabulaire et règles

Généré par `src/signatures.py` depuis `data/collecte/termes_jdm.jsonl` et `data/corpus/clean/`. Aucun appel réseau.

Une signature est un ensemble plat de symboles binaires préfixés par leur provenance (`H:`, `TRT:`, `SST:`), plus le terme lui-même sans préfixe. Une règle est `R = < sL, sR, rt >` : les deux signatures restent séparées, parce que la position porte le sens — « vin de France » n'est pas « France de vin ».

### Coupures appliquées

- **H** : top 20 par poids décroissant, poids > 0. Doublons de casse fusionnés **avant** la coupure, sur la forme normalisée, en gardant la forme d'origine la mieux pondérée. Préfixes de langue conservés (`H_EXCLURE_PREFIXES_LANGUE = False`).
- **TRT** : tous les types entrants d'effectif > 0, sauf 15 types non sémantiques exclus. Aucun seuil d'effectif.
- **SST** : toutes les annotations. Annotations morphologiques conservées (`SST_EXCLURE_MORPHO = False`).

Tous ces seuils sont dans `config.py`. La collecte est restée brute : les faire varier ne demande que de relancer ce script.

## 1. Vocabulaire global

**12 738 symboles distincts**, numérotés de 0 à 12737. Un seul vocabulaire pour les 15 types : sans cela, la même dimension ne désignerait pas le même symbole d'un type à l'autre.

| préfixe | symboles | part |
|---|---|---|
| H | 10 709 | 84,1 % |
| TRT | 128 | 1,0 % |
| SST | 34 | 0,3 % |
| terme | 1 867 | 14,7 % |

La disproportion est attendue : TRT est borné par le nombre de types de relations de JDM et SST par le nombre d'annotations existantes, alors que H est ouvert — chaque hyperonyme distinct est un symbole de plus.

## 2. Taille des signatures

Sur les 1 867 termes collectés.

| ensemble | min | médiane | max | total |
|---|---|---|---|---|
| signature complète | 2 | 49 | 94 | 90 396 |
| dont H | 0 | 20 | 20 | 28 437 |
| dont TRT | 1 | 28 | 65 | 54 954 |
| dont SST | 0 | 2 | 13 | 5 138 |

La signature complète compte toujours le terme lui-même : sa taille minimale est donc 1, jamais 0.

## 3. Taille des signatures par type de relation et par rôle

Repère les types mal dotés : un type dont les signatures sont courtes des deux côtés donnera des similarités faibles et peu fiables.

| relation | règles | médiane \|sL\| (A) | étendue A | médiane \|sR\| (B) | étendue B |
|---|---|---|---|---|---|
| `r_depict` | 80 | 50 | 13–89 | 61 | 12–91 |
| `r_has_causatif` | 80 | 35.5 | 3–83 | 64 | 13–89 |
| `r_has_property-1` | 80 | 44 | 12–75 | 58 | 23–94 |
| `r_holo` | 80 | 48 | 13–78 | 63 | 22–91 |
| `r_lieu` | 80 | 34.5 | 2–77 | 38 | 5–77 |
| `r_lieu>origine` | 80 | 50 | 3–90 | 41 | 10–67 |
| `r_objet>matiere` | 80 | 56.5 | 20–78 | 49 | 10–89 |
| `r_own-1` | 80 | 52.5 | 12–91 | 53 | 31–87 |
| `r_processus>instr-1` | 80 | 52 | 15–88 | 54.5 | 12–89 |
| `r_processus_agent` | 80 | 55.5 | 6–94 | 54 | 2–91 |
| `r_processus_patient` | 80 | 46 | 11–89 | 59 | 6–91 |
| `r_product_of` | 80 | 62.5 | 26–88 | 51.5 | 9–81 |
| `r_quantificateur` | 80 | 39 | 4–77 | 65.5 | 13–94 |
| `r_social_tie` | 80 | 52.5 | 22–82 | 54.5 | 5–87 |
| `r_topic` | 80 | 62 | 28–88 | 63 | 12–94 |

## 4. Signatures vides ou quasi vides

Termes dont la signature compte moins de 3 symboles, terme lui-même inclus : **2**.

| terme | \|signature\| | rôle | type(s) de relation | symboles |
|---|---|---|---|---|
| « bayous » | 2 | A | `r_lieu` | `TRT:r_isa`, `bayous` |
| « cheminots » | 2 | B | `r_processus_agent` | `TRT:r_isa`, `cheminots` |

## 5. Les symboles les plus fréquents

Sur 1 867 termes. **Un symbole présent partout ne discrimine rien** : il gonfle toutes les similarités de la même façon. Ce tableau est là pour que ces symboles soient visibles avant l'étape 4, pas pour les retirer maintenant.

| symbole | trait | termes | part |
|---|---|---|---|
| `TRT:r_isa` | TRT | 1 839 | 98,5 % |
| `TRT:r_syn` | TRT | 1 782 | 95,4 % |
| `TRT:r_hypo` | TRT | 1 766 | 94,6 % |
| `TRT:r_carac-1` | TRT | 1 746 | 93,5 % |
| `TRT:r_domain-1` | TRT | 1 733 | 92,8 % |
| `TRT:r_has_part` | TRT | 1 721 | 92,2 % |
| `TRT:r_lieu-1` | TRT | 1 635 | 87,6 % |
| `TRT:r_sentiment-1` | TRT | 1 617 | 86,6 % |
| `TRT:r_holo` | TRT | 1 616 | 86,6 % |
| `TRT:r_agent` | TRT | 1 545 | 82,8 % |
| `TRT:r_patient` | TRT | 1 515 | 81,1 % |
| `TRT:r_accomp` | TRT | 1 394 | 74,7 % |
| `TRT:r_lieu` | TRT | 1 196 | 64,1 % |
| `TRT:r_interact_with` | TRT | 1 165 | 62,4 % |
| `TRT:r_make` | TRT | 1 152 | 61,7 % |
| `TRT:r_make_use_of` | TRT | 1 119 | 59,9 % |
| `TRT:r_family` | TRT | 1 109 | 59,4 % |
| `TRT:r_anto` | TRT | 1 033 | 55,3 % |
| `TRT:r_processus>agent` | TRT | 1 022 | 54,7 % |
| `TRT:r_concerning` | TRT | 1 014 | 54,3 % |
| `TRT:r_has_causatif` | TRT | 989 | 53,0 % |
| `TRT:r_processus>instr-1` | TRT | 952 | 51,0 % |
| `TRT:r_has_conseq` | TRT | 920 | 49,3 % |
| `TRT:r_has_euphemisme` | TRT | 893 | 47,8 % |
| `TRT:r_has_antimagn` | TRT | 783 | 41,9 % |
| `TRT:r_symptomes-1` | TRT | 780 | 41,8 % |
| `TRT:r_require` | TRT | 777 | 41,6 % |
| `TRT:r_object>mater` | TRT | 765 | 41,0 % |
| `TRT:r_is_instance_of` | TRT | 756 | 40,5 % |
| `TRT:r_instr` | TRT | 755 | 40,4 % |

Aucun symbole n'est présent chez la totalité des termes.

Symbole le plus répandu de chaque trait :

| trait | symbole | termes | part |
|---|---|---|---|
| H | `H:lieu` | 393 | 21,0 % |
| TRT | `TRT:r_isa` | 1 839 | 98,5 % |
| SST | `SST:PLACE` | 671 | 35,9 % |
| terme | `AVC` | 1 | 0,1 % |

Le classement ci-dessus n'est peuplé que de symboles TRT, et ce n'est pas un artefact : il n'y a que 128 types de relations entrantes pour 1 871 termes, donc chacun est forcément très partagé, alors que les 10 717 hyperonymes se répartissent la même population. Autrement dit TRT apporte de la masse commune et H du pouvoir discriminant — ce que l'étape 4 devra arbitrer.

## 6. Vérification manuelle de `similarite`

La fonction calcule le cosinus sur les ensembles : `|s1 ∩ s2| / racine(|s1| × |s2|)`. Trois cas calculés à la main et comparés à la sortie de la fonction.

| cas | calcul à la main | attendu | obtenu | verdict |
|---|---|---|---|---|
| Recouvrement partiel | 2 communs, \|s1\| = 4, \|s2\| = 4 → 2 / racine(4 × 4) = 2 / 4 | 0,5000 | 0,5000 | OK |
| Tailles inégales, aucun symbole commun | 0 commun, \|s1\| = 3, \|s2\| = 2 → 0 / racine(3 × 2) = 0 | 0,0000 | 0,0000 | OK |
| Signature vide | \|s1\| = 0 : la fonction retourne 0.0 sans diviser par zéro | 0,0000 | 0,0000 | OK |

- Identité : `similarite(s, s)` = 1,0000 (attendu 1,0000).
- Symétrie : `similarite(s1, s2)` = 0,7071 et `similarite(s2, s1)` = 0,7071.

**0 écart(s) constaté(s).**

## 7. Sorties écrites

Le vocabulaire (12 738 symboles) et les 1 200 règles de base sont calculés pour ce rapport mais plus écrits sur disque : personne ne les relisait. `grasp.py` reconstruit ses règles depuis le corpus et les signatures.

| fichier | contenu |
|---|---|
| `data/signatures/signatures_termes.json` | 1 867 termes -> liste triée de symboles |

### Cas signalés

- **Termes absents de JDM : 0.** Leur signature est réduite au terme lui-même. 
- **Lignes de corpus sans règle : 0.** Un découpage ambigu laisse A et B vides dans le corpus propre : aucune règle ne peut en être tirée, et le corpus n'est pas modifié pour y remédier.
- **Termes collectés hors corpus : 4.** Candidats de découpage rejetés par l'arbitrage : collectés à l'étape 2, ils ne reçoivent pas de signature. « Ivoire », « Sud », « cacao de Côte », « diamants d'Afrique ».

## 8. Hors périmètre

Cette étape ne fusionne aucune règle, n'applique aucun seuil de 0,5, n'exécute pas GRASP-it, ne classe rien, n'évalue rien et ne calcule aucune matrice de similarité complète. La collecte et le corpus sont inchangés.
