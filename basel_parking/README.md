# Basel Parking

## Mettre à jour le site existant

Décompresse basel-parking-netlify.zip. Le dossier à déposer sur Netlify doit contenir index.html, assets, _headers et les autres fichiers de publication directement à sa racine.

Dans ton projet Netlify existant, ouvre la section des déploiements et dépose ce dossier dans la zone de déploiement manuel. Le remplacement devient public quand le déploiement réussit. Garde la même adresse de projet.

Dépose tout le dossier. index.html seul ne suffit pas pour cette version publiée : les scripts, les polices, les styles et les en-têtes sont des fichiers séparés.

Après publication, ouvre le site et vérifie le nouveau titre. Teste aussi /privacy.html, /robots.txt, /sitemap.xml et une adresse inexistante pour voir la nouvelle page 404. La réception effective des en-têtes dépend du déploiement du fichier _headers.

## Modifier le code

app.js : dates, API, validation des relevés, horaires, estimations et affichage.
i18n.js : textes anglais, allemands et français.
styles.css : interface, mobile et police locale.
config.json : données des parkings, horaires, hauteurs, adresse du site et coordonnées de publication.
dashboard.full.template.html : structure de la page.
pages.js : langues des pages de confidentialité et 404.
build_site.py : génération des fichiers Netlify, des icônes et du HTML autonome.

Installer Python 3 avec Pillow, puis lancer :

```sh
python3 -m pip install Pillow
python3 build_site.py
```

Le dossier basel-parking-netlify est créé à côté du dossier source. dashboard.html et basel-parking-v4.html sont des copies autonomes qui intègrent le code et les polices. Elles nécessitent Internet pour les relevés. Pour Netlify, utilise le dossier complet afin de conserver les pages annexes et les en-têtes de sécurité.

Pour ajouter tes mentions légales, remplis publisher.name, publisher.email et publisher.address dans config.json avec les coordonnées que tu acceptes de publier, puis relance la construction. Ces champs sont publics. La construction ajoute alors legal.html et son lien. Il faut vérifier le contenu légal selon ta situation ; aucune conformité juridique n'est présumée.

## Tests

Node.js et Playwright sont nécessaires uniquement pour les tests, pas pour le site publié.

```sh
npm install --save-dev playwright
npx playwright install chromium
node --test tests/core.test.js
node tests/browser.v4.test.cjs
```

Le test navigateur démarre son serveur local, applique les en-têtes de sécurité et effectue ensuite les appels aux vraies API. BASEL_SKIP_LIVE=1 permet de n'exécuter que les cas simulés. BASEL_CHROMIUM_PATH permet de désigner un exécutable Chromium déjà installé.

Le détail des résultats et des limites est dans RELEASE-V4.md. Les analyses et résultats plus anciens ne prouvent pas la précision de cette version.
