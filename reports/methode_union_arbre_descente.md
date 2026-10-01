# Méthode écartée : union · arbre · descente

**En une phrase** : même arbre, même descente, mais chaque nœud est
représenté par l'ensemble de tous les symboles de ses exemples ; le
cosinus pénalise alors les gros nœuds pour leur seule taille, et la
descente part systématiquement vers le plus petit enfant.

> **Note sur les poids.** Les exemples de ce document raisonnent sur des
> ensembles de symboles, donc sur des feuilles à 1. C'est un schéma
> pédagogique, et il suffit à comprendre pourquoi cette méthode a été
> écartée. Mais **la configuration finale du projet n'utilise plus de
> feuilles binaires** : chaque symbole y porte un poids réel tiré de la
> collecte JDM (H et SST par le poids de la relation, TRT par
> `log(1 + effectif)`, normalisés par terme). Cette pondération a été
> mesurée sur la méthode retenue, jamais sur celle-ci, qui reste
> écartée. Voir `rapport_ponderation.md` et
> `rapport_signatures_variantes.md`.

> Les chiffres des exemples ci-dessous sont simplifiés pour se suivre à
> la main. Les chiffres réels sont dans `rapport_arbres.md` et
> `rapport_grille.md`. La méthode retenue est expliquée dans
> `methode_somme_arbre_descente.md`.

## 1. L'entraînement : on réunit

La fusion garde chaque symbole une seule fois, sans compter :

```
cuillère de bois  côté B :  bois:1  matériau:1  SUBST:1
table de chêne    côté B :  chêne:1  bois:1  matériau:1  SUBST:1

fusion par union :           bois:1  matériau:1  SUBST:1  chêne:1
fusion par somme :           bois:2  matériau:2  SUBST:2  chêne:1
```

L'union ne distingue plus un symbole porté par tous les exemples d'un
symbole porté par un seul. En remontant l'arbre, chaque nœud accumule
tous les symboles de tous ses exemples, communs ou marginaux : les
signatures des racines atteignent en moyenne 673 symboles par côté,
contre une cinquantaine pour une feuille.

## 2. La classification : le petit enfant gagne toujours

Le cosinus entre ensembles vaut :

```
symboles communs / racine( taille de l'exemple × taille du nœud )
```

Même exemple, « commode de merisier », signature d'environ 50
symboles. À la racine d'un arbre, deux enfants :

```
gros enfant, 49 exemples, 600 symboles, 45 en commun :
    45 / racine(50 × 600)  =  0,26

isolat, 1 exemple, 50 symboles, 20 en commun :
    20 / racine(50 × 50)   =  0,40
```

Le gros enfant partage **plus** de symboles avec l'exemple, et perd
pourtant largement : son dénominateur est écrasé par les 555 symboles
marginaux qu'il a accumulés. La descente part vers l'isolat, s'y
arrête, et confie la décision à l'exemple le **moins** représentatif
du type.

## 3. Ce qu'on a mesuré

  - à la racine, la descente part vers l'enfant le plus léger dans
    93 % des cas, quel que soit l'exemple
  - dans 9 arbres sur 15, cet enfant léger est un isolat
  - F1 macro : 0,224 en validation croisée, 0,219 sur le test — contre
    0,53 pour un simple plus proche voisin

Le problème n'est pas l'information contenue dans les signatures : le
plus proche voisin, avec exactement les mêmes signatures, fait deux
fois mieux. C'est la comparaison entre deux frères de tailles très
différentes qui est faussée par le dénominateur du cosinus.

## 4. Pourquoi la somme corrige le problème

Avec la somme, les 45 symboles communs sont ceux que beaucoup
d'exemples du nœud portent : ils ont des comptes élevés. Les 555
symboles marginaux ont un compte de 1 et pèsent presque rien dans la
norme. Le gros nœud n'est plus puni pour sa taille, seulement pour ce
qu'il ne partage pas avec l'exemple.

## 5. Ce que dit l'article

La formule (2) de l'article, p. 29, écrit la fusion comme une union
(∪). La phrase qui la commente parle de « la somme vectorielle des
deux signatures ». Les deux lectures ne sont pas équivalentes ; nous
avons testé les deux.

| | union | somme |
|---|---|---|
| arbre · descente | 0,224 | 0,784 |
| meilleure configuration | 0,555 | 0,784 |
| article publié | | 0,772 |

Nos configurations par union plafonnent entre 0,53 et 0,56 ; la somme
atteint le niveau publié par l'article. C'est un indice — pas une
preuve — que les auteurs ont implémenté la somme vectorielle décrite
dans leur texte.
