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

## 3. La forme réelle des arbres : des peignes

Les schémas des §1 et §2 suggèrent un arbre équilibré, qui séparerait
le type en sous-familles — le partage « 46 exemples / 4 exemples » du
§2 en est une simplification commode. **Ce n'est pas la forme
obtenue.** En représentation somme, le cosinus ne pénalise pas un nœud
pour sa taille : à chaque tour, la fusion la plus attirante est donc
celle du gros nœud avec *une feuille de plus*. Les quinze arbres sont
des **peignes** — profondeur 47 à 49 pour 50 exemples, là où un arbre
équilibré ferait 6.

À la racine, les deux enfants pèsent 49 et 1 dans **14 arbres sur 15**
(48 et 2 dans le quinzième). Et cela se répète à chaque niveau : le
gros enfant a un exemple de moins que son parent.

| profondeur le long de la grosse branche | 1 | 2 | 3 | 6 |
|---|---|---|---|---|
| poids moyen du nœud | 48,9 | 47,8 | 46,6 | 43,5 |
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

Les chiffres mesurés le disent sans ambiguïté :

- **50,9 %** des prédictions s'arrêtent à la racine, c'est-à-dire sur
  le profil complet du type, sans rien retirer.
- **Profondeur d'arrêt moyenne : 1,0.** En moyenne, une feuille
  retirée.
- **Poids relatif du nœud gagnant : 0,97** — le nœud qui décide couvre
  97 % des exemples de son type.
- **66,0 calculs de score par exemple** : quinze racines, leurs trente
  enfants, et quelques pas de plus ici ou là.

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
