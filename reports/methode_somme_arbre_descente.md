# Méthode retenue : somme · arbre · descente

**En une phrase** : chaque type de relation est résumé par un profil
moyen de ses exemples, et un syntagme est rangé dans le type dont le
profil lui ressemble le plus ; l'arbre ne sert qu'à retirer de ce
profil les quelques exemples qui l'en éloignent (§3 et §4 : les arbres
obtenus sont des peignes, pas des hiérarchies de sous-familles).

> **Note sur les poids.** Les exemples de ce document montrent des
> feuilles à 1 : un symbole présent vaut 1, absent vaut 0. C'est un
> schéma pédagogique, et il reste exact pour la *structure* — somme aux
> nœuds, descente, formule 3. Mais **la configuration finale du projet
> n'utilise plus de feuilles binaires** : chaque symbole y porte un
> poids réel tiré de la collecte JDM (H et SST par le poids de la
> relation, TRT par `log(1 + effectif)`, normalisés par terme). Rien de
> ce qui est décrit ici ne change pour autant — un vecteur de poids
> réels s'additionne et se compare au cosinus exactement comme un
> vecteur de 1. Voir `rapport_ponderation.md` pour la pondération et ce
> qu'elle apporte, `rapport_signatures_variantes.md` pour le choix.

> Les chiffres des exemples ci-dessous sont simplifiés pour se suivre à
> la main. Les chiffres réels sont dans `rapport_grille.md` et
> `rapport_final.md`. La méthode écartée est expliquée dans
> `methode_union_arbre_descente.md`.

## 1. L'entraînement : on additionne

Une feuille est un vecteur de 1 : chaque symbole présent vaut 1.

```
cuillère de bois  côté B :  bois:1  matériau:1  SUBST:1
table de chêne    côté B :  chêne:1  bois:1  matériau:1  SUBST:1
```

Quand deux nœuds fusionnent, on additionne leurs vecteurs :

```
fusion côté B :  bois:2  matériau:2  SUBST:2  chêne:1
```

Avec de vrais poids (la configuration retenue), les feuilles ne valent
plus 1 mais un poids réel, tiré de la collecte JDM et normalisé par
terme — voir la note en tête de document. Pour « bois » (côté B de
« cuillère de bois ») et « chêne » (côté B de « table de chêne ») :

```
poids bruts JDM (exemples, pas les vrais chiffres de la collecte) :
  H:matériau de « bois »   = 850  (plus fort hyperonyme retenu de « bois »)   -> 850/850  = 1,00
  SST:SUBST  de « bois »   = 900  (plus forte annotation de « bois »)        -> 900/900  = 1,00

  H:bois     de « chêne »  = 760  (plus fort hyperonyme retenu de « chêne ») -> 760/760  = 1,00
  H:matériau de « chêne »  = 540  (hyperonyme plus lointain, retenu)         -> 540/760 ≈ 0,71
  SST:SUBST  de « chêne »  = 680  (plus forte annotation de « chêne »)       -> 680/680  = 1,00

cuillère de bois  côté B :  H:matériau:1,00  SST:SUBST:1,00
table de chêne    côté B :  H:bois:1,00  H:matériau:0,71  SST:SUBST:1,00

->

fusion côté B :  SST:SUBST:2,00  H:matériau:1,71  H:bois:1,00
```

Même mécanique que `bois:2  matériau:2  SUBST:2  chêne:1` — on
additionne vecteur à vecteur — sauf que les contributions ne sont plus
toutes égales à 1 : `matériau` ne pèse que 0,71 chez « chêne » parce
que c'est un hyperonyme plus lointain que `bois`, alors qu'il pesait
1,00 chez « bois » qui l'a comme hyperonyme direct le plus fort. La
somme, la descente et le cosinus se calculent ensuite exactement
pareil sur ce vecteur.

On fusionne toujours les deux nœuds les plus proches, jusqu'à une
racine unique par type : 49 fusions pour 50 exemples, 99 nœuds.

À la racine du type Matière, divisée par 50 pour la lisibilité — le
cosinus ignore l'échelle, cela ne change rien au calcul :

```
Profil du type Matière, côté B
    SUBST     0,86
    matériau  0,70
    bois      0,56
    métal     0,20
    pierre    0,12
    merisier  0,02
```

