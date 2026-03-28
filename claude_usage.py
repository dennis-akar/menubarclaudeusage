#!/usr/bin/env python3
"""Claude.ai Usage — macOS menu bar app."""

import json
import os
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
import rumps

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

CONFIG_DIR = Path.home() / ".config" / "claude-menubar"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    "cookie_source": "",  # set on first run; "auto", "brave", "safari", "chrome", "manual"
    "session_key": "",         # only used when cookie_source == "manual"
    "poll_interval_seconds": 60,
}

USAGE_URL = "https://claude.ai/api/organizations/{org_id}/usage"
ORGS_URL = "https://claude.ai/api/organizations"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://claude.ai/chats",
}


def load_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            stored = json.load(f)
        cfg = {**DEFAULT_CONFIG, **stored}
    else:
        cfg = dict(DEFAULT_CONFIG)
    return cfg


def save_config(cfg):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)


# ---------------------------------------------------------------------------
# Cookie extraction
# ---------------------------------------------------------------------------

def get_session_key_from_browser(source="auto"):
    """Try to extract the sessionKey cookie from the user's browser."""
    try:
        import rookiepy
    except ImportError:
        return None

    browsers = []
    if source == "auto":
        browsers = ["chrome", "safari", "firefox", "brave", "edge", "arc"]
    else:
        browsers = [source]

    for browser in browsers:
        try:
            fn = getattr(rookiepy, browser, None)
            if fn is None:
                continue
            cookies = fn(["claude.ai"])
            for c in cookies:
                if c.get("name") == "sessionKey" and c.get("value"):
                    return c["value"]
        except Exception:
            continue
    return None


def get_session_key(cfg):
    """Get sessionKey from config or browser."""
    if cfg["cookie_source"] == "manual":
        return cfg.get("session_key") or None
    return get_session_key_from_browser(cfg["cookie_source"])


# ---------------------------------------------------------------------------
# Claude.ai API
# ---------------------------------------------------------------------------

def fetch_org_id(session_key):
    """Get the first organization ID."""
    resp = requests.get(
        ORGS_URL,
        headers={**HEADERS, "Cookie": f"sessionKey={session_key}"},
        timeout=15,
    )
    resp.raise_for_status()
    orgs = resp.json()
    if not orgs:
        return None
    return orgs[0].get("uuid")


