# Feuille de route : macOS et Linux

## Recommandation

Procéder en quatre phases, dans cet ordre :

1. **Phase 0 — noyau portable** (environ 3 j) : isoler les derniers appels propres à Windows hors de `os_layer`.
   Ce travail sert aux deux plateformes.
2. **Phase 1 — Linux, session X11** (environ 11 j) : aucun frais, aucun matériel à acheter, testable dans une
   machine virtuelle et en intégration continue. Elle valide l'abstraction à moindre coût.
3. **Phase 2 — macOS** (environ 16 j) : demande un Mac, un compte Apple Developer (99 $/an) et la notarisation.
4. **Phase 3 — Linux, session Wayland** (environ 8 à 10 j, support partiel) : par défaut sur Ubuntu et Fedora
   récents, mais Wayland limite volontairement l'injection d'entrées et les fenêtres au premier plan.

**Inverser les phases 1 et 2 si** votre priorité est commerciale et que vous avez un Mac : les personnes à
mobilité réduite sont plus nombreuses sur macOS que sur Linux. En contrepartie, macOS intègre déjà
« Contrôle vocal », un concurrent gratuit.

Les engagements actuels restent valables sur les deux plateformes : 100 % hors ligne, arrêt d'urgence garanti,
interface arabe, française et anglaise, aucune trace inutile sur le système.

## 1. Ce qui est déjà portable

| Élément | État |
|---|---|
| Reconnaissance vocale (Vosk, Whisper), vision (MediaPipe), interface (PySide6) | Bibliothèques multiplateformes |
| Modèles (Vosk, MediaPipe, Whisper) | Mêmes fichiers sur les trois systèmes |
| Capture micro | Repli `sounddevice` déjà prévu hors Windows (`audio/capture.py`) |
| Communication entre processus | Sockets Unix déjà prévues hors Windows (`core/ipc.py`) |
| Blocage réseau, instance unique, réglages, profils, macros, aide | Python pur ou Qt |
| Couche système | Interface `OSBackend` unique : il suffit d'écrire une implémentation par système |

## 2. Inventaire : chaque fonction système, plateforme par plateforme

| Fonction | Windows (actuel) | macOS | Linux X11 | Linux Wayland |
|---|---|---|---|---|
| Touches, clics, défilement | `SendInput` | `CGEventPost` (Quartz) — **permission Accessibilité** | XTest (`python-xlib`) | Portail *RemoteDesktop* (accord à chaque session) ou `uinput` (règle udev, admin une fois) |
| Taper du texte Unicode | `KEYEVENTF_UNICODE` | `CGEventKeyboardSetUnicodeString` | Remappage temporaire de keysym (façon `xdotool type`) | Portail, ou `virtual-keyboard` (wlroots seulement) |
| Fenêtres (fermer, aimanter, déplacer) | `user32` | API Accessibilité (`AXUIElement`) — même permission | EWMH (`python-xlib`) | **Impossible de façon générique** (extension GNOME ou script KWin) |
| Luminosité | WMI | Écran interne : DisplayServices ; externe : DDC | `/sys/class/backlight` (droits udev) ou `ddcutil` | Idem X11 |
| Mode sombre | Registre `HKCU` | `osascript` (System Events) | `gsettings` (GNOME), `plasma-apply-colorscheme` (KDE) | Idem X11 |
| Volume, micro coupé | Touches multimédia | `osascript set volume` | `wpctl` / `pactl` (PipeWire, PulseAudio) | Idem X11 |
| Verrouiller, éteindre, capture | `LockWorkStation`, `shutdown.exe`, Win+ImprÉcr | `pmset`, `osascript`, `screencapture` | `loginctl lock-session`, `systemctl poweroff`, outil du bureau | Idem X11 (capture via portail) |
| Bureaux virtuels | Win+Ctrl+flèches | Ctrl+flèches (Mission Control) | Raccourcis du bureau (variables) | Idem X11 |
| Lister et lancer les applications | `Get-StartApps`, `ShellExecute` | `/Applications`, `open -a` | Fichiers `.desktop`, `gio launch` | Idem X11 |
| **Raccourci d'arrêt d'urgence** | `RegisterHotKey` | `RegisterEventHotKey` (Carbon), sans permission | `XGrabKey` | Portail *GlobalShortcuts* (récent), sinon raccourci du bureau → `HADJ --toggle-pause` |
| Temps depuis la dernière saisie | `GetLastInputInfo` | `HIDIdleTime` (IOKit) | `XScreenSaverQueryInfo` | `ext-idle-notify` / Mutter IdleMonitor |
| Caméra | DirectShow | AVFoundation — **permission Caméra** | V4L2 | V4L2 (ou portail Caméra) |
| Micro | WinMM | CoreAudio via PortAudio — **permission Micro** | PipeWire / PulseAudio via PortAudio | Idem X11 |
| Sons de confirmation | `winsound` | Lecture WAV via `sounddevice` (déjà installé hors Windows) | Idem | Idem |
| Ouvrir un fichier, l'aide | `os.startfile` (4 endroits) | `QDesktopServices.openUrl` (Qt, toutes plateformes) | Idem | Idem |
| Icône près de l'horloge | Zone de notification | Barre des menus | Selon le bureau (GNOME : extension AppIndicator requise) | Idem X11 |
| Fenêtres d'état au premier plan | Qt | Qt | Qt | **Premier plan refusé par Wayland** : lancer l'interface via XWayland (`QT_QPA_PLATFORM=xcb`) |
| Vider la corbeille | PowerShell | Finder (`osascript`) | `gio trash --empty` | Idem X11 |

