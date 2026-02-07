"""
Utility functions for Google Maps Reviews Scraper.
"""
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import List

from selenium.common.exceptions import (NoSuchElementException,
                                        StaleElementReferenceException,
                                        TimeoutException)
from selenium.webdriver import Chrome
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# Logger
log = logging.getLogger("scraper")

# Constants for language detection
HEB_CHARS = re.compile(r"[\u0590-\u05FF]")
THAI_CHARS = re.compile(r"[\u0E00-\u0E7F]")


@lru_cache(maxsize=1024)
def detect_lang(txt: str) -> str:
    """Detect language based on character sets"""
    if HEB_CHARS.search(txt):  return "he"
    if THAI_CHARS.search(txt): return "th"
    return "en"


@lru_cache(maxsize=128)
def safe_int(s: str | None) -> int:
    """Safely convert string to integer, returning 0 if not possible"""
    m = re.search(r"\d+", s or "")
    return int(m.group()) if m else 0


def try_find(el: WebElement, css: str, *, all=False) -> List[WebElement]:
    """Safely find elements by CSS selector without raising exceptions"""
    try:
        if all:
            return el.find_elements(By.CSS_SELECTOR, css)
        obj = el.find_element(By.CSS_SELECTOR, css)
        return [obj] if obj else []
    except (NoSuchElementException, StaleElementReferenceException):
        return []


def first_text(el: WebElement, css: str) -> str:
    """Get text from the first matching element that has non-empty text"""
    for e in try_find(el, css, all=True):
        try:
            if (t := e.text.strip()):
                return t
        except StaleElementReferenceException:
            continue
    return ""