def fetch_usage(session_key, org_id):
    """Fetch usage data from claude.ai."""
    resp = requests.get(
        USAGE_URL.format(org_id=org_id),
        headers={**HEADERS, "Cookie": f"sessionKey={session_key}"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def format_reset_countdown(resets_at_str):
    """Format a 'resets_at' ISO timestamp into a human-readable countdown."""
    if not resets_at_str:
        return ""
    try:
        resets_at = datetime.fromisoformat(resets_at_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta = resets_at - now
        total_secs = int(delta.total_seconds())
        if total_secs <= 0:
            return "now"
        days, remainder = divmod(total_secs, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, _ = divmod(remainder, 60)
        if days > 0:
            return f"{days}d {hours}h"
        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"
    except Exception:
        return ""


def format_utilization(pct):
    """Format utilization percentage."""
    if pct is None:
        return "?"
    return f"{pct:.1f}%" if pct < 100 else "100%"


def build_title(usage_data):
    """Build the menu bar title string from usage data."""
    parts = []

    five = usage_data.get("five_hour")
    if five and five.get("utilization") is not None:
        pct = five["utilization"]
        parts.append(f"5h:{format_utilization(pct)}")

    seven = usage_data.get("seven_day")
    if seven and seven.get("utilization") is not None:
        pct = seven["utilization"]
        parts.append(f"7d:{format_utilization(pct)}")

    if not parts:
        return "Claude: --"

    return " | ".join(parts)


def build_menu_details(usage_data):
    """Build detailed menu item strings."""
    details = []

    # Main windows
    for key, label in [("five_hour", "Session (5h)"), ("seven_day", "Weekly (7d)")]:
        window = usage_data.get(key)
        if not window:
            continue
        pct = format_utilization(window.get("utilization"))
        reset = format_reset_countdown(window.get("resets_at"))
        line = f"{label}: {pct}"
        if reset:
            line += f"  \u2022  resets in {reset}"
        details.append(line)

    # Per-model breakdowns (if present)
    model_keys = [
        ("seven_day_opus", "Opus (7d)"),
        ("seven_day_sonnet", "Sonnet (7d)"),
    ]
    model_lines = []
    for key, label in model_keys:
        window = usage_data.get(key)
        if not window or window.get("utilization") is None:
            continue
        pct = format_utilization(window["utilization"])
        model_lines.append(f"  {label}: {pct}")
    if model_lines:
        details.append("")  # visual separator
        details.extend(model_lines)

    return details


# ---------------------------------------------------------------------------
# Menu bar app
# ---------------------------------------------------------------------------

class ClaudeUsageApp(rumps.App):
    def __init__(self):
        super().__init__(
            "Claude: ...",
            quit_button=None,  # we'll add our own
        )

        self.cfg = load_config()
        self.session_key = None
        self.org_id = None
        self.usage_data = None
        self.last_error = None

        # Menu items
        self.detail_items = [
            rumps.MenuItem("Loading...", callback=None),
        ]
        self.separator = rumps.separator
        self.refresh_btn = rumps.MenuItem("Refresh Now", callback=self.on_refresh)
        self.cookie_menu = rumps.MenuItem("Cookie Source")
        self.quit_btn = rumps.MenuItem("Quit", callback=self.on_quit)

        # Cookie source sub-menu
        for src in ["auto", "safari", "chrome", "brave", "firefox", "manual"]:
            item = rumps.MenuItem(src, callback=self.on_set_cookie_source)
            if src == self.cfg["cookie_source"]:
                item.state = 1
            self.cookie_menu.add(item)

        self.menu = [
            *self.detail_items,
            self.separator,
            self.refresh_btn,
            self.cookie_menu,
            self.separator,
            self.quit_btn,
        ]

        # Start background polling
        self.poll_interval = self.cfg.get("poll_interval_seconds", 60)
        self.timer = rumps.Timer(self.poll_usage, self.poll_interval)
        self.timer.start()

        # First-run: prompt for browser, then fetch
        if not self.cfg.get("cookie_source"):
            # Delay slightly so the menu bar has time to appear
            rumps.Timer(self._prompt_browser, 1).start()
        else:
            threading.Thread(target=self._initial_fetch, daemon=True).start()

    # -- first-run -----------------------------------------------------------

    def _prompt_browser(self, timer):
        timer.stop()
        browsers = ["Brave", "Chrome", "Safari", "Firefox", "Arc", "Edge"]
        resp = rumps.Window(
            message=(
                "Which browser are you logged into claude.ai with?\n\n"
                "Type one of: brave, chrome, safari, firefox, arc, edge\n"
                "(or 'auto' to try all)"
            ),
            title="Claude Usage \u2014 Setup",
            default_text="brave",
            ok="OK",
            cancel="Quit",
            dimensions=(260, 24),
        ).run()

        if not resp.clicked:
            rumps.quit_application()
            return

        choice = resp.text.strip().lower()
        # Try to match what they typed to a known browser
        known = {"brave": "brave", "chrome": "chrome", "safari": "safari",
                 "firefox": "firefox", "arc": "arc", "edge": "edge", "auto": "auto"}
        source = known.get(choice, "auto")

        self.cfg["cookie_source"] = source
        save_config(self.cfg)

        # Update checkmarks in menu
        for key in self.cookie_menu:
            self.cookie_menu[key].state = 1 if key == source else 0

        threading.Thread(target=self._initial_fetch, daemon=True).start()

    # -- callbacks -----------------------------------------------------------

    def on_quit(self, _):
        rumps.quit_application()

    def on_refresh(self, _):
        threading.Thread(target=self._do_fetch, daemon=True).start()

    def on_set_cookie_source(self, sender):
        new_source = sender.title
        self.cfg["cookie_source"] = new_source
        save_config(self.cfg)

        # Update checkmarks
        for key in self.cookie_menu:
            self.cookie_menu[key].state = 1 if key == new_source else 0

        # If switching to manual and no key set, prompt
        if new_source == "manual" and not self.cfg.get("session_key"):
            resp = rumps.Window(
                message="Paste your sessionKey cookie value:",
                title="Manual Session Key",
                default_text="sk-ant-sid01-...",
                ok="Save",
                cancel="Cancel",
                dimensions=(400, 24),
            ).run()
            if resp.clicked:
                self.cfg["session_key"] = resp.text.strip()
                save_config(self.cfg)

        # Re-fetch with new source
        self.session_key = None
        self.org_id = None
        threading.Thread(target=self._do_fetch, daemon=True).start()

    # -- polling -------------------------------------------------------------

    def poll_usage(self, _):
        self._do_fetch()

    def _initial_fetch(self):
        self._do_fetch()

    def _do_fetch(self):
        try:
            # Get session key
            if not self.session_key:
                self.session_key = get_session_key(self.cfg)
            if not self.session_key:
                self._set_error("No session key found. Check cookie source or login to claude.ai.")
                return

            # Get org ID
            if not self.org_id:
                self.org_id = fetch_org_id(self.session_key)
            if not self.org_id:
                self._set_error("Could not find organization.")
                return

            # Fetch usage
            data = fetch_usage(self.session_key, self.org_id)
            self.usage_data = data
            self.last_error = None
            self._update_display()

        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 401:
                # Session expired, clear and retry next cycle
                self.session_key = None
                self.org_id = None
                self._set_error("Session expired. Re-login to claude.ai.")
            else:
                self._set_error(f"HTTP {e.response.status_code if e.response else '?'}")
        except Exception as e:
            self._set_error(str(e)[:60])

    def _set_error(self, msg):
        self.last_error = msg
        self.title = "Claude: \u26a0"
        self._update_menu_items([f"\u26a0 {msg}"])

    def _update_display(self):
        if not self.usage_data:
            return
        self.title = build_title(self.usage_data)
        details = build_menu_details(self.usage_data)
        if not details:
            details = ["No usage data available"]
        self._update_menu_items(details)

    def _update_menu_items(self, lines):
        """Replace the detail items at the top of the menu."""
        # Remove old detail items
        for item in self.detail_items:
            if item.title in self.menu:
                del self.menu[item.title]

        # Add new ones
        self.detail_items = []
        for line in lines:
            item = rumps.MenuItem(line, callback=None)
            self.detail_items.append(item)

        # Insert at top of menu
        for i, item in enumerate(self.detail_items):
            self.menu.insert_before(self.refresh_btn.title, item)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    # Ensure config dir exists
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_FILE.exists():
        save_config(DEFAULT_CONFIG)

    app = ClaudeUsageApp()
    app.run()


if __name__ == "__main__":
    main()
