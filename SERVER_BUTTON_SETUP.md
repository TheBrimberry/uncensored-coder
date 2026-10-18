# One-click "Start server" button (Chrome extension)

The extension now has a green **▶ Start server** button (Settings tab). A browser
extension can't launch a program by itself, so this uses Chrome's official
**Native Messaging**: you install a tiny helper once, then the button starts
`serve.py` for you every time.

## One-time install (2 minutes)

1. Put these files in your **agent folder** (the same folder as `serve.py`):
   - `native_host.py`
   - `install_server_button.bat`
   - `install_server_button.ps1`
   (They're already there if you pulled the repo / used the full bundle.)

2. **Double-click `install_server_button.bat`.**
   It finds Python, writes the helper, and registers it for Chrome and Edge.
   You should see **SUCCESS** in green.

3. In Chrome go to `chrome://extensions`:
   - If you loaded the extension before, **remove it** (the ID changed because the
     extension is now signed with a fixed key).
   - Click **Load unpacked** and select the `chrome-extension` folder again.

4. Open the extension → **Settings** tab → click **▶ Start server**.
   The pill turns green **running** and the server launches in the background.

## After setup

- Click **▶ Start server** any time the pill shows **not running**.
- If it's already up, the button just confirms it's connected.

## If the button says "helper not installed"

You skipped step 2, or Chrome was open before you installed. Run
`install_server_button.bat` once, fully quit Chrome, reopen it, and try again.

## Fallback (always works)

You can still start the server the manual way any time: double-click
**Start Trading Agent.bat** (or run `python serve.py`).

## Technical notes

- Host name: `com.omni.trading.launcher`
- Extension ID (pinned by the manifest `key`): `knaemjhcpncdliiclcpgcecpicnkgmdi`
- The helper only ever launches `serve.py` from its own folder — nothing else.
- Registered under HKCU (your user only); no admin rights needed.
