# Diagnostic du trait TRT : huit politiques de sélection

Mesure comparée, sans décision. Rien n'est appliqué : `config.py`, le corpus, la collecte et `data/signatures/` sont inchangés.

## 1. Méthode

- **Population** : 1867 termes distincts du corpus propre, signatures reconstruites en mémoire pour chaque politique. Les fichiers de `data/signatures/` ne sont ni lus ni réécrits.
- **Bruit** : 2000 paires de termes distincts tirées dans tout le corpus, `random.Random(42)`. Deux termes tirés au hasard n'ont aucune raison de se ressembler : leur similarité est le plancher que toute politique doit faire baisser.
- **Signal** : 3000 paires au total, 200 par type de relation, moitié A-A moitié B-B, jamais un terme avec lui-même. Deux A d'un même type jouent le même rôle sémantique : leur similarité est ce que la politique doit préserver.
- **Paires tirées une seule fois** et réutilisées par les huit politiques : les écarts observés viennent des politiques, pas du tirage.
- **Exclusion commune** : les 15 types non sémantiques de `config.TRT_TYPES_EXCLUS` sont retirés sous les huit politiques, y compris P0. Ce n'est pas eux qu'on mesure.
- **Seuil de fusion** : 0,5, valeur du papier. La colonne « fond > 0,5 » est le taux de fusion parasite attendu à l'étape 4.

P6 retire 11 types présents chez plus de 80 % des termes : `r_agent`, `r_carac-1`, `r_domain-1`, `r_has_part`, `r_holo`, `r_hypo`, `r_isa`, `r_lieu-1`, `r_patient`, `r_sentiment-1`, `r_syn`.

## 1.1 La règle des 80 % retrouve seule une partie de la liste faite à la main

Les deux filtres sont disjoints par construction : la fréquence documentaire de P6 est calculée APRÈS le retrait des 15 types de `config.TRT_TYPES_EXCLUS`, donc les 11 types qu'elle retire en plus sont forcément d'autres types. Mais on peut poser la question autrement : si l'on appliquait la règle des 80 % aux types BRUTS, sans liste faite à la main, que retrouverait-elle ?

**9 des 15 types exclus à la main**, dépassant tous le seuil. Une liste bâtie sur l'intuition est donc en grande partie re-dérivable par une mesure, ce qui est rassurant pour les deux.

| type retrouvé par la règle | fréquence documentaire |
|---|---|
| `r_associated` | 100,0 % |
| `r_aki` | 99,5 % |
| `r_context` | 99,5 % |
| `r_variante` | 98,4 % |
| `r_wiki` | 96,9 % |
| `r_translation` | 93,6 % |
| `r_lemma` | 89,4 % |
| `r_der_morpho` | 85,5 % |
| `r_meaning/glose` | 82,4 % |

Les 6 types que la règle ne retrouve pas sont trop rares pour être pris par un seuil de fréquence : ils resteraient dans les signatures sans la liste faite à la main. Les deux filtres sont complémentaires, pas redondants.

| type que la règle manque | fréquence documentaire |
|---|---|
| `r_sing_form` | 79,1 % |
| `r_raff_sem-1` | 60,6 % |
| `r_homophone` | 27,2 % |
| `r_masc` | 16,1 % |
| `r_error` | 6,7 % |
| `r_locution` | 2,0 % |

## 2. Comparaison des huit politiques

Colonnes (a) à (e) : bruit moyen, médian et 90e centile ; signal médian ; écart signal − bruit ; part des paires de fond au-dessus du seuil de fusion ; taille de signature min / médiane / max.

Deux colonnes ajoutées pour l'arbitrage. Le **rapport** signal/bruit corrige un biais de l'écart absolu, qui avantage mécaniquement les politiques laissant les similarités hautes. **Signal > 0,5** est la contrepartie de (d) : le taux de fusion UTILE, celui qu'il ne faut pas sacrifier en faisant tomber le bruit.
**Pire type** est l'écart du type de relation le moins bien servi : une moyenne flatteuse peut masquer un type sacrifié.

