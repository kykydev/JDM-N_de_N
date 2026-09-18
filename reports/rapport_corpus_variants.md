# Rapport de contrôle du corpus

Généré par `src/corpus_check.py` sur `data/corpus/variants/`. Rien n'a été supprimé ni modifié dans `data/corpus/variants/` : ce rapport signale, les décisions restent manuelles.

## 1. Comptes par fichier

| fichier | relation | lignes | parsées | train | test | ambiguës | anomalies | statut |
|---|---|---|---|---|---|---|---|---|
| corpus_r_depict | r_depict | 80 | 80 | 50 | 30 | 0 | 0 | OK |
| corpus_r_has_causatif | r_has_causatif | 80 | 80 | 50 | 30 | 0 | 0 | OK |
| corpus_r_has_property-1 | r_has_property-1 | 80 | 80 | 50 | 30 | 0 | 0 | OK |
| corpus_r_holonymie | r_holo | 80 | 80 | 50 | 30 | 0 | 0 | OK |
| corpus_r_lieu | r_lieu | 80 | 80 | 50 | 30 | 0 | 0 | OK |
| corpus_r_lieu_origine | r_lieu>origine | 80 | 80 | 50 | 30 | 2 | 0 | OK |
| corpus_r_objet_matiere | r_objet>matiere | 80 | 80 | 50 | 30 | 0 | 0 | OK |
| corpus_r_own-1 | r_own-1 | 80 | 80 | 50 | 30 | 0 | 0 | OK |
| corpus_r_processus_agent | r_processus_agent | 80 | 80 | 50 | 30 | 0 | 0 | OK |
| corpus_r_processus_instr-1 | r_processus>instr-1 | 80 | 80 | 50 | 30 | 0 | 0 | OK |
| corpus_r_processus_patient | r_processus_patient | 80 | 80 | 50 | 30 | 0 | 0 | OK |
| corpus_r_product_of | r_product_of | 80 | 80 | 50 | 30 | 0 | 0 | OK |
| corpus_r_quantificateur | r_quantificateur | 80 | 80 | 50 | 30 | 0 | 0 | OK |
| corpus_r_social_tie | r_social_tie | 80 | 80 | 50 | 30 | 0 | 0 | OK |
| corpus_r_topic | r_topic | 80 | 80 | 50 | 30 | 0 | 0 | OK |

Total : 1200 syntagmes parsés sur 1200 lignes.

## 2. Lignes malformées et anomalies

Aucune.

## 3. Cas ambigus (plusieurs prépositions)

Non tranchés ici : résolution via la base de connaissances à l'étape 2 (papier, §4.1). Ces lignes ont A, B, det et definitude vides dans les CSV nettoyés ; les candidats sont dans la colonne `candidats`.

| fichier | ligne | split | syntagme | découpages candidats |
|---|---|---|---|---|
| corpus_r_lieu_origine | 39 | train | **cacao de Côte d'Ivoire** | A=`cacao` · B=`Côte d'Ivoire` (de; NoDet+Def)<br>A=`cacao de Côte` · B=`Ivoire` (d'; NoDet+Def) |
| corpus_r_lieu_origine | 48 | train | **diamants d'Afrique du Sud** | A=`diamants` · B=`Afrique du Sud` (d'; NoDet+Def)<br>A=`diamants d'Afrique` · B=`Sud` (du; Det+Def) |

## 4. Doublons exacts intra-fichier

Aucun.

## 5. Doublons inter-fichiers (classification multiple)

Même syntagme (après normalisation casse/espaces/NFC) présent dans plusieurs types. À arbitrer manuellement ; rien n'est supprimé.

Aucun.

## 6. Doublons de la paire (A, B) normalisée

