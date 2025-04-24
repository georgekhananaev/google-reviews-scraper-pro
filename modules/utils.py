"""
Utility functions for Google Maps Reviews Scraper.
"""
import datetime
import logging
import re
import time
from datetime import timezone
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


def parse_date_to_iso(date_str: str) -> str:
    """
    Parse date strings like "2 weeks ago", "January 2023", etc. into ISO format.
    Returns a best-effort ISO string, or empty string if parsing fails.
    """
    if not date_str:
        return ""

    try:
        now = datetime.now(timezone.utc)

        # Handle relative dates
        if "ago" in date_str.lower():
            # For simplicity, map to approximate dates
            if "minute" in date_str.lower():
                minutes = int(re.search(r'\d+', date_str).group()) if re.search(r'\d+', date_str) else 1
                dt = now.replace(microsecond=0) - timezone.timedelta(minutes=minutes)
            elif "hour" in date_str.lower():
                hours = int(re.search(r'\d+', date_str).group()) if re.search(r'\d+', date_str) else 1
                dt = now.replace(microsecond=0) - timezone.timedelta(hours=hours)
            elif "day" in date_str.lower():
                days = int(re.search(r'\d+', date_str).group()) if re.search(r'\d+', date_str) else 1
                dt = now.replace(microsecond=0) - timezone.timedelta(days=days)
            elif "week" in date_str.lower():
                weeks = int(re.search(r'\d+', date_str).group()) if re.search(r'\d+', date_str) else 1
                dt = now.replace(microsecond=0) - timezone.timedelta(weeks=weeks)
            elif "month" in date_str.lower():
                months = int(re.search(r'\d+', date_str).group()) if re.search(r'\d+', date_str) else 1
                # Approximate months as 30 days
                dt = now.replace(microsecond=0) - timezone.timedelta(days=30 * months)
            elif "year" in date_str.lower():
                years = int(re.search(r'\d+', date_str).group()) if re.search(r'\d+', date_str) else 1
                # Approximate years as 365 days
                dt = now.replace(microsecond=0) - timezone.timedelta(days=365 * years)
            else:
                # Default to current time if can't parse
                dt = now.replace(microsecond=0)
        else:
            # Handle absolute dates (month year format)
            # This is a simplification - would need more robust parsing for production
            dt = now.replace(microsecond=0)

        return dt.isoformat()
    except Exception:
        # If parsing fails, return empty string
        return ""


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
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()

# """
# Utility functions for Google Maps Reviews Scraper.
# """
#
# import re
# import time
# import logging
# from datetime import datetime, timezone
# from functools import lru_cache
# from typing import List, Optional
#
# from selenium.common.exceptions import (NoSuchElementException,
#                                        StaleElementReferenceException,
#                                        TimeoutException)
# from selenium.webdriver import Chrome
# from selenium.webdriver.common.by import By
# from selenium.webdriver.remote.webelement import WebElement
# from selenium.webdriver.support import expected_conditions as EC
# from selenium.webdriver.support.ui import WebDriverWait
#
# # Constants for language detection
# HEB_CHARS = re.compile(r"[\u0590-\u05FF]")
# THAI_CHARS = re.compile(r"[\u0E00-\u0E7F]")
#
# # Logger
# log = logging.getLogger("scraper")
#
#
# @lru_cache(maxsize=1024)
# def detect_lang(txt: str) -> str:
#     """Detect language based on character sets"""
#     if HEB_CHARS.search(txt):  return "he"
#     if THAI_CHARS.search(txt): return "th"
#     return "en"
#
#
# @lru_cache(maxsize=128)
# def safe_int(s: str | None) -> int:
#     """Safely convert string to integer, returning 0 if not possible"""
#     m = re.search(r"\d+", s or "")
#     return int(m.group()) if m else 0
#
#
# def try_find(el: WebElement, css: str, *, all=False) -> List[WebElement]:
#     """Safely find elements by CSS selector without raising exceptions"""
#     try:
#         if all:
#             return el.find_elements(By.CSS_SELECTOR, css)
#         obj = el.find_element(By.CSS_SELECTOR, css)
#         return [obj] if obj else []
#     except (NoSuchElementException, StaleElementReferenceException):
#         return []
#
#
# def first_text(el: WebElement, css: str) -> str:
#     """Get text from the first matching element that has non-empty text"""
#     for e in try_find(el, css, all=True):
#         if (t := e.text.strip()):
#             return t
#     return ""
#
#
# def first_attr(el: WebElement, css: str, attr: str) -> str:
#     """Get attribute value from the first matching element that has a non-empty value"""
#     for e in try_find(el, css, all=True):
#         if (v := (e.get_attribute(attr) or "").strip()):
#             return v
#     return ""
#
#
# def click_if(driver: Chrome, css: str, delay: float = .25, timeout: float = 5.0) -> bool:
#     """Click element if it exists and is clickable, with timeout"""
#     try:
#         WebDriverWait(driver, timeout).until(
#             EC.element_to_be_clickable((By.CSS_SELECTOR, css))
#         ).click()
#         time.sleep(delay)
#         return True
#     except TimeoutException:
#         return False
#
#
# def parse_date_to_iso(date_str: str) -> str:
#     """
#     Parse date strings like "2 weeks ago", "January 2023", etc. into ISO format.
#     Returns a best-effort ISO string, or empty string if parsing fails.
#     """
#     if not date_str:
#         return ""
#
#     try:
#         now = datetime.now(timezone.utc)
#
#         # Handle relative dates
#         if "ago" in date_str.lower():
#             # For simplicity, map to approximate dates
#             if "minute" in date_str.lower():
#                 minutes = int(re.search(r'\d+', date_str).group()) if re.search(r'\d+', date_str) else 1
#                 dt = now.replace(microsecond=0) - timezone.timedelta(minutes=minutes)
#             elif "hour" in date_str.lower():
#                 hours = int(re.search(r'\d+', date_str).group()) if re.search(r'\d+', date_str) else 1
#                 dt = now.replace(microsecond=0) - timezone.timedelta(hours=hours)
#             elif "day" in date_str.lower():
#                 days = int(re.search(r'\d+', date_str).group()) if re.search(r'\d+', date_str) else 1
#                 dt = now.replace(microsecond=0) - timezone.timedelta(days=days)
#             elif "week" in date_str.lower():
#                 weeks = int(re.search(r'\d+', date_str).group()) if re.search(r'\d+', date_str) else 1
#                 dt = now.replace(microsecond=0) - timezone.timedelta(weeks=weeks)
#             elif "month" in date_str.lower():
#                 months = int(re.search(r'\d+', date_str).group()) if re.search(r'\d+', date_str) else 1
#                 # Approximate months as 30 days
#                 dt = now.replace(microsecond=0) - timezone.timedelta(days=30 * months)
#             elif "year" in date_str.lower():
#                 years = int(re.search(r'\d+', date_str).group()) if re.search(r'\d+', date_str) else 1
#                 # Approximate years as 365 days
#                 dt = now.replace(microsecond=0) - timezone.timedelta(days=365 * years)
#             else:
#                 # Default to current time if can't parse
#                 dt = now.replace(microsecond=0)
#         else:
#             # Handle absolute dates (month year format)
#             # This is a simplification - would need more robust parsing for production
#             dt = now.replace(microsecond=0)
#
#         return dt.isoformat()
#     except Exception:
#         # If parsing fails, return empty string
#         return ""
#
#
# def get_current_iso_date() -> str:
#     """Return current UTC time in ISO format."""
#     return datetime.now(timezone.utc).isoformat()
