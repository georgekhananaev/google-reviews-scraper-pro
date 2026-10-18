"""
Signed-in Chrome profile support.

Google shows signed-out browsers only the first few reviews of a place. A
Chrome profile folder that is signed in to a Google account (set with
`browser_profile_dir`) lets the scraper load the full list.

The profile folder holds that account's login cookies, so it is treated as a
credential: created owner-only, never logged, and its sign-in cookies are
never handed to the image downloader.
"""

import os
import shutil
import sqlite3
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

# Cookies Google sets on .google.com only for a signed-in account.
SIGN_IN_COOKIES = ("SID", "__Secure-1PSID", "__Secure-3PSID")

LOGIN_URL = "https://accounts.google.com/ServiceLogin?continue=https%3A%2F%2Fwww.google.com%2Fmaps"

# Chrome locks a profile while it is open, so scrapes in this process take
# turns (the API runs several jobs in parallel threads).
PROFILE_LOCK = threading.Lock()

_CHROME_PATHS = {
    "darwin": [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ],
    "win32": [
        r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe",
        r"%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe",
        r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe",
    ],
}
_CHROME_COMMANDS = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser")


def profile_dir(config: Dict[str, Any]) -> Optional[Path]:
    """The configured profile folder as an absolute path, or None if unset."""
    raw = (config.get("browser_profile_dir") or "").strip()
    return Path(raw).expanduser().resolve() if raw else None


def prepare_profile_dir(path: Path) -> Path:
    """Create the profile folder, readable by the owner only."""
    path.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        path.chmod(0o700)
    return path


def is_auth_cookie(name: str) -> bool:
    """Google's sign-in cookies all contain "SID" (SID, HSID, SAPISID, __Secure-1PSID, ...)."""
    return "SID" in name


def is_signed_in(cookies: Iterable[Dict[str, Any]]) -> bool:
    """True if the browser cookies (driver.get_cookies()) include a Google sign-in."""
    return any(c.get("name") in SIGN_IN_COOKIES for c in cookies)


def profile_signed_in(path: Path) -> bool:
    """Read Chrome's cookie store in a closed profile and look for a Google sign-in."""
    for relative in ("Default/Network/Cookies", "Default/Cookies"):
        store = path / relative
        if not store.is_file():
            continue
        try:
            con = sqlite3.connect(f"{store.as_uri()}?mode=ro&immutable=1", uri=True)
            try:
                rows = con.execute(
                    "SELECT 1 FROM cookies WHERE host_key LIKE '%google.com' AND name IN (?, ?, ?) LIMIT 1",
                    SIGN_IN_COOKIES,
                ).fetchall()
            finally:
                con.close()
        except sqlite3.Error:
            continue
        if rows:
            return True
    return False


def find_chrome() -> Optional[str]:
    """Path of the installed Chrome (CHROME_BIN wins), or None."""
    candidates: List[str] = [os.environ.get("CHROME_BIN", "")]
    candidates += [os.path.expanduser(os.path.expandvars(p)) for p in _CHROME_PATHS.get(sys.platform, [])]
    candidates += [shutil.which(c) or "" for c in _CHROME_COMMANDS]
    return next((c for c in candidates if c and os.path.isfile(c)), None)


def open_login_window(chrome: str, path: Path) -> int:
    """
    Open a normal (not automated) Chrome window on the profile at Google's
    sign-in page and wait until that Chrome quits. Google often refuses
    sign-in from automated browsers, which is why this is plain Chrome.
    """
    return subprocess.call([
        chrome,
        f"--user-data-dir={path}",
        "--no-first-run",
        "--no-default-browser-check",
        LOGIN_URL,
    ])