_UNIT_KEYWORDS = {
    "year": [
        "year", "years",
        "tahun",                                          # Indonesian
        "año", "años",                                    # Spanish
        "an", "ans", "année", "années",                   # French
        "jahr", "jahre", "jahren",                        # German
        "anno", "anni",                                   # Italian
        "ano", "anos",                                    # Portuguese
        "год", "года", "лет",                             # Russian
        "년",                                             # Korean
        "年",                                             # Japanese / Chinese
        "سنة", "سنوات",                                   # Arabic
        "साल", "वर्ष",                                     # Hindi
        "yıl",                                            # Turkish
        "jaar", "jaren",                                  # Dutch
        "rok", "lat", "lata", "roku",                     # Polish
        "năm",                                            # Vietnamese
        "år",                                             # Swedish / Norwegian / Danish
        "vuosi", "vuotta",                                # Finnish
        "χρόνο", "χρόνια", "έτος", "έτη",                 # Greek
        "roky", "let", "lety",                            # Czech
        "ani",                                            # Romanian
        "év", "éve", "évet",                              # Hungarian
        "ปี",                                             # Thai
        "שנה", "שנים",                                     # Hebrew
        "година", "години",                                # Bulgarian
    ],
    "month": [
        "month", "months",
        "bulan",                                          # Indonesian
        "mes", "meses",                                   # Spanish
        "mois",                                           # French
        "monat", "monate", "monaten",                     # German
        "mese", "mesi",                                   # Italian
        "mês",                                            # Portuguese
        "месяц", "месяца", "месяцев",                     # Russian
        "개월",                                            # Korean
        "か月", "ヶ月", "ケ月", "个月", "個月",               # Japanese / Chinese
        "شهر", "أشهر", "شهور",                             # Arabic
        "महीना", "महीने",                                   # Hindi
        "ay",                                             # Turkish
        "maand", "maanden",                               # Dutch
        "miesiąc", "miesiące", "miesięcy",                # Polish
        "tháng",                                          # Vietnamese
        "månad", "månader",                               # Swedish
        "måned", "måneder",                               # Norwegian / Danish
        "kuukausi", "kuukautta",                          # Finnish
        "μήνα", "μήνες",                                   # Greek
        "měsíc", "měsíce", "měsíců", "měsíci",           # Czech
        "lună", "luni",                                   # Romanian
        "hónap", "hónapja",                               # Hungarian
        "เดือน",                                           # Thai
        "חודש", "חודשים",                                   # Hebrew
        "месец", "месеца",                                 # Bulgarian
    ],
    "week": [
        "week", "weeks",
        "minggu",                                         # Indonesian
        "semana", "semanas",                              # Spanish / Portuguese
        "semaine", "semaines",                            # French
        "woche", "wochen",                                # German
        "settimana", "settimane",                         # Italian
        "неделя", "недели", "недель",                      # Russian
        "주",                                              # Korean
        "週間", "週",                                       # Japanese
        "周",                                              # Chinese
        "أسبوع", "أسابيع",                                  # Arabic
        "हफ्ता", "हफ्ते", "सप्ताह",                         # Hindi
        "hafta",                                          # Turkish
        "weken",                                          # Dutch
        "tydzień", "tygodnie", "tygodni",                 # Polish
        "tuần",                                           # Vietnamese
        "vecka", "veckor",                                # Swedish
        "uke", "uker",                                    # Norwegian
        "uge", "uger",                                    # Danish
        "viikko", "viikkoa",                              # Finnish
        "εβδομάδα", "εβδομάδες",                           # Greek
        "týden", "týdny", "týdnů",                        # Czech
        "săptămână", "săptămâni",                         # Romanian
        "hét", "hete",                                    # Hungarian
        "สัปดาห์",                                          # Thai
        "שבוע", "שבועות",                                   # Hebrew
        "седмица", "седмици",                               # Bulgarian
    ],
    "day": [
        "day", "days",
        "hari",                                           # Indonesian
        "día", "días",                                    # Spanish
        "jour", "jours",                                  # French
        "tag", "tage", "tagen",                           # German
        "giorno", "giorni",                               # Italian
        "dia", "dias",                                    # Portuguese
        "день", "дня", "дней",                             # Russian
        "일",                                              # Korean
        "日",                                              # Japanese / Chinese
        "يوم", "أيام",                                      # Arabic
        "दिन",                                              # Hindi
        "gün",                                            # Turkish
        "dag", "dagen", "dagar",                          # Dutch / Swedish / Norwegian / Danish
        "dzień", "dni",                                   # Polish
        "ngày",                                           # Vietnamese
        "päivä", "päivää",                                # Finnish
        "ημέρα", "ημέρες", "μέρα", "μέρες",               # Greek
        "den", "dny", "dnů", "dní",                       # Czech
        "zi", "zile",                                     # Romanian
        "nap", "napja",                                   # Hungarian
        "วัน",                                             # Thai
        "יום", "ימים",                                      # Hebrew
        "ден", "дни",                                      # Bulgarian
    ],
    "hour": [
        "hour", "hours",
        "jam",                                            # Indonesian
        "hora", "horas",                                  # Spanish / Portuguese
        "heure", "heures",                                # French
        "stunde", "stunden",                              # German
        "ora", "ore",                                     # Italian / Romanian
        "час", "часа", "часов",                            # Russian / Bulgarian
        "시간",                                             # Korean
        "時間",                                             # Japanese
        "小时", "小時",                                      # Chinese
        "ساعة", "ساعات",                                    # Arabic
        "घंटा", "घंटे",                                     # Hindi
        "saat",                                           # Turkish
        "uur",                                            # Dutch
        "godzina", "godziny", "godzin",                   # Polish
        "giờ",                                            # Vietnamese
        "timme", "timmar",                                # Swedish
        "time", "timer",                                  # Norwegian / Danish
        "tunti", "tuntia",                                # Finnish
        "ώρα", "ώρες",                                     # Greek
        "hodina", "hodiny", "hodin",                      # Czech
        "óra", "órája",                                   # Hungarian
        "ชั่วโมง",                                          # Thai
        "שעה", "שעות",                                      # Hebrew
    ],
    "minute": [
        "minute", "minutes",
        "menit",                                          # Indonesian
        "minuto", "minutos",                              # Spanish / Portuguese / Italian
        "minuten",                                        # German / Dutch
        "minuti",                                         # Italian
        "минута", "минуты", "минут", "минути",             # Russian / Bulgarian
        "분",                                              # Korean
        "分",                                              # Japanese / Chinese
        "دقيقة", "دقائق",                                   # Arabic
        "मिनट",                                             # Hindi
        "dakika",                                         # Turkish
        "minuta", "minuty", "minut",                      # Polish / Czech
        "phút",                                           # Vietnamese
        "minuter",                                        # Swedish
        "minutt", "minutter",                             # Norwegian / Danish
        "minuutti", "minuuttia",                          # Finnish
        "λεπτό", "λεπτά",                                  # Greek
        "perc", "perce",                                  # Hungarian
        "นาที",                                            # Thai
        "דקה", "דקות",                                      # Hebrew
    ],
}