Paires identiques après normalisation (minuscules, NFC, espaces, apostrophes), que le syntagme de surface soit identique ou non. Les lignes ambiguës sont exclues. Une même paire avec des déterminants différents dans deux types (ex. « photo de famille » vs « photo d'une famille ») est précisément le cas que le trait de définitude doit séparer.

Aucun.

## 7. Diversité lexicale par type

Nombre de termes A et B distincts (formes normalisées, lignes non ambiguës) et termes apparaissant au moins 3 fois dans un même type.

| fichier | n | A distincts | B distincts | A vus ≥2 fois | B vus ≥2 fois | A répétés (≥3) | B répétés (≥3) |
|---|---|---|---|---|---|---|---|
| corpus_r_depict | 80 | 51 | 80 | 29 | 0 | — | — |
| corpus_r_has_causatif | 80 | 80 | 79 | 0 | 1 | — | — |
| corpus_r_has_property-1 | 80 | 80 | 80 | 0 | 0 | — | — |
| corpus_r_holonymie | 80 | 79 | 80 | 1 | 0 | — | — |
| corpus_r_lieu | 80 | 79 | 78 | 1 | 2 | — | — |
| corpus_r_lieu_origine | 78 | 74 | 78 | 4 | 0 | — | — |
| corpus_r_objet_matiere | 80 | 75 | 80 | 4 | 0 | mur (3) | — |
| corpus_r_own-1 | 80 | 79 | 80 | 1 | 0 | — | — |
| corpus_r_processus_agent | 80 | 79 | 80 | 1 | 0 | — | — |
| corpus_r_processus_instr-1 | 80 | 78 | 79 | 1 | 1 | clé (3) | — |
| corpus_r_processus_patient | 80 | 80 | 80 | 0 | 0 | — | — |
| corpus_r_product_of | 80 | 79 | 79 | 1 | 1 | — | — |
| corpus_r_quantificateur | 80 | 79 | 76 | 1 | 4 | — | — |
| corpus_r_social_tie | 80 | 75 | 74 | 5 | 5 | — | accusé (3) |
| corpus_r_topic | 80 | 75 | 80 | 4 | 0 | salon (3) | — |

## 8. Répartition des traits de définitude par type

Règles (§4.4.2) : Det = du, de la, de l', des, d'un, d'une ; NoDet = de, d' ; Def = déterminant défini ; NoDef = absence de déterminant ou indéfini ; B à majuscule initiale (entité nommée) ⇒ Def forcé. Lignes ambiguës exclues.

| fichier | Det+Def | Det+NoDef | NoDet+Def | NoDet+NoDef |
|---|---|---|---|---|
| corpus_r_depict | 3 | 77 | 0 | 0 |
| corpus_r_has_causatif | 61 | 10 | 0 | 9 |
| corpus_r_has_property-1 | 68 | 12 | 0 | 0 |
| corpus_r_holonymie | 70 | 7 | 0 | 3 |
| corpus_r_lieu | 12 | 0 | 68 | 0 |
| corpus_r_lieu_origine | 15 | 0 | 63 | 0 |
| corpus_r_objet_matiere | 0 | 0 | 0 | 80 |
| corpus_r_own-1 | 70 | 10 | 0 | 0 |
| corpus_r_processus_agent | 70 | 10 | 0 | 0 |
| corpus_r_processus_instr-1 | 5 | 0 | 0 | 75 |
| corpus_r_processus_patient | 70 | 10 | 0 | 0 |
| corpus_r_product_of | 70 | 10 | 0 | 0 |
| corpus_r_quantificateur | 0 | 0 | 0 | 80 |
| corpus_r_social_tie | 70 | 10 | 0 | 0 |
| corpus_r_topic | 8 | 0 | 1 | 71 |
| **total** | **592** | **156** | **132** | **318** |

Contrôle des exemples du papier :

- chat du rabbin → Det+Def (OK)
- écran de cinéma → NoDet+NoDef (OK)
- tableau de Chagall → NoDet+Def (OK)

## 9. Fichier des termes

`data/corpus/clean/termes.csv` : 2064 couples (terme, rôle) distincts, formes originales conservées. `nb_occurrences` compte les lignes non ambiguës ; `nb_candidats_ambigus` compte les apparitions comme candidat d'une ligne ambiguë. 8 terme(s) n'existent que comme candidats.