## 3. Phase 0 : noyau portable — **réalisée le 4 octobre 2026**

Ne change rien pour les utilisateurs Windows (586 tests, application vérifiée). Ce qui a été fait :

- `OSBackend.open_path()` et `empty_recycle_bin()` remplacent `os.startfile` et PowerShell dans
  l'application. L'implémentation par défaut utilise `open` sur macOS et `xdg-open` sur Linux.
- `OSBackend.capabilities()` est **déduit automatiquement** : une méthode que le backend ne réimplémente
  pas est « non disponible ». Les commandes et gestes concernés disparaissent alors de la grammaire.
  Le poing reste toujours lié à l'arrêt d'urgence.
- 9 actions qui envoient des raccourcis propres à Windows (Win+V, Win+R, Win+I…) sont marquées
  `WINDOWS_ONLY` et masquées ailleurs, en attendant leur équivalent par système.
- Le pilote caméra est choisi selon le système : DirectShow, AVFoundation ou V4L2.
- `os_layer/posix_sound.py` lit les sons de confirmation avec `sounddevice` sur macOS et Linux.
- `HADJ-NoTouch --pause | --resume | --toggle-pause | --show` pilote l'instance en cours par un canal local
  réservé à l'utilisateur. Relancer l'application affiche désormais son panneau au lieu d'un message.

Estimation initiale de la phase :

| Tâche | Où | Effort |
|---|---|---|
| Remplacer les 4 `os.startfile` par une fonction `open_path()` basée sur Qt | `ui/tray.py`, `commands/actions.py` | 0,5 j |
| Choisir le pilote caméra selon le système (DirectShow, AVFoundation, V4L2) | `vision/worker.py` | 0,5 j |
| Sons via `sounddevice` hors Windows | `os_layer` | 0,5 j |
| Ajouter `capabilities()` à `OSBackend` : l'application masque les commandes non disponibles (grammaire vocale, aide, réglages) au lieu d'échouer | `os_layer/base.py`, contrôleur, aide | 1 j |
| Commande `--toggle-pause` qui envoie l'arrêt d'urgence à l'instance en cours : secours partout où un raccourci global est impossible | `main.py`, `core/ipc.py` | 0,5 j |

Le point `capabilities()` est le plus important. Sur Wayland, « aimante la fenêtre à gauche » ne peut pas
fonctionner : la commande doit disparaître de la grammaire et de l'aide, au lieu d'être reconnue puis de
ne rien faire.

## 4. Phase 1 : Linux X11 — **backend réalisé le 4 octobre 2026, paquet AppImage à faire**

Fait : `src/os_layer/linux/` (`LinuxX11Backend`), avec python-xlib (100 % Python, LGPL) comme seule
dépendance.
- **Clavier, souris, texte Unicode** via XTEST.
- **Fenêtres** via EWMH : fermer, réduire, agrandir, aimanter, déplacer, toujours au premier plan, focus par titre.
- **Écrans** via RandR ; **bureaux virtuels** via `_NET_CURRENT_DESKTOP`.
- **Raccourci d'urgence** via `XGrabKey`, qui renvoie `False` si un autre programme possède déjà la
  combinaison.
- **Applications** via les fichiers `.desktop`, avec le nom dans la langue de l'utilisateur.
- **Son, luminosité, mode sombre, corbeille, verrouillage, extinction** via `wpctl`/`pactl`,
  `brightnessctl`, `gsettings`, `gio`, `loginctl`, `systemctl`. Si un outil est absent du PC, la commande
  correspondante disparaît.

Vérifié dans l'Ubuntu 24.04 de WSL, sur un vrai serveur X : 31 tests de logique, plus 8 tests où une
fenêtre réelle reçoit le texte tapé, les clics, le défilement et le raccourci global. Sur 16 passages
complets, 15 réussissent ; l'échec restant est un événement en trop ou manquant propre à WSLg.

Limites constatées :
- **Sous XWayland** (session Wayland, WSLg), le remappage temporaire d'une touche peut couper la connexion
  X. Le texte contenant des caractères absents du clavier (arabe, €…) est donc **refusé avec une erreur**
  au lieu d'être tapé à moitié. Solution prévue en phase 3 : passer par le presse-papiers.
