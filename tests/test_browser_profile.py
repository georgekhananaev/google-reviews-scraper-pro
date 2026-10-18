"""
Tests for the signed-in Chrome profile (browser_profile_dir).

The profile holds Google login cookies, so besides the feature itself these
tests pin the safety rules: owner-only folder, sign-in cookies never reach
the image downloader, one Chrome per profile at a time.
"""

import os
import sqlite3
import stat
import threading
import time
from types import SimpleNamespace

import pytest

from modules import browser_profile as bp
from modules.image_handler import ImageHandler
from modules.scraper import GoogleReviewsScraper

AUTH_COOKIES = ["SID", "HSID", "SSID", "APISID", "SAPISID", "__Secure-1PSID",
                "__Secure-3PSID", "__Secure-1PAPISID", "SIDCC", "__Secure-1PSIDTS"]
OTHER_COOKIES = ["NID", "AEC", "SOCS", "__Secure-ENID"]


def write_cookie_store(profile, names, relative="Default/Network/Cookies"):
    store = profile / relative
    store.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(store)
    con.execute("CREATE TABLE cookies (host_key TEXT, name TEXT, value TEXT)")
    con.executemany("INSERT INTO cookies VALUES ('.google.com', ?, 'x')", [(n,) for n in names])
    con.commit()
    con.close()


class TestProfileFolder:

    def test_unset_means_off(self):
        assert bp.profile_dir({}) is None
        assert bp.profile_dir({"browser_profile_dir": "  "}) is None

    def test_path_is_expanded(self):
        path = bp.profile_dir({"browser_profile_dir": "~/grs-profile"})
        assert path.is_absolute() and "~" not in str(path)

    @pytest.mark.skipif(os.name == "nt", reason="POSIX permissions")
    def test_folder_is_owner_only(self, tmp_path):
        path = bp.prepare_profile_dir(tmp_path / "profile")
        assert stat.S_IMODE(path.stat().st_mode) == 0o700


class TestSignIn:

    @pytest.mark.parametrize("name", AUTH_COOKIES)
    def test_sign_in_cookies_are_recognised(self, name):
        assert bp.is_auth_cookie(name)

    @pytest.mark.parametrize("name", OTHER_COOKIES)
    def test_other_cookies_are_not(self, name):
        assert not bp.is_auth_cookie(name)

    def test_driver_cookies(self):
        assert bp.is_signed_in([{"name": "NID"}, {"name": "__Secure-1PSID"}])
        assert not bp.is_signed_in([{"name": "NID"}, {"name": "AEC"}])

    def test_closed_profile_signed_in(self, tmp_path):
        write_cookie_store(tmp_path, ["NID", "SID"])
        assert bp.profile_signed_in(tmp_path)

    def test_closed_profile_signed_in_older_chrome_layout(self, tmp_path):
        write_cookie_store(tmp_path, ["SID"], relative="Default/Cookies")
        assert bp.profile_signed_in(tmp_path)

    def test_closed_profile_signed_out(self, tmp_path):
        write_cookie_store(tmp_path, ["NID", "AEC"])
        assert not bp.profile_signed_in(tmp_path)
        assert not bp.profile_signed_in(tmp_path / "empty")


def test_sign_in_cookies_never_reach_image_downloader(tmp_path):
    handler = ImageHandler({"image_dir": str(tmp_path)})
    handler.apply_browser_cookies(
        [{"name": n, "value": "secret", "domain": ".google.com"} for n in AUTH_COOKIES + OTHER_COOKIES]
    )
    forwarded = {c.name for c in handler._session.cookies}
    assert forwarded == set(OTHER_COOKIES)


def test_find_chrome_prefers_chrome_bin(tmp_path, monkeypatch):
    fake = tmp_path / "chrome"
    fake.write_text("")
    monkeypatch.setenv("CHROME_BIN", str(fake))
    assert bp.find_chrome() == str(fake)


class TestBrowserLoginCommand:

    @pytest.fixture
    def run(self, monkeypatch):
        from start import _run_browser_login

        def run(config, signs_in=True, check=False, profile_dir=None):
            def fake_window(chrome, path):
                if signs_in:
                    write_cookie_store(path, ["SID"])
                return 0

            monkeypatch.setattr(bp, "find_chrome", lambda: "/fake/chrome")
            monkeypatch.setattr(bp, "open_login_window", fake_window)
            _run_browser_login(config, SimpleNamespace(profile_dir=profile_dir, check=check))
        return run

    def test_sign_in_succeeds(self, run, tmp_path, capsys):
        run({"browser_profile_dir": str(tmp_path / "p")})
        assert "is signed in" in capsys.readouterr().out

    def test_window_closed_without_sign_in(self, run, tmp_path, capsys):
        with pytest.raises(SystemExit) as exit_info:
            run({"browser_profile_dir": str(tmp_path / "p")}, signs_in=False)
        assert exit_info.value.code == 1
        assert "NOT signed in" in capsys.readouterr().out

    def test_check_does_not_open_chrome(self, run, tmp_path, capsys):
        write_cookie_store(tmp_path / "p", ["SID"])
        run({}, signs_in=False, check=True, profile_dir=str(tmp_path / "p"))
        assert "is signed in" in capsys.readouterr().out

    def test_missing_profile_folder_setting(self, run):
        with pytest.raises(SystemExit) as exit_info:
            run({})
        assert exit_info.value.code == 2


def test_scrapes_sharing_a_profile_take_turns(tmp_path):
    active, peak = 0, 0
    counter = threading.Lock()

    def fake_scrape(self):
        nonlocal active, peak
        with counter:
            active += 1
            peak = max(peak, active)
        time.sleep(0.2)
        with counter:
            active -= 1
        return True

    scrapers = []
    for _ in range(3):
        s = GoogleReviewsScraper.__new__(GoogleReviewsScraper)
        s.config = {"browser_profile_dir": str(tmp_path / "p")}
        s._scrape_with_retries = fake_scrape.__get__(s)
        scrapers.append(s)

    threads = [threading.Thread(target=s.scrape) for s in scrapers]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert peak == 1


def test_driver_opens_with_profile(tmp_path):
    """Integration: real headless Chrome writes into the profile folder."""
    profile = tmp_path / "profile"
    scraper = GoogleReviewsScraper.__new__(GoogleReviewsScraper)
    scraper.config = {"browser_profile_dir": str(profile)}
    driver = scraper.setup_driver(headless=True)
    try:
        driver.get("data:text/html,<p>ok</p>")
    finally:
        driver.quit()
    assert (profile / "Default").is_dir()