La racine est devenue un **profil** : pour chaque symbole, la
proportion des exemples du type qui le portent. C'est un centroïde.

## 2. La classification : on descend

Arrive « commode de merisier ». Ses deux signatures sont des vecteurs
de 1 :

```
s(commode)  : meuble  objet  THING-ARTEFACT
s(merisier) : bois  arbre fruitier  matériau  SUBST
```

**Étape 1 — les quinze racines.** Chaque symbole de l'exemple « vote »
avec le poids que lui donne le profil du type. Côté B, face au profil
Matière :

```
bois 0,56 + arbre fruitier 0,02 + matériau 0,70 + SUBST 0,86  =  2,14
```

Face au profil Holonymie, dont les termes B sont des touts (bateau,
arbre, voiture) :

```
bois 0,05 + arbre fruitier 0,03 + matériau 0,02 + SUBST 0,04  =  0,14
```

Le cosinus divise ensuite par les normes, mais l'ordre est déjà clair.
Même chose côté A. Après calcul complet :

```
racine Matière     0,64
racine Topic       0,31
racine Holonymie   0,28
... les douze autres plus bas
```

**Étape 2 — la descente.** Dans chaque arbre, on compare le nœud
courant à ses deux enfants, et on descend si l'un fait strictement
mieux. Dans Matière :

```
racine            0,64
  enfant 46 ex.   0,63
  enfant  4 ex.   0,41
```

Aucun enfant ne fait mieux : arrêt à la racine. Prédiction : Matière.

### Avec de vrais poids : comparer un nouveau syntagme

Le principe de l'étape 1 ne change pas : chaque symbole du syntagme à
classer « vote » avec le poids que lui donne le profil du type — sauf
qu'avec des poids réels, **chaque vote est lui-même pondéré**, des deux
côtés de la comparaison, et pas seulement présent ou absent.

Reprenons le nœud à deux feuilles du §1 (« bois » + « chêne »,
fusion côté B : `SST:SUBST:2,00  H:matériau:1,71  H:bois:1,00`) et
faisons-y arriver un nouveau syntagme, « boîte de hêtre ». Signature
pondérée de « hêtre », côté B, construite avec la même recette que
pour « bois » et « chêne » :

```
s(hêtre) côté B :  H:bois:0,95  SST:SUBST:1,00
```

