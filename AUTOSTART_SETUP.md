# Auto-start the agent server at Windows login

So you never have to start anything manually, the server can launch itself every
time you log in to Windows — silently in the background (no window, no browser
popup).

## Turn it ON (one time)

1. Put these files in your **agent folder** (next to `serve.py`):
   - `install_autostart.bat`
   - `install_autostart.ps1`
   - `uninstall_autostart.bat`
2. **Double-click `install_autostart.bat`.**
   It registers the server to run at login, then starts it now in the background.
   You'll see **DONE** in green.

That's it. From now on the agent is always running after you log in. Open it any
time at **http://127.0.0.1:8765**, and the Chrome extension will show
"agent connected" automatically.

## Turn it OFF

Double-click **`uninstall_autostart.bat`**. It stops auto-starting at login.
(The currently running copy keeps going until you reboot or end the `pythonw`
task in Task Manager.)

## How it works

- Adds a per-user entry to `HKCU\...\CurrentVersion\Run` named
  `OmniTradingAgentServer` that runs `pythonw serve.py --no-browser`.
- `pythonw` = Python with **no console window**; `--no-browser` stops it opening
  a tab at login.
- If a server is already running, a second copy detects the busy port and exits
  cleanly — no duplicates.
- No admin rights needed (it's per-user).

## Which "start it" option should I use?

You now have three, pick one:
- **Auto-start at login** (this) — best "set and forget". Always on.
- **Extension "Start server" button** — start on demand from the browser
  (needs `install_server_button.bat`).
- **`Start Trading Agent.bat`** — manual double-click, shows a console window.

Auto-start + the extension button work great together: it's normally already
running, and the button is there if you ever stopped it.