# Dual forms (Arabic/Hebrew) where the word itself encodes "2"
_DUAL_FORMS = {
    "שנתיים": ("year", 2), "חודשיים": ("month", 2), "שבועיים": ("week", 2),
    "יומיים": ("day", 2), "שעתיים": ("hour", 2),
    "سنتين": ("year", 2), "شهرين": ("month", 2), "أسبوعين": ("week", 2),
    "يومين": ("day", 2), "ساعتين": ("hour", 2),
}

# Build reverse lookup: keyword → unit (sorted longest-first for matching priority)
_WORD_TO_UNIT = {}
for _unit, _keywords in _UNIT_KEYWORDS.items():
    for _kw in _keywords:
        _WORD_TO_UNIT[_kw.lower()] = _unit
_SORTED_KEYWORDS = sorted(_WORD_TO_UNIT.items(), key=lambda x: -len(x[0]))


def parse_date_to_iso(date_str: str) -> str:
    """Parse relative date strings in 25+ languages into ISO format."""
    if not date_str:
        return ""

    try:
        now = datetime.now(timezone.utc).replace(microsecond=0)
        text = date_str.lower()

        # Check dual forms first (Arabic/Hebrew "two years" as single word)
        for dual_word, (unit, amount) in _DUAL_FORMS.items():
            if dual_word in text:
                return _compute_date(now, unit, amount)

        # Extract numeric value (default 1 for "a year ago", "setahun lalu", etc.)
        num_match = re.search(r'\d+', text)
        amount = int(num_match.group()) if num_match else 1

        # Find time unit keyword in any language
        for kw, unit in _SORTED_KEYWORDS:
            if kw in text:
                return _compute_date(now, unit, amount)

        return ""
    except Exception:
        return ""


def _compute_date(now: datetime, unit: str, amount: int) -> str:
    """Subtract the given amount of time units from now and return ISO string."""
    deltas = {
        "minute": timedelta(minutes=amount),
        "hour":   timedelta(hours=amount),
        "day":    timedelta(days=amount),
        "week":   timedelta(weeks=amount),
        "month":  timedelta(days=30 * amount),
        "year":   timedelta(days=365 * amount),
    }
    dt = now - deltas.get(unit, timedelta())
    return dt.isoformat()


def first_attr(el: WebElement, css: str, attr: str) -> str:
    """Get attribute value from the first matching element that has a non-empty value"""
    for e in try_find(el, css, all=True):
        try:
            if (v := (e.get_attribute(attr) or "").strip()):
                return v
        except StaleElementReferenceException:
            continue
    return ""


def click_if(driver: Chrome, css: str, delay: float = .25, timeout: float = 5.0) -> bool:
    """
    Click element if it exists and is clickable, with timeout and better error handling.

    Args:
        driver: WebDriver instance
        css: CSS selector for the element to click
        delay: Time to wait after clicking (seconds)
        timeout: Maximum time to wait for element (seconds)

    Returns:
        True if element was found and clicked, False otherwise
    """
    try:
        # First check if elements exist at all
        elements = driver.find_elements(By.CSS_SELECTOR, css)
        if not elements:
            return False

        # Try clicking the first visible element
        for element in elements:
            try:
                if element.is_displayed() and element.is_enabled():
                    element.click()
                    time.sleep(delay)
                    return True
            except Exception:
                # Try next element if this one fails
                continue

        # If we couldn't click any of the direct elements, try with WebDriverWait
        try:
            WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, css))
            ).click()
            time.sleep(delay)
            return True
        except TimeoutException:
            return False

    except Exception as e:
        log.debug(f"Error in click_if: {str(e)}")
        return False


def get_current_iso_date() -> str:
    """Return current UTC time in ISO format."""
    return datetime.now(timezone.utc).isoformat()