|  | rôle | politique | bruit moy. (a) | bruit méd. (a) | bruit c90 (a) | signal méd. (b) | écart (c) | rapport | fond > 0,5 (d) | signal > 0,5 | pire type (c) | taille (e) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **P0** | témoin | actuelle : tous les types d'effectif > 0 | 0,363 | 0,363 | 0,500 | 0,455 | **0,092** | 1,25 | 10,05 % | 33,03 % | 0,052 (`r_lieu`) | 2 / 49 / 94 |
| **P1** | candidate | top 5 types par effectif décroissant | 0,109 | 0,086 | 0,208 | 0,169 | **0,083** | 1,97 | 0,75 % | 2,47 % | 0,020 (`r_topic`) | 2 / 28 / 39 |
| **P2** | candidate | top 10 types par effectif décroissant | 0,184 | 0,171 | 0,297 | 0,254 | **0,082** | 1,48 | 1,05 % | 4,67 % | 0,005 (`r_topic`) | 2 / 33 / 44 |
| **P3** | candidate | top 15 types par effectif décroissant | 0,253 | 0,247 | 0,364 | 0,327 | **0,081** | 1,33 | 1,60 % | 7,60 % | 0,024 (`r_topic`) | 2 / 38 / 49 |
| **P4** | candidate | effectif >= 5 % du type dominant du terme | 0,132 | 0,113 | 0,251 | 0,195 | **0,082** | 1,72 | 0,95 % | 3,10 % | 0,000 (`r_topic`) | 2 / 28 / 46 |
| **P5** | candidate | effectif >= 10 % du type dominant du terme | 0,102 | 0,079 | 0,202 | 0,157 | **0,078** | 1,99 | 0,70 % | 2,47 % | 0,005 (`r_topic`) | 2 / 26 / 41 |
| **P6** | candidate | retrait des types présents chez plus de 80 % des termes | 0,208 | 0,197 | 0,390 | 0,327 | **0,130** | 1,66 | 1,85 % | 9,83 % | 0,056 (`r_depict`) | 1 / 39 / 83 |
| **P7** | témoin | H et SST seuls, aucun TRT (borne basse) | 0,039 | 0,000 | 0,122 | 0,080 | **0,080** | — | 0,45 % | 1,77 % | 0,000 (`r_has_causatif`) | 1 / 23 / 34 |

## 3. Détail par type de relation

Pour les trois politiques les mieux classées, la médiane du signal de chaque type, l'écart avec le bruit de la même politique, et la taille médiane des signatures des termes du type. Un type dont l'écart s'effondre serait sacrifié au profit de la moyenne.

| type | P6 signal | P6 écart | P6 taille | P1 signal | P1 écart | P1 taille | P2 signal | P2 écart | P2 taille |
|---|---|---|---|---|---|---|---|---|---|
| `r_depict` | 0,253 | 0,056 | 46 | 0,120 | 0,034 | 29 | 0,201 | 0,029 | 34 |
| `r_has_causatif` | 0,356 | 0,159 | 38 | 0,122 | 0,036 | 23 | 0,206 | 0,034 | 28 |
| `r_has_property-1` | 0,357 | 0,160 | 41 | 0,184 | 0,098 | 28 | 0,264 | 0,092 | 33 |
| `r_holo` | 0,297 | 0,100 | 46 | 0,164 | 0,078 | 30 | 0,253 | 0,081 | 34 |
| `r_lieu` | 0,262 | 0,065 | 30 | 0,248 | 0,162 | 28 | 0,345 | 0,174 | 33 |
| `r_lieu>origine` | 0,293 | 0,096 | 34 | 0,209 | 0,123 | 28 | 0,292 | 0,121 | 33 |
| `r_objet>matiere` | 0,304 | 0,107 | 42 | 0,217 | 0,131 | 28 | 0,290 | 0,119 | 33 |
| `r_own-1` | 0,345 | 0,148 | 42 | 0,208 | 0,122 | 29 | 0,296 | 0,124 | 34 |
| `r_processus>instr-1` | 0,354 | 0,157 | 43 | 0,179 | 0,093 | 27 | 0,260 | 0,088 | 32 |
| `r_processus_agent` | 0,337 | 0,140 | 43 | 0,168 | 0,082 | 28 | 0,239 | 0,067 | 33 |
| `r_processus_patient` | 0,388 | 0,191 | 42 | 0,209 | 0,123 | 24 | 0,277 | 0,106 | 30 |
| `r_product_of` | 0,335 | 0,138 | 46 | 0,143 | 0,057 | 29 | 0,233 | 0,061 | 34 |
| `r_quantificateur` | 0,277 | 0,080 | 43 | 0,136 | 0,050 | 28 | 0,223 | 0,051 | 33 |
| `r_social_tie` | 0,322 | 0,125 | 42 | 0,207 | 0,121 | 29 | 0,298 | 0,126 | 34 |
| `r_topic` | 0,337 | 0,140 | 51 | 0,106 | 0,020 | 28 | 0,177 | 0,005 | 33 |

