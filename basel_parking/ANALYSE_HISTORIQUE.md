# Archive de la première version — septembre 2026

Ce document décrit la première analyse et son interface désormais remplacée. Ses chiffres et captures servent à reproduire cette expérience historique. Le site actuel utilise `app.js`, récupère les données récentes dans le navigateur et suit la méthode décrite dans `README.md`. Les performances de cette archive ne valident pas automatiquement les nouvelles estimations.

---

# Basel Parking Lab — aide à la décision, données ouvertes

**Usage réel :** une personne choisit une destination à Bâle, son heure d'arrivée, le rayon qu'elle accepte autour de cette destination et la hauteur de son véhicule. L'application compare les parkings compatibles, montre leur disponibilité **habituelle** à cette heure et la dernière disponibilité **actuelle** publiée par la ville. Elle renvoie vers l'itinéraire et les conditions officielles. Elle ne promet pas une place et ne chiffre pas le temps de marche.

Ouvrir directement **`dashboard.html`**. Il fonctionne sans installation pour l'historique ; l'information actuelle exige une connexion Internet. Exemple reproductible : Rathaus, samedi à 16 h, rayon 1 km. Dans les 182 jours précédant le 25 septembre 2026, Storchen déclarait moins de dix places libres **23 samedis sur 25** à cette heure. Kunstmuseum : **1 sur 25** ; City : **0 sur 25**, mais les distances et les chemins réels diffèrent. Un zéro sur 25 ne signifie pas « impossible d'être complet » : son intervalle d'échantillonnage à 95 % va de 0 à environ 13 %.

## Pour le reproduire et le modifier

Prérequis : Python 3.9 ou plus, **aucun paquet tiers**.

```bash
python build.py
python build.py --refresh
python verify.py
```

- `build.py` recrée `results.json` et `dashboard.html` depuis le CSV fourni.
- `--refresh` retélécharge de manière atomique l'historique intégral depuis l'API de Basel-Stadt, puis régénère les résultats. En cas de téléchargement interrompu, le CSV précédent est conservé.
- `verify.py` vérifie indépendamment les 16 audits, les profils horaires, la chronologie et le cas du samedi à 16 h à partir du CSV.
- `portfolio_figure.png` est une figure exportable pour présenter le problème et l'évaluation. `portfolio_figure.py` la régénère après installation facultative de Matplotlib et NumPy ; ces bibliothèques ne sont pas nécessaires pour l'application.
- `dashboard.full.template.html` contient l'interface autonome ; les données calculées sont insérées dans `dashboard.html`. `data/all_historical.csv` est le cliché des 241 200 relevés du 1er janvier 2025 au 25 septembre 2026. `results.json` contient les critères, chiffres, audit et résultats de l'évaluation.

Les fichiers embarqués permettent d'examiner exactement les chiffres du dossier de candidature. Pour obtenir des chiffres récents, il faut reconstruire et réévaluer le projet ; ouvrir le HTML seul ne rafraîchit que les **relevés actuels**, jamais les statistiques historiques.

## Données, filtre et calcul

