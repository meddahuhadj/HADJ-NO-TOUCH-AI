# Threat model

`hadj-input` exists to control a computer on behalf of a person who cannot, or prefers not to, use the
keyboard and mouse. That power is the point of the library, so this document is explicit about what it
can do, what it cannot do, and how the risks are reduced.

> **Français.** Ce document décrit ce que la bibliothèque peut faire, ce qu'elle ne peut pas faire, et
> comment les risques sont réduits. Il est destiné aux équipes informatiques et de sécurité.

## 1. Assets

| Asset | Why it matters |
|---|---|
| Control of the user's session | Keystrokes and clicks can do anything the user can do |
| What the user types and sees | Must never be collected |
| Integrity of the machine | No persistence, no privilege change |
| The user's safety | Input must stop immediately when asked (emergency stop) |

## 2. Trust boundaries

```
 person ──voice/gesture──▶ HADJ No-Touch app (decides) ──calls──▶ hadj-input ──Win32──▶ Windows session
                                                                    │
                                                    no network, no hook, user rights only
```

The **application** decides *what* to do (it asks for confirmation before destructive commands).
`hadj-input` only *executes*, with the user's own rights, inside the user's own session.

## 3. Threats and mitigations

| # | Threat | Mitigation |
|---|---|---|
| T1 | Key logging / spying on typed text | No keyboard hook, no keyboard-state or raw-input API. Enforced by the export audit. |
| T2 | Data exfiltration | No network module may be imported. Enforced by the export audit. The full app also blocks sockets at runtime. |
| T3 | Privilege escalation | No elevation request. Windows UIPI blocks input to elevated windows (admin consoles, UAC prompt). |
| T4 | Persistence | No service, task, startup entry or file writes. Single registry write: `HKCU\…\Themes\Personalize` (dark mode, on request). |
| T5 | Stuck keys or buttons after a crash or stop | `release_all()` releases every modifier and every mouse button, including buttons pressed by another process. Called on pause, stop and exit. |
| T6 | Command injection through PowerShell | Only fixed scripts are run (brightness, Start-menu list). Numeric values are clamped integers inserted by the code, never user text. |
| T7 | Accidental destructive action (close, delete, shutdown) | Decided by the application: it asks “yes/no” first, and gestures can never trigger a command that needs confirmation. `shutdown` waits 5 s. |
| T8 | A malicious caller uses the library | Out of scope: any program running as the user can already call `SendInput`. The library adds no capability beyond the user's own rights. |
| T9 | Emergency stop blocked | The global emergency shortcut uses `RegisterHotKey` on its own thread, so it works even if the app's UI is busy. |

## 4. Residual risks

- Input injected into the wrong window if focus changes between two steps. Mitigation in the app: short,
  confirmed macros; the person can stop at any time.
- `type_text` into a terminal could run a command. Mitigation in the app: text steps are explicit and visible
  in the macro editor; destructive shortcuts force confirmation.
- Windows APIs used here (WMI brightness, `Get-StartApps`) depend on the system's own integrity.

## 5. How to verify

1. Read `src/hadj_input/windows/input.py`: every key and click goes through one `SendInput` call.
2. Search the code for `socket`, `http`, `SetWindowsHookEx`, `GetKeyboardState`: there are none.
3. Run `pytest`: the tests check the public API, the absence of forbidden imports and `release_all()`.
