# Pondération par trait : test complémentaire sur dix graines

**Ce rapport est un éclairage, pas une règle de choix.** La configuration retenue par le projet reste `H 20 · jdm · T2 · TRT tous · SST toutes`, décidée à l'étape 1 de `rapport_signatures_variantes.md` **avant toute lecture du test**. Rien ici ne la révise, et l'incohérence de décision relevée au §3.1 de ce rapport y reste telle quelle : ce qui suit dit seulement avec quelle confiance on peut la lire.

## 1. Protocole

- **10 graines** (42–51) × 5 plis stratifiés par type, sur les 750 exemples d'entraînement. **Le test n'est pas lu.**
- **Méthode figée** : somme · arbre · descente, inchangée.
- **L'unité d'analyse est la graine, pas le pli.** Les 5 plis d'une même graine rebattent les mêmes 750 exemples : les traiter comme autant de mesures indépendantes surestime la précision, et c'était la réserve explicite de `rapport_signatures_variantes.md`. On moyenne donc les 5 plis d'une graine, ce qui donne 10 mesures échangeables.
- **Test de Wilcoxon apparié bilatéral**, loi exacte par énumération des 2^n configurations de signes. Différences nulles écartées, rangs moyens sur les ex aequo. Aucune dépendance externe.
- **Les cinq configurations** se comparent à la même référence binaire `H 20 · binaire · T2 · TRT tous · SST toutes`, sur les mêmes découpages.
- **Ce que le test ne fait pas** : il ne corrige pas la multiplicité (quatre comparaisons à la même référence), et il porte sur les mêmes 750 exemples que l'étude d'origine. Il réduit l'optimisme du compte en plis, il ne l'annule pas.

## 2. Reproductibilité

Les mesures de ce rapport ont **toutes** été calculées sur la machine qui l'écrit (Windows 11, CPython 3.14, `py -3`, en séquentiel). Les mesures de `mesures_cv.json`, elles, **ne pouvaient pas l'être** : jusqu'au commit `fd1b94c`, `variantes_signatures.executer()` exigeait `multiprocessing.get_context("fork")`, absent de Windows — toute configuration non présente au cache y levait `ValueError`. Les 28 configurations d'origine ont donc été produites sur une plateforme POSIX (Linux ou macOS), que le dépôt ne permet pas d'identifier plus précisément : ni journal d'exécution, ni empreinte d'environnement n'y sont conservés. Seules les 3 pondérations partielles, ajoutées au commit `fd1b94c`, l'ont été ici, après l'ajout d'un repli séquentiel.

Le recoupement porte sur les 3 graines communes aux deux études (42, 43, 44), soit 15 plis par configuration, comparés pli à pli.

| pondération | plis comparés | identiques | F1 ailleurs | F1 ici | écart max |
|---|---|---|---|---|---|
| `binaire` | 15 | 15 | 0,789 | 0,789 | 0 |
| `jdm_H` | 15 | 15 | 0,787 | 0,787 | 0 |
| `jdm_TRT` | 15 | 15 | 0,773 | 0,773 | 0 |
| `jdm_SST` | 15 | 15 | 0,792 | 0,792 | 0 |
| `jdm` | 15 | 15 | 0,819 | 0,819 | 0 |

**Tous les F1 sont identiques au bit près.** La référence binaire redonne exactement 0,789 sur ces trois graines, la valeur du rapport des variantes. Le calcul ne dépend donc ni de la plateforme, ni du nombre de processus : les découpages sont tirés d'un générateur à graine fixe et les parcours sont ordonnés. Ce qui venait d'ailleurs est vérifié ici.

## 3. Les cinq configurations sur dix graines

F1 macro moyen des moyennes par graine, et son écart-type **entre graines** — pas entre plis : il est donc plus petit que celui du rapport des variantes, et ce n'est pas une amélioration, seulement une autre quantité.

