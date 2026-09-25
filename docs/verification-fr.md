# Basel Parking, version 4

## Changements

Les relevés actuels restent affichés quand la capacité totale manque. Dans ce cas, aucun pourcentage n'est calculé. Les valeurs impossibles, les statuts inconnus et les relevés trop anciens restent écartés.

Un statut actuel ouvert ne peut plus être remplacé silencieusement par les horaires habituels. Une divergence affiche un avertissement. Un statut fermé récent reste prioritaire. Les dates d'ouverture exceptionnelle d'Anfos sont signalées comme à confirmer.

Les chiffres futurs sont présentés comme des estimations historiques. Les jours fériés connus et les dates du carnaval de Bâle n'ont pas d'estimation. Badischer Bahnhof conserve le relevé actuel, avec un avertissement sur la capacité visiteurs. Son pourcentage et son estimation restent suspendus tant que les sources divergent. La fourchette dépliable décrit les relevés passés, sans garantie statistique.

L'interface montre quatre parkings au départ, puis permet d'afficher les autres. Les détails sont dépliables et un lien ouvre l'itinéraire dans Google Maps. Les champs conservés sont destination, date, horaire et hauteur du véhicule. Les dates et les requêtes historiques restent calculées à partir du jour courant, dans le fuseau Europe/Zurich.

Police Atkinson Hyperlegible Next hébergée avec le site. Bouton principal au premier écran à 375 px. Champs de 16 px et commandes de 44 px minimum. Les détails ouverts et le focus clavier sont préservés pendant l'actualisation.

Ajouts : 404 personnalisée, descriptions, image de partage compressée, favicons, icône iPhone, manifeste, robots.txt, sitemap, page de confidentialité traduite, choix de stockage facultatif avec refus et retrait, en-têtes de sécurité Netlify. Aucun script de mesure d'audience n'a été ajouté.

## Vérifications effectuées

13 tests de logique réussis : dates en 2032, changement d'heure été/hiver, années bissextiles, historique glissant, relevés invalides ou anciens, capacité manquante, horaires et exceptions.

Tests Chromium réussis à 375 x 667, en anglais, allemand et français : absence de débordement, bouton principal au premier écran, police locale chargée, respect de CSP, échappement des noms fournis par l'API, affichage malgré capacité manquante, contradictions d'horaires, fermeture explicite, passage à minuit en 2032, actualisation des places, expiration du cache après six heures, perte de connexion et reprise, consentement et refus, conservation du focus, 404 et confidentialité.

Test avec les vraies API : 16 parkings reçus, Post Basel affiché avec 77 places lors du test, 11 estimations affichées pour le créneau futur testé. Ces nombres sont des observations de test datées, jamais des données intégrées au site.

Le serveur local de test a appliqué les en-têtes préparés pour Netlify. Leur activation sur le domaine publié devra être vérifiée après le nouveau déploiement. Les fichiers n'ont pas été envoyés au compte Netlify.

Safari et un iPhone physique n'ont pas été testés. Les tests de navigateur ont utilisé Chromium, y compris l'émulation tactile à 375 px. La précision prédictive de cette version n'a pas été mesurée sur un jeu indépendant. Le fichier results.json et l'analyse historique antérieurs restent des résultats de recherche anciens ; ils ne valident pas la version 4.

## Informations manquantes

Les mentions légales et le contact public nécessitent les coordonnées réelles du responsable. Aucun nom, aucune adresse et aucun email n'ont été inventés. La page de confidentialité décrit les traitements techniques connus ; elle ne remplace pas ces mentions.

La mesure d'audience n'est pas activée. Le site ne contient aucun traceur d'audience. Le choix de stockage concerne uniquement la langue et le cache des données publiques. La décision de refus elle-même est conservée pour éviter de redemander à chaque visite.

Les horaires et hauteurs sont encore des données vérifiées manuellement. Ils peuvent évoluer indépendamment du code. Une date qui avance toute seule ne garantit pas que l'exploitant n'a pas changé ses horaires. Les API et l'hébergement doivent aussi rester disponibles.

Aucun formulaire d'envoi, compte, mot de passe, base de données privée ni téléchargement de fichier utilisateur n'est présent. Les contrôles d'authentification, d'accès par utilisateur et de sessions ne s'appliquent donc pas à cette version. Aucune clé d'API n'est nécessaire. Les requêtes ne demandent que les champs utiles. Les liens externes sont échappés ou construits à partir de paramètres encodés.

## Sources vérifiées

- Données actuelles : https://data.bs.ch/explore/dataset/100088/
- Historique : https://data.bs.ch/explore/dataset/100014/
- Capacité visiteurs de Badischer Bahnhof : https://www.parkleitsystem-basel.ch/parkhaus/badbahnhof.html
- Exceptions Anfos : https://www.parkleitsystem-basel.ch/parkhaus/anfos.html
- Dates du carnaval : https://www.basel.com/en/events/carnival
- En-têtes Netlify : https://docs.netlify.com/manage/routing/headers/
- Police : https://www.brailleinstitute.org/freefont/

La licence de la police est incluse dans assets/FONT-LICENSE.txt.

## Relecture et corrections

La relecture a conduit à retirer Inter, les tirets cadratins des textes actifs et les indications de fiabilité non démontrées. Le contrôle visuel a révélé un chemin de police incorrect ; il a été corrigé et le chargement de la police a ensuite été testé. Aucun compteur, témoignage ni renseignement légal fictif n'a été ajouté.