- Si plus aucune fenêtre n'a le focus clavier, X ignore toutes les frappes, y compris le raccourci global.
  Le poing et « stop » restent alors l'arrêt d'urgence.

Reste à faire :
- paquet **AppImage** (environnement de build Linux nécessaire) ;
- validation sur un vrai bureau GNOME/KDE en session Xorg (gestion des fenêtres, caméra, micro).

Estimation initiale de la phase :

| Tâche | Effort |
|---|---|
| Clavier, souris, texte Unicode (XTest) | 2 j |
| Fenêtres et écrans (EWMH, XRandR) | 2 j |
| Luminosité, volume, mode sombre, verrouillage, extinction | 2 j |
| Applications (`.desktop`) | 1 j |
| Raccourci d'urgence (`XGrabKey`), temps d'inactivité | 0,5 j |
| Paquet **AppImage** : un seul fichier, sans installation, cohérent avec la version ZIP actuelle | 2 j |
| Tests et intégration continue (Ubuntu + Xvfb) | 1,5 j |

Cible : Ubuntu 22.04 et 24.04 LTS en session X11 (« Ubuntu sur Xorg » à l'écran de connexion), Debian 12.

**Flatpak est déconseillé** : son isolation bloque justement l'injection de clavier et de souris.

## 5. Phase 2 : macOS (environ 16 jours, plus un Mac et 99 $/an)

| Tâche | Effort |
|---|---|
| Clavier, souris, texte (Quartz `CGEvent`) ; coordonnées en points (écrans Retina) | 2 j |
| Fenêtres (API Accessibilité) | 3 j |
| Luminosité, volume, mode sombre, verrouillage, extinction | 2 j |
| Applications, raccourci d'urgence (Carbon), inactivité (IOKit) | 2 j |
| **Accueil des permissions** : écran guidé pour Accessibilité, Caméra et Micro, avec liens directs vers Réglages Système et état clair dans le cercle d'état si une permission manque | 2 j |
| Bundle `.app`, signature Developer ID, runtime renforcé, **notarisation**, image `.dmg` | 3 j |
| Tests (intégration continue macOS et tests manuels sur Mac) | 2 j |

**À savoir :**
- **Sans notarisation**, Gatekeeper bloque l'application au premier lancement. C'est le même problème que
  SmartScreen sur Windows (étape 4a).
- **Les permissions macOS sont enregistrées par le système** (base TCC). C'est une trace sur les postes
  partagés, inévitable sur macOS : à documenter pour les établissements.
- **Il faut viser Apple Silicon (arm64)** en priorité. MediaPipe, Vosk, PySide6 et CTranslate2 publient des
  paquets arm64. À confirmer version par version au moment du portage.

## 6. Phase 3 : Linux Wayland (environ 8 à 10 jours, support partiel)

- **Clavier et souris** : portail *RemoteDesktop* (GNOME 41+, KDE 5.27+). L'utilisateur accepte une
  fenêtre de consentement à chaque session. L'alternative `uinput` demande une règle udev posée une fois
  par un administrateur.
- **Arrêt d'urgence** : portail *GlobalShortcuts* là où il existe. Sinon, raccourci du bureau vers
  `HADJ --toggle-pause`. **Le poing et la commande vocale « stop » fonctionnent toujours**, quel que soit
  le système.
- **Fenêtres** : gestion non disponible de façon générique. Les commandes correspondantes sont masquées
  grâce à `capabilities()`.
- **Interface** : lancée via XWayland pour garder le cercle d'état et la grille au premier plan.

## 7. Risques

| Risque | Plateforme | Réponse |
|---|---|---|
| L'arrêt d'urgence ne peut pas être un raccourci global | Wayland sans portail | Poing et « stop » restent actifs ; `--toggle-pause` lié à un raccourci du bureau |
| Une permission refusée rend l'application muette | macOS | Écran d'accueil des permissions et état d'erreur explicite |
| La diversité des bureaux Linux (GNOME, KDE, XFCE…) | Linux | Cibler Ubuntu LTS officiellement ; le reste « au mieux » |
| Paquets natifs manquants (Linux ARM, Raspberry Pi) | Linux | Hors cible initiale |
| Concurrence de « Contrôle vocal » d'Apple | macOS | Mettre en avant les gestes, l'arabe, le hors-ligne et les profils |

## 8. Ce qu'il me faut pour démarrer

- **Pour Linux** : rien pour commencer. Ubuntu est déjà installé dans WSL sur ce PC : j'y développe et teste
  le clavier, la souris et les fenêtres (X11 via WSLg ou Xvfb). **La caméra et le micro ne passent pas dans
  WSL** : leur validation finale demande un vrai PC Linux, ou un portable démarré sur une clé Ubuntu.
- **Pour macOS** : un Mac (Apple Silicon de préférence) pour tester la caméra, le micro et les permissions,
  et un compte Apple Developer au moment de distribuer.
