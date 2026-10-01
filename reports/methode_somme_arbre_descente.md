# Méthode retenue : somme · arbre · descente

**En une phrase** : chaque type de relation est résumé par un profil
moyen de ses exemples, et un syntagme est rangé dans le type dont le
profil lui ressemble le plus ; l'arbre ne sert qu'à aller chercher le
profil d'une sous-famille quand un type est hétérogène.

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

## 3. Ce qui se passe dans la plupart des cas

La racine résume tous les exemples du type ; un enfant n'en résume
qu'une partie, son profil est donc plus bruité. Face à un exemple
ordinaire, le profil complet gagne.

Nuance : dans 9 arbres sur 15, la racine a pour petit enfant un
**isolat**, l'exemple que le type n'a su rapprocher de personne. Le
gros enfant couvre alors 49 exemples sur 50 : c'est la racine moins
l'intrus, un profil très légèrement plus propre. La descente y entre
souvent, fait un pas, et s'arrête.

D'où les chiffres observés : 50,9 % des prédictions viennent
d'une racine, et le nœud gagnant couvre en moyenne 97 % de
son type. Nombre moyen de calculs par exemple : 66,0 —
quinze racines, trente enfants au premier niveau, quelques pas de plus
ailleurs.

L'isolat, lui, ne gagne plus : c'est une feuille chargée de ses propres
particularités, face à un profil qui n'est plus pénalisé pour sa
taille. Il ne l'emporte que si l'exemple lui ressemble presque
exactement.

## 4. Quand la descente va plus bas

Seulement si le type contient une **sous-famille nette** et que
l'exemple y appartient clairement. Le type Topic mélange de vrais
thèmes (*livre de cuisine*, *film d'aventure*) et des cas temporels
(*repas de midi*, *bus de nuit*) ; l'arbre les sépare dès la racine.

Arrive « dîner du soir » :

```
racine Topic               0,45
  enfant « temporel »      0,58   mieux, on descend
    petit-enfant A         0,53
    petit-enfant B         0,50
    arrêt : réponse « temporel »
```

Le profil global de Topic est tiré par les thèmes ; celui de la
sous-famille temporelle colle. La descente trouve le bon niveau de
généralité.

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

F1 macro : 0,753. Détail par type et analyse des erreurs :
`rapport_final.md`.