| trait pondéré | F1 moyen ± é.-t. entre graines | différence à la référence ± é.-t. |
|---|---|---|
| aucun (référence) | 0,786 ± 0,008 | — |
| H seul | 0,784 ± 0,008 | −0,001 ± 0,010 |
| TRT seul | 0,769 ± 0,007 | −0,016 ± 0,008 |
| SST seul | 0,789 ± 0,007 | +0,003 ± 0,004 |
| les trois (`jdm`) | 0,814 ± 0,006 | +0,028 ± 0,006 |

## 4. Test de Wilcoxon apparié

Chaque pondération contre la référence binaire, sur les dix moyennes par graine. « graines favorables » = graines où la pondération fait mieux. « W+ » = somme des rangs des différences positives. Seuil usuel de 0,05, sans correction de multiplicité.

| trait pondéré | différence moyenne | graines favorables | W+ | p (bilatéral, exact) | significatif |
|---|---|---|---|---|---|
| H seul | −0,001 | 3/10 | 18,0 | 0,375 | non |
| TRT seul | −0,016 | 0/10 | 0,0 | 0,002 | **oui** |
| SST seul | +0,003 | 7/10 | 47,0 | 0,049 | **oui** |
| les trois (`jdm`) | +0,028 | 10/10 | 55,0 | 0,002 | **oui** |

## 5. Lecture

- **Le gain des trois traits ensemble tient** : +0,028 de F1, p = 0,002, 10 graines favorables sur 10. Le test en plis bruts l'avait donné pour acquis de justesse (1,06 écart-type) ; sur dix découpages entiers, il passe un test apparié en règle.
- **Un trait pondéré améliore le F1 seul, mais de très peu** : SST seul +0,003 (p = 0,049). Le détail des trois : H seul −0,001 (p = 0,375), TRT seul −0,016 (p = 0,002), SST seul +0,003 (p = 0,049). Ce gain ne survit pas à une correction de multiplicité : avec quatre comparaisons, le seuil de Bonferroni est 0,0167. Et un tel écart, de l'ordre du millième de F1, ne pèse rien devant celui des trois traits ensemble.
- **Pondérer un seul trait peut nuire** : TRT seul −0,016 (p = 0,002, 0 graines favorables sur 10). C'est le résultat le plus net du tableau, et il va contre l'idée qu'on pourrait alléger la pondération en ne gardant que le trait le plus fourni. TRT pèse à lui seul une trentaine des cinquante symboles d'une signature (§4 du rapport des variantes : le retirer fait tomber la taille médiane de 51 à 22) ; le pondérer pendant que H et SST restent à 1 ne fait que déséquilibrer la norme du vecteur en sa faveur.
- **Le tout reste différent de la somme de ses parties** : les trois gains séparés valent −0,014 au total, contre +0,028 pour les trois ensemble. Pondérer un seul trait change la part qu'il occupe dans la norme du vecteur face à deux traits restés à 1 ; les trois ensemble, le poids d'un symbole veut dire la même chose des deux côtés du cosinus. C'est une conjonction, pas l'addition de trois effets.
- **Ce que ce test ne dit pas.** Il ne corrige pas la multiplicité des quatre comparaisons ; il réutilise les mêmes 750 exemples que l'étude d'origine, donc il ne constitue pas une réplication indépendante ; et il ne porte que sur l'entraînement. Le F1 de test de la configuration retenue est dans `rapport_final_signatures.md`, lu une seule fois, et son propre test des signes y donnait p = 0,27.
- **Aucune décision n'en découle.** La configuration retenue a été choisie avant la lecture du test ; la changer maintenant, à la lumière d'une analyse faite après, reviendrait à ajuster le choix sur un test déjà dépensé.

## 6. Sorties

- `data/signatures_variantes/mesures_ponderation.json` : les 50 mesures de chacune des cinq configurations, qui permettent de reconstruire ce rapport sans rien recalculer (`--rapport-seulement`).
- `data/signatures/` n'est pas touché, et le test n'est pas lu.
