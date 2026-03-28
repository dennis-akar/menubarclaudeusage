# Claude Usage — macOS Menu Bar App

A lightweight macOS menu bar app that shows your Claude.ai usage (session and weekly utilization) at a glance.

```
5h:10.0% | 7d:7.0%
```

## Requirements

- macOS 13+ (Ventura or later)
- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- A Claude.ai account (Pro/Max) with an active session in your browser

## Setup

```bash
git clone <repo-url>
cd menubarclaudeusage

# Create virtual environment and install dependencies
uv venv
uv pip install -e .
```

## Run

```bash
.venv/bin/python claude_usage.py
```

On first launch, a dialog will ask which browser you're logged into claude.ai with. Type one of:

- `brave`
- `chrome`
- `safari`
- `firefox`
- `arc`
- `edge`
- `auto` (tries all browsers)

Your choice is saved to `~/.config/claude-menubar/config.json` so you won't be asked again.

### Keychain prompt

When the app reads cookies from a Chromium-based browser (Brave, Chrome, Arc, Edge), macOS will show a Keychain access dialog asking to use "Chrome Safe Storage" or similar. This is the browser's cookie encryption key — **click Allow** to let the app read your claude.ai session cookie. It does not access passwords, autofill, or any other data.

Safari requires **Full Disk Access** for your terminal in System Settings > Privacy & Security.

## What it shows

**Menu bar:** `5h:10.0% | 7d:7.0%` — your session (5-hour) and weekly (7-day) utilization.

**Click the menu bar item** to see:

- Detailed usage with reset countdowns (e.g., "Session (5h): 42.5% · resets in 2h 15m")
- Per-model breakdowns (Opus/Sonnet) when available
- **Refresh Now** — manually re-fetch usage
- **Cookie Source** — switch browsers at any time
- **Quit**

Usage auto-refreshes every 60 seconds.

## Manual cookie mode

If you'd rather not grant Keychain access, select **manual** from the Cookie Source menu. You'll be prompted to paste your `sessionKey` cookie:

1. Open claude.ai in your browser
2. Open DevTools (F12 or Cmd+Option+I)
3. Go to **Application** > **Cookies** > `https://claude.ai`
4. Copy the value of the `sessionKey` cookie
5. Paste it into the dialog

## Configuration

Config is stored at `~/.config/claude-menubar/config.json`:

```json
{
  "cookie_source": "brave",
  "session_key": "",
  "poll_interval_seconds": 60
}
```

- `cookie_source` — which browser to read cookies from (`auto`, `brave`, `chrome`, `safari`, `firefox`, `arc`, `edge`, `manual`)
- `session_key` — only used when `cookie_source` is `manual`
- `poll_interval_seconds` — how often to refresh usage (default: 60)

## Build as a standalone .app

```bash
uv pip install -e ".[build]"
.venv/bin/python setup.py py2app
```

This creates `dist/Claude Usage.app`. Move it to `/Applications/` and add it to **System Settings > General > Login Items** to start at login. The app hides from the Dock automatically.

## How it works

The app uses [rookiepy](https://github.com/thewh1teagle/rookie) to read your `sessionKey` cookie from your browser's local cookie store, then calls Claude.ai's internal usage API (`/api/organizations/{orgId}/usage`) — the same endpoint the web interface uses. All data stays local.

## License

MIT
