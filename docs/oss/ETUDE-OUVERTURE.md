# Ouverture partielle du code : la couche système (`hadj-input`)

## Recommandation

Publier sur GitHub, sous **licence Apache 2.0**, **tout le code qui agit sur Windows** (le dossier
`src/os_layer`, sans `apps_index.py`), sous le nom `hadj-input`. Garder fermés la reconnaissance vocale,
la vision, l'interface, les profils et les macros.

Tout est prêt dans le dépôt : `python scripts/export_oss.py` produit le dépôt public complet dans
`dist/oss/hadj-input/` (code, licence, politique de sécurité, modèle de menaces, tests, intégration continue).
**Rien n'a été publié.** Il reste quatre décisions à prendre (section 6).

## 1. Pourquoi ouvrir cette partie

Un service informatique d'hôpital ou d'entreprise se pose une question avant d'installer HADJ No-Touch :
*« que peut faire ce logiciel à nos postes ? »*. La réponse se trouve entièrement dans la couche système,
car c'est le seul code qui touche à Windows. En la publiant :

- n'importe qui peut vérifier qu'il n'y a **ni réseau, ni hook clavier, ni élévation de privilèges, ni persistance** ;
- ces garanties sont **vérifiées automatiquement** à chaque export (l'export échoue sinon) ;
- la partie qui fait la valeur du produit (reconnaissance, gestes, interface, profils) reste fermée.

## 2. Périmètre

| Ouvert (`hadj-input`) | Fermé (reste dans l'application) |
|---|---|
| Clavier, souris, texte Unicode (`SendInput`) | Reconnaissance vocale (Vosk, Whisper) |
| Fenêtres, écrans, bureaux virtuels | Vision, gestes, calibration |
| Luminosité, mode sombre, volume, micro | Interface, aide, profils, macros |
| Verrouillage, capture, arrêt/redémarrage | Recherche floue des applications (`apps_index.py`) |
| Raccourci d'urgence, `release_all()` | Confirmations « oui / non » (décidées par l'application) |

Ouvrir **tout** ce qui touche au système, plutôt que seulement le clavier et la souris, est volontaire :
un audit partiel ne rassure pas un responsable sécurité.

## 3. Choix de la licence

| Licence | Pour | Contre | Verdict |
|---|---|---|---|
| **Apache 2.0** | Brevets accordés explicitement ; marque protégée (§6) ; connue des services juridiques | Texte plus long | **Recommandée** |
| MIT | Très simple, très répandue | Pas de clause brevets ni marque | Acceptable |
| MPL 2.0 | Les modifications du module doivent être republiées | Moins connue en entreprise | Possible si vous voulez forcer le partage des améliorations |
| GPL / AGPL | Partage obligatoire de tout logiciel dérivé | Freine l'adoption en entreprise et à l'hôpital | Déconseillée ici |

Apache 2.0 a deux avantages concrets pour vous :
- **La clause brevets** est souvent exigée par les services juridiques des établissements.
- **L'article 6** dit que la licence ne donne pas le droit d'utiliser le nom « HADJ No-Touch » : le nom de
  votre produit reste à vous.

## 4. Ce qui a été préparé

| Fichier | Rôle |
|---|---|
| `scripts/export_oss.py` | Produit le dépôt public à partir du code réel (pas de copie à maintenir) et **refuse l'export** si le code importe un module réseau, utilise un hook clavier, lit l'état du clavier, ou dépend du reste de l'application |
| `oss/hadj-input/README.md` | Présentation en anglais avec résumé français : ce que fait la bibliothèque, ce qu'elle ne fait jamais |
| `oss/hadj-input/SECURITY.md` | Signalement privé via GitHub, délais de réponse, périmètre |
| `oss/hadj-input/docs/THREAT_MODEL.md` | Modèle de menaces : 9 menaces, leurs parades, les risques restants |
| `oss/hadj-input/LICENSE`, `NOTICE` | Apache 2.0 et mention de copyright |
| `oss/hadj-input/tests/`, `.github/workflows/` | Tests (API, absence de réseau et de hook, `release_all`) exécutés sur Windows à chaque modification |

Vérifié :
- l'export passe l'audit ;
- le paquet exporté fonctionne seul (aucun module de l'application chargé) ;
- ses tests passent ;
- `pip` en fait un paquet installable (`hadj_input-0.1.0`) ;
- l'application elle-même fonctionne toujours, avec la seule modification nécessaire : les sons sont
  maintenant fournis au backend au lieu d'être importés.

## 5. Audit du code système (ce que lira un responsable sécurité)

- **Lecture d'état** : `GetAsyncKeyState` est utilisé uniquement sur les 3 boutons de la souris, pour
  relâcher un bouton resté enfoncé. Le clavier n'est jamais lu.
- **PowerShell** : deux scripts fixes (luminosité par WMI, liste du menu Démarrer). Les seules valeurs
  insérées sont des entiers bornés, donc pas d'injection possible.
- **Registre** : une seule écriture, la préférence de thème de l'utilisateur (`HKCU`), sur demande.
- **Arrêt / redémarrage** : `shutdown.exe` avec 5 secondes de délai ; la confirmation est demandée par l'application.
- **Raccourci d'urgence** : `RegisterHotKey`, sans hook, sur un fil d'exécution dédié.

## 6. À décider avant de publier

1. **Titulaire du copyright** : votre nom ou celui de votre structure (à écrire dans `NOTICE`).
2. **Compte GitHub** qui héberge le dépôt, avec la double authentification activée.
3. **Commentaires en arabe** : les garder (le README le signale) ou les traduire en anglais avant la
   publication, pour faciliter la relecture par des auditeurs non arabophones. Je recommande de traduire au
   moins `input.py` et `backend.py`.
4. **Contributions** : accepter les contributions extérieures ou non. Si oui, je recommande la signature DCO
   (`Signed-off-by`) plutôt qu'un contrat de cession, plus simple pour les contributeurs.

## 7. Risques et limites

| Risque | Niveau | Réponse |
|---|---|---|
| Un concurrent réutilise le code | Faible | C'est la partie la moins différenciante ; la valeur est dans la reconnaissance et l'interface |
| Signalements de sécurité à traiter | Moyen | `SECURITY.md` fixe 7 jours pour répondre et 30 jours pour corriger |
| Écart entre le dépôt public et l'application | Moyen | L'export part toujours du code réel ; republier à chaque version |
| Fausse impression de sécurité totale | Moyen | Le modèle de menaces liste les risques restants (fenêtre au premier plan qui change, texte tapé dans un terminal) |

## 8. Publication (quand vous l'aurez décidé)

```bash
python scripts/export_oss.py --version 0.1.0
cd dist/oss/hadj-input
git init && git add . && git commit -m "hadj-input 0.1.0"
# créer le dépôt vide sur GitHub, puis :
git remote add origin https://github.com/<compte>/hadj-input.git
git push -u origin main
```

Puis, sur GitHub :
- activer *Settings → Security → Private vulnerability reporting* ;
- protéger la branche `main` ;
- publier une *release* `v0.1.0`.
