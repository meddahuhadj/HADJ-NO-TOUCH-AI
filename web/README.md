# HADJ NO-TOUCH OFFLINE AI — Landing PWA

Page de présentation installable (PWA) du projet, entièrement statique : HTML, CSS et
JavaScript natifs, aucune dépendance, aucune étape de build.

## Servir en local

Un service worker exige une origine `http(s)` — ouvrir `index.html` directement depuis
le disque (`file://`) fonctionne pour la lecture, mais sans cache hors ligne.

```powershell
# Option 1 — Python
python -m http.server 8080 -d web

# Option 2 — Node
npx serve web
```

Puis ouvrir <http://localhost:8080>.

## Installer

- **Windows / Android / Chrome, Edge** — bouton « Installer » de l'en-tête, ou le menu
  du navigateur → « Installer l'application ».
- **iOS / Safari** — bouton Partager → « Sur l'écran d'accueil ». L'application iOS ne
  remonte pas d'événement d'installation : le bouton affiche à la place une fiche
  d'aide contextuelle.
- Hors ligne après la première visite : le squelette de l'application est mis en cache,
  les polices Google sont mises en cache séparément en *stale-while-revalidate*.

## Langues

Bascule `ع / FR / EN` dans l'en-tête. Le choix est conservé dans `localStorage`
(clé `hadj.lang`). L'arabe passe la page en `dir="rtl"` complète : navigation,
diagramme d'architecture, onglets, journal.

## Fichiers

| Fichier | Rôle |
| :--- | :--- |
| `index.html` | Contenu et structure sémantique |
| `styles.css` | Système de design (jetons alignés sur `ui/theme.py`) |
| `app.js` | i18n, atlas des gestes, atlas vocal, flux d'installation |
| `sw.js` | Service worker : précache + repli hors ligne |
| `manifest.webmanifest` | Manifeste PWA |
| `offline.html` | Repli pour les requêtes de navigation hors ligne |
| `icons/` | Icônes 64 → 512, y compris variantes *maskable* |
| `tools/make-icons.py` | Régénère le jeu d'icônes PNG |

## Régénérer les icônes

Le dessin est décrit par des fonctions de distance signée, rasterisé avec
antialiasing analytique et encodé avec `zlib` de la bibliothèque standard. Aucune
dépendance, aucun binaire externe.

```powershell
python web\tools\make-icons.py
```

Pour ajuster le rendu, modifier `geometry()` (marge, rayons, épaisseur) puis relancer.

## Compatibilité

| Navigateur | État |
| :--- | :--- |
| Chrome / Edge 108+ | Complet, installation native |
| Firefox 115+ | Complet, installation via le menu |
| Safari 16.4+ iOS/macOS | Complet, installation « Sur l'écran d'accueil » |
| Navigateurs sans SW | La page reste lisible, l'i18n fonctionne |

## Accessibilité

Navigation clavier de bout en bout, anneau de focus visible, lien d'évitement,
onglets `role="tablist"` avec flèches gauche/droite, accordéons `<details>` natifs,
contrastes AA, cibles tactiles de 44 px minimum, `prefers-reduced-motion` respecté.