Les deux types à surveiller sont `r_lieu` et `r_lieu>origine` : leurs signatures sont déjà les plus courtes du corpus, ce sont eux qui souffriraient le plus d'une coupure trop franche.

## 4. Les deux types les plus fragiles, sous les huit politiques

Le tableau de la section 3 ne couvre que les trois meilleures politiques. Celui-ci suit `r_lieu` et `r_lieu>origine` partout, pour vérifier qu'aucune politique ne les fait décrocher en silence.

|  | `r_lieu` signal | `r_lieu` écart | `r_lieu` taille | `r_lieu>origine` signal | `r_lieu>origine` écart | `r_lieu>origine` taille |
|---|---|---|---|---|---|---|
| **P0** | 0,415 | 0,052 | 38 | 0,421 | 0,058 | 42 |
| **P1** | 0,248 | 0,162 | 28 | 0,209 | 0,123 | 28 |
| **P2** | 0,345 | 0,174 | 33 | 0,292 | 0,121 | 33 |
| **P3** | 0,394 | 0,148 | 37 | 0,364 | 0,117 | 38 |
| **P4** | 0,276 | 0,162 | 29 | 0,248 | 0,134 | 31 |
| **P5** | 0,240 | 0,161 | 27 | 0,207 | 0,129 | 28 |
| **P6** | 0,262 | 0,065 | 30 | 0,293 | 0,096 | 34 |
| **P7** | 0,120 | 0,120 | 23 | 0,142 | 0,142 | 23 |

## 5. Masse TRT restante

Nombre moyen de symboles TRT par signature, et taille médiane. C'est la grandeur que le diagnostic cherche à réduire : chaque symbole TRT quasi universel ajoute du recouvrement entre deux termes sans rapport.

|  | politique | TRT moyen | taille médiane |
|---|---|---|---|
| **P0** | actuelle : tous les types d'effectif > 0 | 29,4 | 49 |
| **P1** | top 5 types par effectif décroissant | 5,0 | 28 |
| **P2** | top 10 types par effectif décroissant | 9,8 | 33 |
| **P3** | top 15 types par effectif décroissant | 14,3 | 38 |
| **P4** | effectif >= 5 % du type dominant du terme | 7,2 | 28 |
| **P5** | effectif >= 10 % du type dominant du terme | 4,8 | 26 |
| **P6** | retrait des types présents chez plus de 80 % des termes | 19,5 | 39 |
| **P7** | H et SST seuls, aucun TRT (borne basse) | 0,0 | 23 |

## 6. Recommandation

### Ce que disent les deux témoins

**P0, l'état actuel** : bruit médian 0,363, signal médian 0,455, écart 0,092. Surtout, 10,05 % des paires de termes tirés au hasard dépassent déjà le seuil de fusion de 0,5. Une paire sur dix sans aucun rapport serait fusionnée à l'étape 4. Le diagnostic confirme le problème, et il est plus net que la seule médiane ne le laissait voir.

**P7, sans aucun TRT** : bruit médian 0,000 — plus de la moitié des paires tirées au hasard ne partagent alors strictement rien — signal médian 0,080, écart 0,080. H et SST seuls séparent donc déjà aussi bien que plusieurs des politiques TRT testées. C'est l'enseignement de cette borne : TRT doit gagner sa place, il ne l'a pas d'office.

### Le mécanisme que les mesures mettent au jour

Les cinq politiques de saillance par terme (P1 à P5) font toutes chuter le bruit — de 0,363 à 0,086 pour P1 — sans améliorer l'écart pour autant. La raison se lit dans la colonne « pire type » :

|  | pire type | écart | les trois plus bas |
|---|---|---|---|
| **P1** | `r_topic` | 0,020 | `r_topic` 0,020, `r_depict` 0,034, `r_has_causatif` 0,036 |
| **P2** | `r_topic` | 0,005 | `r_topic` 0,005, `r_depict` 0,029, `r_has_causatif` 0,034 |
| **P3** | `r_topic` | 0,024 | `r_topic` 0,024, `r_has_causatif` 0,035, `r_depict` 0,036 |
| **P4** | `r_topic` | 0,000 | `r_topic` 0,000, `r_depict` 0,033, `r_has_causatif` 0,035 |
| **P5** | `r_topic` | 0,005 | `r_topic` 0,005, `r_has_causatif` 0,026, `r_depict` 0,030 |
| **P6** | `r_depict` | 0,056 | `r_depict` 0,056, `r_lieu` 0,065, `r_quantificateur` 0,080 |