(« hêtre » a lui aussi « bois » comme hyperonyme le plus fort, mais à
0,95 plutôt que 1,00 — un cran plus faible que pour « chêne ». La
signature de « hêtre » ne porte pas le symbole `H:matériau`, qui
n'intervient donc pas dans la comparaison.)

**Étape 1 — le vote.** Pour chaque symbole présent **dans les deux**
vecteurs, on multiplie le poids du syntagme par le poids que porte ce
même symbole dans le nœud, puis on additionne :

```
H:bois     : 0,95 (hêtre)  × 1,00 (nœud)  =  0,95
SST:SUBST  : 1,00 (hêtre)  × 2,00 (nœud)  =  2,00
                                     total =  2,95
```

`H:matériau`, absent de la signature de « hêtre », ne vote pas : il ne
rapproche ni n'éloigne la comparaison, exactement comme un symbole
absent valait 0 dans la version binaire. Le cosinus divise ensuite ce
total par la norme du nœud (≈ 2,82) et celle de « hêtre » (≈ 1,38), ce
qui donne environ **0,76** — un score comparable, à cette
normalisation près, à celui obtenu face aux quatorze autres profils de
type, exactement comme `0,64` contre `0,31` et `0,28` plus haut pour
« commode de merisier ».

La mécanique est donc identique à celle de l'étape 1 avec « commode de
merisier » : un vote par symbole partagé, une somme, une division par
les normes. Ce qui change, c'est seulement la valeur de chaque voix —
un hyperonyme fort compte plus qu'un hyperonyme lointain, du côté du
profil comme du côté du syntagme à classer — et la **descente** de
l'étape 2 s'applique ensuite sans aucune modification, sur ce même
genre de score.

## 3. La forme réelle des arbres : des peignes

Les schémas des §1 et §2 suggèrent un arbre équilibré, qui séparerait
le type en sous-familles — le partage « 46 exemples / 4 exemples » du
§2 en est une simplification commode. **Ce n'est pas la forme
obtenue.** En représentation somme, le cosinus ne pénalise pas un nœud
pour sa taille : à chaque tour, la fusion la plus attirante est donc
celle du gros nœud avec *une feuille de plus*. Les quinze arbres sont
des **peignes** : pour 50 exemples, la grosse branche est longue de 35 à
48 pas avec les signatures retenues (47 à 49 avec les binaires), là où
un arbre équilibré ferait 6.

À la racine, les deux enfants pèsent 49 et 1 dans **les 15 arbres** de
la configuration retenue (14 sur 15 avec les signatures binaires, 48 et
2 dans le quinzième). Et cela se répète à chaque niveau : le gros
enfant a un exemple de moins que son parent.

| profondeur le long de la grosse branche | 1 | 2 | 3 | 6 |
|---|---|---|---|---|
| poids moyen du nœud, signatures retenues | 49,0 | 48,0 | 46,9 | 43,7 |
| poids moyen du nœud, signatures binaires | 48,9 | 47,8 | 46,6 | 43,5 |
| `50 − profondeur` | 49 | 48 | 47 | 44 |

Le poids d'un nœud vaut donc **à peu près `50 − profondeur`**. Il n'y a
pas de sous-famille dans ces arbres, et pas non plus d'« isolat » à la
racine : la petite feuille écartée au premier pas n'a rien d'un intrus,
c'est simplement celle que l'ordre des fusions a laissée pour la fin.

**Conséquence, et c'est tout le §4 :** descendre d'un pas ne fait pas
passer à un groupe, cela **retire quelques feuilles du profil du
type**. Le nœud à la profondeur *k*, c'est le type moins *k* exemples.

## 4. Ce que la descente fait vraiment

Elle élague. Si quelques exemples du type tirent son profil moyen loin
du syntagme à classer, les retirer rapproche le profil ; la descente
s'arrête dès qu'un pas de plus n'y gagne rien. C'est un **ajustement
marginal du profil**, pas la recherche du bon niveau de généralité.

Les chiffres mesurés sur le test le disent sans ambiguïté. Ceux de la
**configuration retenue** (signatures pondérées) d'abord, ceux des
signatures binaires entre parenthèses :

- **43,6 %** des prédictions s'arrêtent à la racine (50,9 %),
  c'est-à-dire sur le profil complet du type, sans rien retirer.
- **Profondeur d'arrêt moyenne : 1,33** (1,02). En moyenne, une à deux
  feuilles retirées.
- **Poids relatif du nœud gagnant : 0,97** (0,97) — le nœud qui décide
  couvre 97 % des exemples de son type. C'est le chiffre décisif : même
  quand la descente bouge, elle ne descend presque pas.
- **70,5 calculs de score par exemple** (66,0) : quinze racines, leurs
  trente enfants, et quelques pas de plus ici ou là.

Autrement dit, la prédiction se joue presque toujours sur les quinze
profils de type, l'arbre ne servant qu'à en rogner les bords. C'est
cohérent avec ce que mesure la validation croisée : s'en tenir aux
quinze racines, sans aucune descente, donne le même F1 (0,783 contre
0,784). **Le gain vient de la représentation, pas de la structure.**

## 5. Pourquoi ça marche aussi bien

Un profil moyen efface l'accidentel. Un terme polysémique apporte des
symboles parasites — « Perse » tiré vers le patronyme plutôt que vers
le pays — mais ces parasites sont propres à chaque terme : dans la
moyenne de cinquante exemples, ils pèsent presque rien. Ce qui reste,
c'est ce que le type a en commun.

C'est pour cela que le plus proche voisin, qui décide sur un seul
exemple, plafonne à 0,53 en validation croisée, quand cette méthode
atteint 0,78.

## 6. Résultat sur le test

F1 macro **0,753** avec les signatures **binaires** (`binaire · T0`),
celles que décrivent les exemples de ce document : détail par type et
analyse des erreurs dans `rapport_final.md`.

Avec les **signatures retenues** (`jdm · T2`, les feuilles pondérées de
la note en tête), même méthode et même test : **0,778**, dans
`rapport_final_signatures.md`. Les deux configurations diffèrent par
deux réglages à la fois — les poids et le retrait du symbole du terme —
donc l'écart de 0,025 ne s'attribue pas à la seule pondération.
