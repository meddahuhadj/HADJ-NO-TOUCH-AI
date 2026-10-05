# Signature et avertissements Windows : que faire sans entreprise

Situation : développeur particulier, sans entreprise enregistrée. Informations vérifiées le 4 octobre 2026
(sources en fin de document ; les tarifs changent, à revérifier avant d'acheter).

## Recommandation

1. **Maintenant, gratuit** : garder la version portable telle quelle et publier les empreintes SHA-256
   (déjà générées par le build dans `dist/SHA256SUMS.txt`).
2. **Ensuite, gratuit** : publier l'application sur le **Microsoft Store**. C'est le seul moyen de supprimer
   *tous* les avertissements, et l'inscription est gratuite pour un particulier (pièce d'identité + selfie).
3. **Plus tard, seulement si nécessaire** : un certificat Certum « Standard Code Signing » au nom d'un
   particulier (à partir d'environ 209 € par an), si vous ajoutez un jour votre propre `.exe` ou un installateur.

À **ne pas** acheter : un certificat EV. Il ne supprime plus les avertissements SmartScreen depuis 2024, et
il est réservé aux entreprises.

## 1. Où en est la version actuelle

- La version portable ne contient **aucun exécutable à nous**. `HADJ-NoTouch.bat` lance le `python.exe`
  officiel, **déjà signé par la Python Software Foundation**. C'est pour cela qu'elle passe Smart App Control
  (vérifié sur votre machine, où Smart App Control est actif).
- Un certificat n'aurait donc **rien à signer** aujourd'hui : un fichier `.bat` ne peut pas porter de
  signature Authenticode.
- Avertissements possibles : le navigateur ou SmartScreen peut signaler un ZIP « rarement téléchargé ».
  L'utilisateur clique alors sur « Informations complémentaires » puis « Exécuter quand même ».
  À expliquer sur la page de téléchargement.
- **Les empreintes SHA-256** permettent à un service informatique de vérifier que le fichier téléchargé est
  bien celui que vous avez publié. Elles sont gratuites et générées à chaque build.

## 2. Les options comparées

| Option | Coût | Accessible à un particulier ? | Supprime les avertissements ? | Remarques |
|---|---|---|---|---|
| **Microsoft Store** | **Gratuit** | **Oui**, environ 200 pays ; pièce d'identité + selfie | **Oui, entièrement** : Microsoft signe l'application | Paquet MSIX à préparer ; mises à jour automatiques ; déployable par les services informatiques |
| Rien (situation actuelle) + empreintes | Gratuit | Oui | Non | Suffisant pour démarrer |
| Certum Standard Code Signing (cloud) | Environ 209 €/an | **Oui** : pièce d'identité + justificatif de domicile | Non au début : la réputation se construit avec les téléchargements | Le nom affiché est le vôtre ; validité limitée à 459 jours depuis février 2026 |
| Azure Artifact Signing (ex-Trusted Signing) | 9,99 $/mois | **Particuliers : États-Unis et Canada seulement** | Non au début | Le moins cher si vous créez un jour une structure dans un pays éligible |
| Certum Open Source Code Signing | Environ 49 € | Oui, mais **seulement pour un projet public** | Non au début | Valable pour `hadj-input` (étape 4b) s'il est publié, **pas** pour l'application fermée |
| Certificat EV | À partir d'environ 379 €/an | **Non**, entreprises seulement | **Non**, depuis 2024 | Ne plus le considérer |

Pays éligibles à Artifact Signing pour une **organisation** : États-Unis, Canada, Union européenne,
Royaume-Uni, Australie, Nouvelle-Zélande, Japon, Corée du Sud, Singapour, Suisse, Norvège, Israël.

## 3. Ce que dit Microsoft sur SmartScreen (documentation mise à jour en 2026)

- Même signé, un nouveau fichier peut afficher un avertissement tant que sa réputation n'est pas établie.
  Cela peut prendre plusieurs semaines et des centaines d'installations.
- **Les certificats EV ne contournent plus SmartScreen.**
- Un fichier non signé repart de zéro à chaque nouvelle version. Un certificat permet de cumuler la
  réputation d'une version à l'autre.
- Les applications du Microsoft Store ne déclenchent jamais d'avertissement SmartScreen.
- En entreprise, l'administrateur peut soumettre le fichier à Microsoft pour accélérer la confiance.

## 4. Le Microsoft Store pour HADJ No-Touch

| Avantage | Point d'attention |
|---|---|
| Aucun avertissement, gratuit, mises à jour automatiques | L'application s'installe (MSIX) au lieu d'être portable : la version ZIP reste proposée pour les clés USB |
| Les hôpitaux peuvent déployer via leurs outils habituels (Intune, winget) | Une page « politique de confidentialité » est exigée (caméra et micro) : elle peut être sur votre site |
| Désinstallation propre, sans trace : utile sur les postes partagés | Les réglages devront aller dans le dossier de l'utilisateur, car le dossier d'installation est en lecture seule |
| Le pack arabe peut devenir un module optionnel du Store | Validation par Microsoft à chaque version (quelques jours) |

Travail estimé : environ 4 jours, plus la création de votre compte développeur :
- installation du kit de développement Windows ;
- paquet MSIX des éditions Complète et Lite ;
- déplacement des réglages hors du dossier d'installation ;
- fiche Store en trois langues ;
- page de confidentialité.

## Sources

- Microsoft, *SmartScreen reputation for Windows app developers* :
  https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation
- Microsoft, *Free developer registration for individual developers on Microsoft Store* :
  https://blogs.windows.com/windowsdeveloper/2025/09/10/free-developer-registration-for-individual-developers-on-microsoft-store/
- Microsoft Q&A, pays éligibles à Artifact Signing pour les particuliers :
  https://learn.microsoft.com/en-nz/answers/questions/5810735/cant-create-a-new-trusted-signing-individual-ident
- Microsoft, options de signature : https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/code-signing-options
- Certum, documents requis : https://support.certum.eu/en/code-signing-required-documents/
- Certum, tarifs : https://shop.certum.eu/standard-code-signing-in-the-cloud.html et
  https://shop.certum.eu/open-source-code-signing-on-simplysign.html
