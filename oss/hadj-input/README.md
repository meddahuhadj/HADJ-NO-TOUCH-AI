# hadj-input

Offline keyboard, mouse, window and display control for Windows, in pure Python (`ctypes`).

This is the operating-system layer of **HADJ No-Touch**, a hands-free accessibility app that lets people
control their PC with their voice and hand gestures. It is published so that hospitals, companies and
individual users can check for themselves exactly what the app is able to do to their computer.

> **Français.** `hadj-input` est la couche système de HADJ No-Touch : tout le code qui agit sur Windows
> (clavier, souris, fenêtres, écran, son). Nous le publions pour que les établissements de santé, les
> entreprises et les utilisateurs puissent vérifier eux-mêmes ce que l'application peut faire sur leur poste.
> Résumé de sécurité : aucune connexion réseau, aucun hook clavier, aucune lecture de ce que vous tapez,
> aucune élévation de privilèges, aucune persistance. Voir [SECURITY.md](SECURITY.md) et
> [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md).

## What it does

| Area | Examples | How |
|---|---|---|
| Keyboard | press keys, shortcuts, type Unicode text | `SendInput` |
| Mouse | move, click, drag, scroll, zoom (Ctrl+wheel) | `SendInput` |
| Windows | close, minimize, snap, move between monitors, always on top | `user32` window APIs |
| Display | brightness, monitor power, dark mode | WMI (fixed PowerShell script), `HKCU` theme value |
| System | volume, lock screen, screenshot, shutdown/restart | media keys, `LockWorkStation`, `shutdown.exe` |
| Apps | list Start-menu apps, launch one | `Get-StartApps`, `ShellExecute` |
| Safety | release every held key and mouse button | `release_all()` |
| Hotkey | one global emergency shortcut | `RegisterHotKey` (no hook) |

## What it never does

- **No network.** No socket, HTTP or update check. The export script refuses any network module.
- **No keyboard hook, no key logging.** It never reads what you type: no `SetWindowsHookEx`,
  `GetKeyboardState` or raw input. The only state it reads is whether the three *mouse buttons* are
  down, so that it can release a stuck button.
- **No elevation.** It runs with the user's rights. Windows (UIPI) prevents it from sending input to
  elevated windows such as an administrator console or the UAC prompt.
- **No persistence.** No service, scheduled task, startup entry or file outside the caller's folder.
  The only registry write is the user's own dark-mode preference (`HKCU`), when asked.

These rules are checked automatically on every export, see `scripts/export_oss.py` in the main project.

## Install and use

Requires Windows 10/11 and Python 3.10+. No third-party dependency.

```bash
pip install .
```

```python
from hadj_input import create_backend

os = create_backend()
os.prepare_process()          # per-monitor DPI awareness: real pixel coordinates
os.hotkey("ctrl", "c")
os.type_text("Bonjour 👋 مرحبا")
os.mouse_move(400, 300)
os.mouse_button("left", "click")
os.release_all()              # always safe to call: nothing stays pressed
```

Every method is documented in [`hadj_input/base.py`](src/hadj_input/base.py) (`OSBackend`).
Code comments are partly in Arabic, the project's original language. English translations are welcome.

## Status

Version {{version}}. Windows only. A macOS/Linux backend can be added by implementing `OSBackend`.

## License

Apache License 2.0, see [LICENSE](LICENSE). It includes an explicit patent grant, which legal teams in
hospitals and companies usually ask for.
