# Security policy / Politique de sécurité

## Reporting a vulnerability

Please **do not open a public issue** for a security problem.
Use GitHub's private reporting instead: **Security → Report a vulnerability** on this repository.

We aim to acknowledge reports within 7 days and to publish a fix or mitigation within 30 days for
confirmed issues. We credit reporters in the release notes unless they prefer to stay anonymous.

> **Français.** Merci de ne pas ouvrir de ticket public pour un problème de sécurité. Utilisez le
> signalement privé de GitHub : **Security → Report a vulnerability**. Nous répondons sous 7 jours et
> visons un correctif sous 30 jours pour tout problème confirmé.

## Supported versions

Only the latest release receives security fixes.

## Scope

In scope: anything in `src/hadj_input` that could let a third party
- send input or run an action the caller did not request,
- read user data (keystrokes, window contents, files),
- reach the network,
- gain privileges or persist on the machine,
- leave a key or mouse button stuck down after `release_all()`.

Out of scope: what an application chooses to do with this library (it is, by design, able to control the
keyboard and mouse: see [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md)).

## Guarantees checked automatically

Each export from the main project is refused if the code:
- imports a network module (`socket`, `urllib`, `http`, `requests`, `ssl`, `asyncio`…),
- calls a keyboard hook or keyboard-state API (`SetWindowsHookEx`, `GetKeyboardState`, raw input,
  `BlockInput`, `keybd_event`),
- reads `GetAsyncKeyState` for anything other than the three mouse buttons,
- imports code from the rest of the application.