Sources : [historique d'occupation horaire, jeu 100014](https://data.bs.ch/explore/dataset/100014/) et [occupation actuelle, jeu 100088](https://data.bs.ch/explore/dataset/100088/), © **Kanton Basel-Stadt**, CC BY 4.0. Les coordonnées des destinations Rathaus, Basel SBB, Messeplatz et Kunstmuseum ont été obtenues via OpenStreetMap Nominatim le 25 septembre 2026 ; les coordonnées des garages viennent du CSV cantonal. La **distance est à vol d'oiseau**, calculée avec la formule de Haversine : ce n'est ni la distance routière ni le trajet à pied. Les [pages du système officiel de parkings](https://www.parkleitsystem-basel.ch/) ont servi à relever la hauteur maximale de passage des neuf parkings retenus le 25 septembre 2026 ; les liens présents dans l'application permettent de la revérifier avant de partir.

L'heure de chaque relevé est convertie d'UTC en **Europe/Zurich**. Pour chaque parking, jour de semaine et heure, le modèle prend les relevés des **182 jours précédents** : environ 25 ou 26 observations. Il calcule le nombre médian de places libres, le 10e percentile et la part des observations déclarant **moins de dix places libres**. Le segment autour de cette part est l'intervalle de Wilson à 95 % : il représente seulement l'incertitude liée au faible nombre d'observations comparables. Un événement, une fermeture, une panne ou un changement de comportement peut faire sortir le futur de cet intervalle.

Le tri « moins de risque » utilise cette **fréquence descriptive**, puis la distance à vol d'oiseau ; l'autre tri inverse ces critères. Il ne transforme pas arbitrairement un mètre et un point de risque en un même score. Le rayon est appliqué avant le tri. La hauteur est un filtre strict : un parking déclaré à 1,90 m ne sera pas proposé pour un véhicule indiqué à 2,00 m. Le prix n'est pas intégré au tri ; il se vérifie auprès de l'exploitant.

La disponibilité actuelle vient de l'API du canton au moment où la page est ouverte, puis toutes les 60 secondes. Si le parking est déclaré fermé, si la réponse échoue ou si le relevé a plus de 15 minutes, l'application n'affiche pas de nombre périmé comme « actuel ».

## Audit des données : 16 parkings, neuf inclus

Avant tout classement, une observation est marquée impossible lorsque `free < 0`, `total <= 0`, `free > total` ou qu'une valeur indispensable manque. Le parking est exclu si **plus de 1 %** de ses observations sont impossibles, si **plus de 5 %** des observations valides de minuit à 6 h sont à zéro, si les coordonnées ou l'historique sont insuffisants, ou si sa hauteur n'a pas été vérifiée. Ces seuils sont des choix de prudence documentés, pas des seuils statistiques universels. Les doublons exacts d'horodatage sont ignorés.

Inclus : Aeschen, Bad. Bahnhof, Bahnhof Süd, City, Elisabethen, Europe, Kunstmuseum, Steinen et Storchen. Exclus : Anfos (**31,7 %** de valeurs impossibles), Centralbahn (**30,7 %**), Clarahuus (**10,0 %** et beaucoup de zéros nocturnes), Claramatte (**29,5 %**), Messe (**14,4 %**), Post Basel (capacité absente dans cet historique), Rebgasse (**17,4 %** de zéros nocturnes). Cette dernière série peut refléter des fermetures ou un problème de comptage ; l'audit ne permet pas de trancher. Les 16 lignes complètes et les motifs sont dans l'application et `results.json`.

**Conséquence pratique :** près de Messeplatz, le parking « Messe » n'est pas présenté comme recommandation calculée, précisément parce que la série historique échoue au contrôle qualité. L'utilisateur peut néanmoins ouvrir son état actuel sur le site officiel ; l'exclusion ne signifie pas qu'il est fermé.

## Évaluation chronologique et limites des chiffres

Les **56 derniers jours disponibles** servent à une évaluation en avançant dans le temps. Avant de calculer une prévision pour une heure donnée, le programme coupe l'historique à cette heure ; aucune observation future ne peut entrer dans son calcul. On compare :

- **MAE** en places libres de la médiane historique contre le dernier relevé au même jour/heure de la semaine précédente ; plus petit est meilleur.
- **Score de Brier** de la fréquence historique « moins de dix places libres » contre la fréquence générale des 182 jours précédents dans le même parking ; plus petit est meilleur. Une fréquence rarement positive produit facilement un score faible, même pour un modèle banal.

| Parking | Heures testées | MAE modèle | MAE semaine précédente | Brier modèle | Brier fréquence globale |
| --- | ---: | ---: | ---: | ---: | ---: |
| Aeschen | 1 339 | 3,6 | 4,7 | 0,001 | 0,001 |
| Bad. Bahnhof | 1 339 | 43,0 | 54,5 | 0,000 | 0,000 |
| Bahnhof Süd | 1 339 | 6,0 | 7,2 | 0,005 | 0,005 |
| City | 1 339 | 29,7 | 31,0 | 0,000 | 0,000 |
| Elisabethen | 1 339 | 26,3 | 31,8 | 0,000 | 0,000 |
| Europe | 1 339 | 13,4 | 17,3 | **0,006** | **0,005** |
| Kunstmuseum | 1 339 | 15,3 | 19,1 | 0,001 | 0,001 |
| Steinen | 1 339 | 25,1 | 33,1 | 0,009 | 0,012 |
| Storchen | 1 339 | 8,4 | 10,6 | 0,081 | 0,189 |

Sur cette fenêtre, la médiane améliore la MAE dans les neuf parkings. **La fréquence horaire ne bat pas la référence pour Europe** en score de Brier, et beaucoup d'autres scores sont à égalité après arrondi. Il serait faux de déclarer le modèle « fiable à 92 % » à Storchen parce que 23 des 25 samedis passés étaient chargés. Les événements, les jours fériés, les changements de capacité, les tarifs et la circulation ne sont pas modélisés. Ce projet est une aide à la comparaison de créneaux, pas un système de réservation ni une garantie en temps réel.

## Ce que le projet prouve en candidature

1. **Problème concret :** conseiller des alternatives à une heure et près d'une destination donnée, avec une contrainte physique (hauteur).
2. **Ingénierie reproductible :** API officielle, export local, génération de l'interface, fuseaux horaires, contrôle qualité sur tout le catalogue et rafraîchissement sûr.
3. **Analyse honnête :** référence simple, évaluation sans fuite temporelle, score du risque distinct de l'erreur du nombre de places, résultat défavorable pour Europe, limites visibles dans l'application.
4. **Produit utilisable :** filtres, état actuel non périmé, adresses, liens officiels, incertitude et données hors réseau pour les statistiques historiques.

**Pitch allemand de 30 secondes :** « Ich habe mit offenen Basler Daten eine Entscheidungshilfe für die Parkplatzsuche entwickelt. Sie vergleicht für eine Ankunftszeit neun geprüfte Parkhäuser in der Nähe eines Ziels, berücksichtigt die Fahrzeughöhe und zeigt aktuelle Messwerte getrennt von historischen Mustern. Ich habe 16 Datenreihen auf Widersprüche geprüft und die Vorhersage zeitlich sauber gegen eine einfache Referenz getestet. Die Ergebnisse und die Grenzen sind in der Anwendung sichtbar. »

**Prochaine expérience utile :** intégrer les événements et les jours fériés comme variables connues avant le trajet, puis vérifier sur une nouvelle période si la MAE et le score de Brier s'améliorent. Ne pas écrire dans un CV que cette amélioration existe tant qu'elle n'a pas été mesurée.