P1 à P5 s'effondrent toutes sur le même type, et pour la même raison. Garder les N types d'effectif le plus élevé pour un terme, c'est garder ses types les plus fréquents — donc `r_isa`, `r_syn`, `r_hypo`, ceux-là mêmes qui sont universels. La saillance par terme sélectionne l'universalité et jette les types rares, qui sont précisément les discriminants. Elle raccourcit les signatures sans les spécialiser : le bruit baisse, le signal baisse autant.

P6 fait l'inverse : elle retire les types universels et garde les rares. C'est la seule politique de la liste qui coupe selon la fréquence DOCUMENTAIRE — la présence dans le corpus — et non selon l'effectif interne à un terme. La distinction est tout le diagnostic.

### Les deux classements

| classement | 1er | 2e | 3e |
|---|---|---|---|
| écart global (c) | **P6** (0,130) | **P1** (0,083) | **P2** (0,082) |
| écart du pire type | **P6** (0,056, `r_depict`) | **P3** (0,024, `r_topic`) | **P1** (0,020, `r_topic`) |

Les deux classements désignent **P6**, ce qui n'allait pas de soi : une politique peut très bien gagner en moyenne en sacrifiant un type. Ici P6 a à la fois le meilleur écart global (0,130, contre 0,083 pour la suivante) et le meilleur plancher (0,056, contre 0,024). Aucun type n'est sacrifié : son plus mauvais type reste au-dessus du MEILLEUR plancher de toutes les autres candidates.

### Les deux types sous surveillance

Ce sont ceux qui ont le moins de matière à perdre : leurs signatures sont les plus courtes du corpus.

| type | P0 écart | P6 écart | P2 écart |
|---|---|---|---|
| `r_lieu` | 0,052 | 0,065 | 0,174 |
| `r_lieu>origine` | 0,058 | 0,096 | 0,121 |

Nuance honnête : sur `r_lieu` pris isolément, P2 fait mieux que P6 (0,174 contre 0,065). P6 retire `r_lieu-1`, présent chez plus de 80 % des termes, et ce type portait une part du caractère de lieu. Mais P2 paie ce gain local par un effondrement sur `r_topic` (0,005), là où P6 tient 0,140. Aucun des deux types de lieu n'est sous le plancher de P6, et les deux restent au-dessus de leur valeur sous P0.

### Recommandation

**P6 — retrait des types présents chez plus de 80 % des termes.**

Les chiffres :

- écart signal/bruit 0,130, contre 0,092 pour P0 et au mieux 0,083 pour les autres candidates ;
- plancher par type 0,056 sur `r_depict`, quand la meilleure des autres plafonne à 0,024 ;
- fusions parasites ramenées de 10,05 % à 1,85 % des paires de fond : c'est le problème qui motivait ce diagnostic, divisé par 5,4 ;
- fusions utiles conservées à 9,83 % des paires de même rôle, contre 2,47 % pour P1 : c'est le point où les politiques de saillance perdent tout ;
- bruit médian 0,197 contre 0,363, rapport signal/bruit 1,66 contre 1,25 ;
- masse TRT 19,5 symboles par signature contre 29,4, taille médiane 39 contre 49.

**Ce que cela suppose de changer** : remplacer le filtre d'effectif par un filtre de fréquence documentaire, calculé sur le corpus entier et non terme par terme. Les 15 types déjà exclus par `config.TRT_TYPES_EXCLUS` le restent ; le nouveau filtre s'y ajoute et en recouvre une partie.

**Deux réserves.** Le seuil de 80 % n'a pas été optimisé : il vient de l'énoncé, pas d'une recherche. Un balayage de 60 % à 95 % dirait s'il est au bon endroit. Et la liste des types retirés dépend de CE corpus : changer les 1867 termes change la liste. C'est cohérent avec la méthode du papier, qui définit la saillance relativement à une population, mais cela veut dire que la liste doit être recalculée, jamais figée en dur.

Si l'étape 4 fusionne trop peu avec P6, la correction est de baisser le seuil de 0,5, pas de revenir à P0 : sous P0 les fusions supplémentaires seraient majoritairement parasites.

Ce script ne touche pas à `config.py` : la décision reste à prendre.

