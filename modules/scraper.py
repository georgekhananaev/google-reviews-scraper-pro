"""
Selenium scraping logic for Google Maps Reviews.
Uses SeleniumBase UC Mode for enhanced anti-detection and better Chrome version management.
"""

import logging
import os
import platform
import re
import threading
import time
import traceback
from typing import Dict, Any, List

from seleniumbase import Driver
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
from selenium.webdriver import Chrome
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, MofNCompleteColumn

from modules.models import RawReview
from modules.pipeline import PostScrapeRunner
from modules.review_db import ReviewDB
from modules.place_id import extract_place_id

# Logger
log = logging.getLogger("scraper")

# CSS Selectors
PANE_SEL = 'div[role="main"] div.m6QErb.DxyBCb.kA9KIf.dS8AEf'
CARD_SEL = "div[data-review-id]"
COOKIE_BTN = ('button[aria-label*="Accept" i],'
              'button[jsname="hZCF7e"],'
              'button[data-mdc-dialog-action="accept"]')
SORT_BTN = 'button[aria-label="Sort reviews" i], button[aria-label="Sort" i]'
MENU_ITEMS = 'div[role="menu"] [role="menuitem"], li[role="menuitem"]'

SORT_OPTIONS = {
    "newest": (
        "Newest", "החדשות ביותר", "ใหม่ที่สุด", "最新", "Más recientes", "最近",
        "Mais recentes", "Neueste", "Plus récent", "Più recenti", "Nyeste",
        "Новые", "Nieuwste", "جديد", "Nyeste", "Uusimmat", "Najnowsze",
        "Senaste", "Terbaru", "Yakın zamanlı", "Mới nhất", "नवीनतम"
    ),
    "highest": (
        "Highest rating", "הדירוג הגבוה ביותר", "คะแนนสูงสุด", "最高評価",
        "Calificación más alta", "最高评分", "Melhor avaliação", "Höchste Bewertung",
        "Note la plus élevée", "Valutazione più alta", "Høyeste vurdering",
        "Наивысший рейтинг", "Hoogste waardering", "أعلى تقييم", "Højeste vurdering",
        "Korkein arvostelu", "Najwyższa ocena", "Högsta betyg", "Peringkat tertinggi",
        "En yüksek puan", "Đánh giá cao nhất", "उच्चतम रेटिंग", "Top rating"
    ),
    "lowest": (
        "Lowest rating", "הדירוג הנמוך ביותר", "คะแนนต่ำสุด", "最低評価",
        "Calificación más baja", "最低评分", "Pior avaliação", "Niedrigste Bewertung",
        "Note la plus basse", "Valutazione più bassa", "Laveste vurdering",
        "Наименьший рейтинг", "Laagste waardering", "أقل تقييم", "Laveste vurdering",
        "Alhaisin arvostelu", "Najniższa ocena", "Lägsta betyg", "Peringkat terendah",
        "En düşük puan", "Đánh giá thấp nhất", "निम्नतम रेटिंग", "Worst rating"
    ),
    "relevance": (
        "Most relevant", "רלוונטיות ביותר", "เกี่ยวข้องมากที่สุด", "関連性",
        "Más relevantes", "最相关", "Mais relevantes", "Relevanteste",
        "Plus pertinents", "Più pertinenti", "Mest relevante",
        "Наиболее релевантные", "Meest relevant", "الأكثر صلة", "Mest relevante",
        "Olennaisimmat", "Najbardziej trafne", "Mest relevanta", "Paling relevan",
        "En alakalı", "Liên quan nhất", "सबसे प्रासंगिक", "Relevance"
    )
}

# Comprehensive multi-language review keywords
REVIEW_WORDS = {
    # English
    "reviews", "review", "ratings", "rating",

    # Hebrew
    "ביקורות", "ביקורת", "ביקורות על", "דירוגים", "דירוג",

    # Thai
    "รีวิว", "บทวิจารณ์", "คะแนน", "ความคิดเห็น",

    # Spanish
    "reseñas", "opiniones", "valoraciones", "críticas", "calificaciones",

    # French
    "avis", "commentaires", "évaluations", "critiques", "notes",

    # German
    "bewertungen", "rezensionen", "beurteilungen", "meinungen", "kritiken",

    # Italian
    "recensioni", "valutazioni", "opinioni", "giudizi", "commenti",

    # Portuguese
    "avaliações", "comentários", "opiniões", "análises", "críticas",

    # Russian
    "отзывы", "рецензии", "обзоры", "оценки", "комментарии",

    # Japanese
    "レビュー", "口コミ", "評価", "批評", "感想",

    # Korean
    "리뷰", "평가", "후기", "댓글", "의견",

    # Chinese (Simplified and Traditional)
    "评论", "評論", "点评", "點評", "评价", "評價", "意见", "意見", "回顾", "回顧",

    # Arabic
    "مراجعات", "تقييمات", "آراء", "تعليقات", "نقد",

    # Hindi
    "समीक्षा", "रिव्यू", "राय", "मूल्यांकन", "प्रतिक्रिया",

    # Turkish
    "yorumlar", "değerlendirmeler", "incelemeler", "görüşler", "puanlar",

    # Dutch
    "beoordelingen", "recensies", "meningen", "opmerkingen", "waarderingen",

    # Polish
    "recenzje", "opinie", "oceny", "komentarze", "uwagi",

    # Vietnamese
    "đánh giá", "nhận xét", "bình luận", "phản hồi", "bài đánh giá",

    # Indonesian
    "ulasan", "tinjauan", "komentar", "penilaian", "pendapat",

    # Swedish
    "recensioner", "betyg", "omdömen", "åsikter", "kommentarer",

    # Norwegian
    "anmeldelser", "vurderinger", "omtaler", "meninger", "tilbakemeldinger",

    # Danish
    "anmeldelser", "bedømmelser", "vurderinger", "meninger", "kommentarer",

    # Finnish
    "arvostelut", "arviot", "kommentit", "mielipiteet", "palautteet",

    # Greek
    "κριτικές", "αξιολογήσεις", "σχόλια", "απόψεις", "βαθμολογίες",

    # Czech
    "recenze", "hodnocení", "názory", "komentáře", "posudky",

    # Romanian
    "recenzii", "evaluări", "opinii", "comentarii", "note",

    # Hungarian
    "vélemények", "értékelések", "kritikák", "hozzászólások", "megjegyzések",

    # Bulgarian
    "отзиви", "ревюта", "мнения", "коментари", "оценки"
}


class GoogleReviewsScraper:
    """Main scraper class for Google Maps reviews"""

    def __init__(self, config: Dict[str, Any],
                 cancel_event: threading.Event | None = None):
        """Initialize scraper with configuration"""
        self.config = config
        self.scrape_mode = config.get("scrape_mode", "update")
        self.cancel_event = cancel_event or threading.Event()
        db_path = config.get("db_path", "reviews.db")
        self.review_db = ReviewDB(db_path)

    @staticmethod
    def _db_review_to_legacy(db_review: Dict[str, Any]) -> Dict[str, Any]:
        """Convert DB review format to legacy format for MongoDB/JSON compat."""
        text = db_review.get("review_text", {})
        description = text if isinstance(text, dict) else {}
        images = db_review.get("user_images", [])
        owner = db_review.get("owner_responses", {})
        return {
            "review_id": db_review.get("review_id", ""),
            "place_id": db_review.get("place_id", ""),
            "author": db_review.get("author", ""),
            "rating": db_review.get("rating", 0),
            "description": description,
            "likes": db_review.get("likes", 0),
            "user_images": images if isinstance(images, list) else [],
            "author_profile_url": db_review.get("profile_url", ""),
            "profile_picture": db_review.get("profile_picture", ""),
            "owner_responses": owner if isinstance(owner, dict) else {},
            "created_date": db_review.get("created_date", ""),
            "review_date": db_review.get("review_date", ""),
            "last_modified_date": db_review.get("last_modified", ""),
        }

    def setup_driver(self, headless: bool):
        """
        Set up and configure Chrome driver using SeleniumBase UC Mode.
        SeleniumBase provides enhanced anti-detection and automatic Chrome/ChromeDriver version management.
        Works in both Docker containers and on regular OS installations (Windows, Mac, Linux).
        """
        # Log platform information for debugging
        log.info(f"Platform: {platform.platform()}")
        log.info(f"Python version: {platform.python_version()}")
        log.info("Using SeleniumBase UC Mode for enhanced anti-detection")

        # Determine if we're running in a container
        in_container = os.environ.get('CHROME_BIN') is not None

        if in_container:
            chrome_binary = os.environ.get('CHROME_BIN')
            log.info(f"Container environment detected")
            log.info(f"Chrome binary: {chrome_binary}")

            # Create driver with custom binary location for containers
            if chrome_binary and os.path.exists(chrome_binary):
                try:
                    driver = Driver(
                        uc=True,
                        headless=headless,
                        binary_location=chrome_binary,
                        page_load_strategy="normal"
                    )
                    log.info("Successfully created SeleniumBase UC driver with custom binary")
                except Exception as e:
                    log.warning(f"Failed to create driver with custom binary: {e}")
                    # Fall back to default
                    driver = Driver(
                        uc=True,
                        headless=headless,
                        page_load_strategy="normal"
                    )
                    log.info("Successfully created SeleniumBase UC driver with defaults")
            else:
                driver = Driver(
                    uc=True,
                    headless=headless,
                    page_load_strategy="normal"
                )
                log.info("Successfully created SeleniumBase UC driver")
        else:
            # Regular OS environment - SeleniumBase handles version matching automatically
            log.info("Creating SeleniumBase UC Mode driver")
            try:
                driver = Driver(
                    uc=True,
                    headless=headless,
                    page_load_strategy="normal",
                    incognito=True  # Use incognito mode for better stealth
                )
                log.info("Successfully created SeleniumBase UC driver")
            except Exception as e:
                log.error(f"Failed to create SeleniumBase driver: {e}")
                raise

        # Set page load timeout to avoid hanging
        driver.set_page_load_timeout(30)

        # Set window size
        driver.set_window_size(1400, 900)

        # Add additional stealth settings and Google Maps login-state bypass
        try:
            driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': '''
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                    Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                    Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
                '''
            })
            log.info("Additional stealth settings applied")
        except Exception as e:
            log.debug(f"Could not apply additional stealth settings: {e}")

        log.info("SeleniumBase UC driver setup completed successfully")
        return driver

    def dismiss_cookies(self, driver: Chrome):
        """
        Dismiss cookie consent dialogs if present.
        Handles stale element references by re-finding elements if needed.
        """
        try:
            # Use WebDriverWait with expected_conditions to handle stale elements
            WebDriverWait(driver, 3).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, COOKIE_BTN))
            )
            log.info("Cookie consent dialog found, attempting to dismiss")

            # Get elements again after waiting to avoid stale references
            elements = driver.find_elements(By.CSS_SELECTOR, COOKIE_BTN)
            for elem in elements:
                try:
                    if elem.is_displayed():
                        elem.click()
                        log.info("Cookie dialog dismissed")
                        return True
                except Exception as e:
                    log.debug(f"Error clicking cookie button: {e}")
                    continue
        except TimeoutException:
            # This is expected if no cookie dialog is present
            log.debug("No cookie consent dialog detected")
        except Exception as e:
            log.debug(f"Error handling cookie dialog: {e}")

        return False

    def _extract_place_name(self, driver: Chrome, url: str) -> str:
        """
        Extract the place name from a Google Maps URL.
        Tries URL decoding first, then falls back to loading the page.
        """
        import urllib.parse

        # Try to extract from URL path (e.g. /maps/place/PLACE+NAME/...)
        match = re.search(r'/maps/place/([^/@]+)', url)
        if match:
            name = urllib.parse.unquote(match.group(1))
            # Remove Unicode control characters
            name = re.sub(r'[\u200e\u200f\u202a-\u202e]', '', name)
            if len(name) > 2:
                log.info(f"Extracted place name from URL: '{name}'")
                return name

        # If the URL is a shortened URL or we couldn't parse the name,
        # load it briefly to get the title
        try:
            driver.get(url)
            time.sleep(4)
            # Get the page title - usually "Place Name - Google Maps"
            title = driver.title or ""
            name = title.replace(" - Google Maps", "").strip()
            name = re.sub(r'[\u200e\u200f\u202a-\u202e]', '', name)
            if name:
                log.info(f"Extracted place name from page title: '{name}'")
                return name
        except Exception as e:
            log.debug(f"Could not extract place name from page: {e}")

        return ""

    def _extract_place_coords(self, url: str) -> tuple:
        """Extract lat/lng coordinates from a Google Maps URL."""
        match = re.search(r'@(-?[\d.]+),(-?[\d.]+)', url)
        if match:
            return match.group(1), match.group(2)
        match = re.search(r'!3d(-?[\d.]+)!4d(-?[\d.]+)', url)
        if match:
            return match.group(1), match.group(2)
        return None, None

    def navigate_to_place(self, driver: Chrome, url: str, wait: WebDriverWait) -> bool:
        """
        Navigate to a Google Maps place, bypassing the 'limited view' restriction
        that Google shows to non-logged-in users.

        Strategy:
        1. Warm up by visiting google.com to establish cookies/session state
        2. Use Google Maps search-based navigation (avoids limited view)
        3. Fall back to direct URL if search doesn't work
        """
        log.info("Navigating to place with limited-view bypass...")

        # Step 1: Warm up - visit google.com first to establish session cookies
        try:
            driver.get("https://www.google.com")
            time.sleep(2)
            self.dismiss_cookies(driver)
            log.info("Session warm-up completed")
        except Exception as e:
            log.debug(f"Warm-up navigation failed: {e}")

        # Step 2: Resolve the target URL and extract place name
        place_name = self._extract_place_name(driver, url)
        current_url = driver.current_url

        # Step 3: Try search-based navigation (primary bypass method)
        if place_name:
            # Extract coordinates for more precise search
            lat, lng = self._extract_place_coords(current_url)
            search_query = place_name
            if lat and lng:
                search_url = f"https://www.google.com/maps/search/{search_query}/@{lat},{lng},17z"
            else:
                search_url = f"https://www.google.com/maps/search/{search_query}/"

            log.info(f"Trying search-based navigation: {search_url}")
            driver.get(search_url)
            time.sleep(5)

            # Check if we landed on a place page with full content (tabs visible)
            tabs = driver.find_elements(By.CSS_SELECTOR, '[role="tab"]')
            has_reviews = any(
                any(w in (t.text or "").lower() for w in REVIEW_WORDS)
                or t.get_attribute("data-tab-index") == "1"
                for t in tabs
            )

            if has_reviews:
                log.info("Search-based navigation successful - full page with reviews tab loaded")
                self.dismiss_cookies(driver)
                return True

            # Check for review cards directly (some layouts skip tabs)
            cards = driver.find_elements(By.CSS_SELECTOR, 'div[data-review-id]')
            if cards:
                log.info(f"Search-based navigation found {len(cards)} review cards")
                self.dismiss_cookies(driver)
                return True

            log.info("Search-based navigation did not show reviews, trying direct URL...")

        # Step 4: Fallback to direct URL
        log.info(f"Navigating directly to: {url}")
        driver.get(url)
        try:
            wait.until(lambda d: "google.com/maps" in d.current_url)
        except TimeoutException:
            log.warning("Timed out waiting for Google Maps to load")
        time.sleep(3)
        self.dismiss_cookies(driver)

        # Check if limited view is active
        try:
            body_text = driver.find_element(By.TAG_NAME, "body").text
            if "limited view" in body_text.lower():
                log.warning("Google Maps is showing 'limited view' - reviews may not be available")
        except Exception:
            pass

        return True

    def is_reviews_tab(self, tab: WebElement) -> bool:
        """
        Dynamically detect if an element is the reviews tab across multiple languages and layouts.
        Uses multiple detection approaches for maximum reliability.
        """
        try:
            # Strategy 1: Data attribute detection (most reliable across languages)
            tab_index = tab.get_attribute("data-tab-index")
            if tab_index == "1" or tab_index == "reviews":
                return True

            # Strategy 2: Role and aria attributes (accessibility detection)
            role = tab.get_attribute("role")
            aria_selected = tab.get_attribute("aria-selected")
            aria_label = (tab.get_attribute("aria-label") or "").lower()

            # Many review tabs have role="tab" and data attributes
            if role == "tab" and any(word in aria_label for word in REVIEW_WORDS):
                return True

            # Strategy 3: Text content detection (multiple sources)
            sources = [
                tab.text.lower() if tab.text else "",  # Direct text
                aria_label,  # ARIA label
                tab.get_attribute("innerHTML").lower() or "",  # Inner HTML
                tab.get_attribute("textContent").lower() or ""  # Text content
            ]

            # Check all sources against our comprehensive keyword list
            for source in sources:
                if any(word in source for word in REVIEW_WORDS):
                    return True

            # Strategy 4: Nested element detection
            try:
                # Check text in all child elements
                for child in tab.find_elements(By.CSS_SELECTOR, "*"):
                    try:
                        child_text = child.text.lower() if child.text else ""
                        child_content = child.get_attribute("textContent").lower() or ""

                        if any(word in child_text for word in REVIEW_WORDS) or any(
                                word in child_content for word in REVIEW_WORDS):
                            return True
                    except:
                        continue
            except:
                pass

            # Strategy 5: URL detection (some tabs have hrefs or data-hrefs with tell-tale values)
            for attr in ["href", "data-href", "data-url", "data-target"]:
                attr_value = (tab.get_attribute(attr) or "").lower()
                if attr_value and ("review" in attr_value or "rating" in attr_value):
                    return True

            # Strategy 6: Class detection (some review tabs have specific classes)
            tab_class = tab.get_attribute("class") or ""
            review_classes = ["review", "reviews", "rating", "ratings", "comments", "feedback", "g4jrve"]
            if any(cls in tab_class for cls in review_classes):
                return True

            return False

        except StaleElementReferenceException:
            return False
        except Exception as e:
            log.debug(f"Error in is_reviews_tab: {e}")
            return False

    def click_reviews_tab(self, driver: Chrome):
        """
        Highly dynamic reviews tab detection and clicking with multiple fallback strategies.
        Works across different languages, layouts, and browser environments.
        """
        max_timeout = 25  # Maximum seconds to try
        end_time = time.time() + max_timeout
        attempts = 0

        # Define different selectors to try in order of reliability
        tab_selectors = [
            # Direct tab selectors
            '[data-tab-index="1"]',  # Most common tab index
            '[role="tab"][data-tab-index]',  # Any tab with index
            'button[role="tab"]',  # Button tabs
            'div[role="tab"]',  # Div tabs
            'a[role="tab"]',  # Link tabs

            # Common Google Maps review tab selectors
            '.fontTitleSmall[role="tab"]',  # Google Maps title font tabs
            '.hh2c6[role="tab"]',  # Common Google Maps class
            '.m6QErb [role="tab"]',  # Maps container tabs

            # Text-based selectors for various languages
            'button:contains("reviews")',  # Button containing "reviews"
            'div[role="tablist"] > *',  # Any tab in a tab list
            'div.m6QErb div[role="tablist"] > *',  # Google Maps specific tablist
        ]

        # Record successful clicks for debugging
        successful_method = None
        successful_selector = None

        # Try each selector in turn
        for selector in tab_selectors:
            if time.time() > end_time:
                break

            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if not elements:
                    continue

                # Try each element found with this selector
                for element in elements:
                    attempts += 1

                    # First check if this is actually a reviews tab
                    if not self.is_reviews_tab(element):
                        continue

                    # Found a reviews tab, attempt to click it with multiple methods
                    log.info(f"Found potential reviews tab ({selector}): '{element.text}', attempting to click")

                    # Ensure visibility
                    driver.execute_script("arguments[0].scrollIntoView({block:'center', behavior:'smooth'});", element)
                    time.sleep(0.7)  # Wait for scroll

                    # Try different click methods in order of reliability
                    click_methods = [
                        # Method 1: JavaScript click (most reliable)
                        lambda: driver.execute_script("arguments[0].click();", element),

                        # Method 2: Direct click
                        lambda: element.click(),

                        # Method 3: ActionChains click
                        lambda: ActionChains(driver).move_to_element(element).click().perform(),

                        # Method 4: Send RETURN key
                        lambda: element.send_keys(Keys.RETURN),

                        # Method 5: Center click with ActionChains
                        lambda: ActionChains(driver).move_to_element_with_offset(
                            element, element.size['width'] // 2, element.size['height'] // 2).click().perform(),
                    ]

                    # Try each click method
                    for i, click_method in enumerate(click_methods):
                        try:
                            click_method()
                            time.sleep(1.5)  # Wait for click to take effect

                            # Verify if click worked (check for new content)
                            if self.verify_reviews_tab_clicked(driver):
                                successful_method = i + 1
                                successful_selector = selector
                                log.info(
                                    f"Successfully clicked reviews tab using method {i + 1} and selector '{selector}'")
                                return True
                        except Exception as click_error:
                            log.debug(f"Click method {i + 1} failed: {click_error}")
                            continue

            except Exception as selector_error:
                log.debug(f"Error with selector '{selector}': {selector_error}")
                continue

        # If we reach here, try XPath as a last resort
        if time.time() <= end_time:
            for language_keyword in REVIEW_WORDS:
                try:
                    # Try XPath contains text
                    xpath = f"//*[contains(text(), '{language_keyword}')]"
                    elements = driver.find_elements(By.XPATH, xpath)

                    for element in elements:
                        try:
                            log.info(f"Trying XPath with keyword '{language_keyword}'")
                            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", element)
                            time.sleep(0.7)
                            driver.execute_script("arguments[0].click();", element)
                            time.sleep(1.5)

                            if self.verify_reviews_tab_clicked(driver):
                                log.info(f"Successfully clicked element with keyword '{language_keyword}'")
                                return True
                        except:
                            continue
                except:
                    continue

        # Final attempt: try to navigate directly to reviews by URL
        try:
            current_url = driver.current_url
            if "?hl=" in current_url:  # Preserve language setting if present
                lang_param = re.search(r'\?hl=([^&]*)', current_url)
                if lang_param:
                    lang_code = lang_param.group(1)
                    # Try to replace the current part with 'reviews' or append it
                    if '/place/' in current_url:
                        parts = current_url.split('/place/')
                        new_url = f"{parts[0]}/place/{parts[1].split('/')[0]}/reviews?hl={lang_code}"
                        driver.get(new_url)
                        time.sleep(3)  # Increased wait time for page load
                        if "review" in driver.current_url.lower():
                            log.info("Navigated directly to reviews page via URL")
                            # Extra wait for reviews to render after URL navigation
                            time.sleep(2)
                            return True

            # Try to identify reviews link in URL
            if '/place/' in current_url and '/reviews' not in current_url:
                parts = current_url.split('/place/')
                new_url = f"{parts[0]}/place/{parts[1].split('/')[0]}/reviews"
                driver.get(new_url)
                time.sleep(3)  # Increased wait time for page load
                if "review" in driver.current_url.lower():
                    log.info("Navigated directly to reviews page via URL")
                    # Extra wait for reviews to render after URL navigation
                    time.sleep(2)
                    return True
        except Exception as url_error:
            log.warning(f"Failed to navigate to reviews via URL: {url_error}")

        log.warning(f"Failed to find/click reviews tab after {attempts} attempts")
        raise TimeoutException("Reviews tab not found or could not be clicked")

    def verify_reviews_tab_clicked(self, driver: Chrome) -> bool:
        """
        Verify that the reviews tab was successfully clicked by checking for
        characteristic elements that appear on the reviews page.
        """
        try:
            # Common elements that appear when reviews tab is active
            verification_selectors = [
                # Reviews container
                'div.m6QErb.DxyBCb.kA9KIf.dS8AEf',

                # Review cards
                'div[data-review-id]',

                # Sort button (usually appears with reviews)
                'button[aria-label*="Sort" i]',

                # Review rating elements
                'span[role="img"][aria-label*="star" i]',

                # Other indicators
                'div.m6QErb div.jftiEf',
                '.HlvSq'
            ]

            # Check if any verification selector is present
            for selector in verification_selectors:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements and len(elements) > 0:
                    return True

            # URL check - if "review" appears in the URL
            if "review" in driver.current_url.lower():
                return True

            return False
        except Exception as e:
            log.debug(f"Error verifying reviews tab click: {e}")
            return False

    def set_sort(self, driver: Chrome, method: str):
        """
        Set the sorting method for reviews with enhanced detection for the latest Google Maps UI.
        Works across different languages and UI variations, with robust error handling.
        """
        if method == "relevance":
            log.info("Using default 'relevance' sort - no need to change sort order")
            return True  # Default order, no need to change

        log.info(f"Attempting to set sort order to '{method}'")

        try:
            # 1. Find and click the sort button
            sort_button_selectors = [
                # Exact selectors based on recent HTML structure
                'button.HQzyZ[aria-haspopup="true"]',
                'div.m6QErb button.HQzyZ',
                'button[jsaction*="pane.wfvdle84"]',
                'div.fontBodyLarge.k5lwKb',  # The text element inside sort button

                # Common attribute-based selectors
                'button[aria-label*="Sort" i]',
                'button[aria-label*="sort" i]',
                'button[aria-expanded="false"][aria-haspopup="true"]',

                # Multilingual selectors
                'button[aria-label*="סדר" i]',  # Hebrew
                'button[aria-label*="เรียง" i]',  # Thai
                'button[aria-label*="排序" i]',  # Chinese
                'button[aria-label*="Trier" i]',  # French
                'button[aria-label*="Ordenar" i]',  # Spanish/Portuguese
                'button[aria-label*="Sortieren" i]',  # German

                # Parent container-based selectors
                'div.m6QErb.Hk4XGb.XiKgde.tLjsW button',
                'div.m6QErb div.XiKgde button'
            ]

            # Attempt to find the sort button
            sort_button = None

            # Try each selector
            for selector in sort_button_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        try:
                            # Skip invisible/disabled elements
                            if not element.is_displayed() or not element.is_enabled():
                                continue

                            # Get button text and attributes for verification
                            button_text = element.text.strip() if element.text else ""
                            button_aria = element.get_attribute("aria-label") or ""
                            button_class = element.get_attribute("class") or ""

                            # Skip buttons that are clearly not sort buttons
                            negative_keywords = ["back", "next", "previous", "close", "cancel", "חזרה", "סגור", "ปิด"]
                            if any(keyword in button_text.lower() or keyword in button_aria.lower()
                                   for keyword in negative_keywords):
                                continue

                            # Positive detection for sort buttons
                            sort_keywords = ["sort", "Sort", "SORT", "סידור", "เรียง", "排序", "trier", "ordenar", "sortieren"]
                            has_sort_keyword = any(keyword in button_text or keyword in button_aria 
                                                 for keyword in sort_keywords)
                            
                            # Check for common sort button classes
                            has_sort_class = "HQzyZ" in button_class or "sort" in button_class.lower()
                            
                            # Check for aria attributes that indicate a dropdown
                            has_dropdown_attrs = (element.get_attribute("aria-haspopup") == "true" or
                                                element.get_attribute("aria-expanded") is not None)

                            if has_sort_keyword or has_sort_class or has_dropdown_attrs:
                                # Found a potential sort button
                                sort_button = element
                                log.info(f"Found sort button with selector: {selector}")
                                log.info(f"Button text: '{button_text}', aria-label: '{button_aria}'")
                                break
                        except Exception as e:
                            log.debug(f"Error checking element: {e}")
                            continue

                    if sort_button:
                        break
                except Exception as e:
                    log.debug(f"Error with selector '{selector}': {e}")
                    continue

            # If no button found with CSS selectors, try finding it from its container
            if not sort_button:
                try:
                    # Look for the sort container by its distinctive classes
                    containers = driver.find_elements(By.CSS_SELECTOR, 'div.m6QErb.Hk4XGb, div.XiKgde.tLjsW')
                    for container in containers:
                        try:
                            # Find buttons within this container
                            buttons = container.find_elements(By.TAG_NAME, 'button')
                            for button in buttons:
                                if button.is_displayed() and button.is_enabled():
                                    sort_button = button
                                    log.info("Found sort button through container element")
                                    break
                        except:
                            continue
                        if sort_button:
                            break
                except Exception as e:
                    log.debug(f"Error finding button via container: {e}")

            # If still no button found, try XPath approach with keywords
            if not sort_button:
                xpath_terms = ["sort", "Sort", "סדר", "סידור", "เรียง", "排序", "Trier", "Ordenar", "Sortieren"]
                for term in xpath_terms:
                    try:
                        xpath = f"//*[contains(text(), '{term}') or contains(@aria-label, '{term}')]"
                        elements = driver.find_elements(By.XPATH, xpath)
                        for element in elements:
                            try:
                                if element.is_displayed() and element.is_enabled():
                                    sort_button = element
                                    log.info(f"Found sort button with XPath term: '{term}'")
                                    break
                            except:
                                continue
                        if sort_button:
                            break
                    except:
                        continue
            
            # Final fallback: look for any button in the reviews area that might open a dropdown
            if not sort_button:
                try:
                    # Look specifically in the reviews container area
                    reviews_container = driver.find_elements(By.CSS_SELECTOR, 'div.m6QErb, div.DxyBCb')
                    for container in reviews_container:
                        try:
                            # Find all buttons in this container
                            buttons = container.find_elements(By.TAG_NAME, 'button')
                            for button in buttons:
                                try:
                                    if (button.is_displayed() and button.is_enabled() and
                                        (button.get_attribute("aria-haspopup") == "true" or
                                         "dropdown" in (button.get_attribute("class") or "").lower())):
                                        sort_button = button
                                        log.info("Found potential sort button via fallback dropdown detection")
                                        break
                                except:
                                    continue
                            if sort_button:
                                break
                        except:
                            continue
                except Exception as e:
                    log.debug(f"Error in fallback sort button detection: {e}")

            # Final check - do we have a sort button?
            if not sort_button:
                log.warning("No sort button found with any method - keeping default sort order")
                return False

            # 2. Click the sort button to open dropdown menu

            # First ensure the button is in view
            driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", sort_button)
            time.sleep(0.8)  # Wait for scroll

            # Try multiple click methods
            click_methods = [
                # Method 1: JavaScript click
                lambda: driver.execute_script("arguments[0].click();", sort_button),

                # Method 2: Direct click
                lambda: sort_button.click(),

                # Method 3: ActionChains click with move first
                lambda: ActionChains(driver).move_to_element(sort_button).pause(0.3).click().perform(),

                # Method 4: Click on center of element
                lambda: ActionChains(driver).move_to_element_with_offset(
                    sort_button, sort_button.size['width'] // 2, sort_button.size['height'] // 2
                ).click().perform(),

                # Method 5: JavaScript focus and click
                lambda: driver.execute_script(
                    "arguments[0].focus(); setTimeout(function() { arguments[0].click(); }, 100);", sort_button
                ),

                # Method 6: Send RETURN key after focusing
                lambda: ActionChains(driver).move_to_element(sort_button).click().send_keys(Keys.RETURN).perform()
            ]

            # Try each click method
            menu_opened = False

            for i, click_method in enumerate(click_methods):
                try:
                    log.info(f"Trying click method {i + 1} for sort button...")
                    click_method()
                    time.sleep(1)  # Wait for menu to appear

                    # Check if menu opened
                    menu_opened = self.check_if_menu_opened(driver)

                    if menu_opened:
                        log.info(f"Sort menu opened with click method {i + 1}")
                        break
                except Exception as e:
                    log.debug(f"Click method {i + 1} failed: {e}")
                    continue

            # If menu not opened, abort
            if not menu_opened:
                log.warning("Failed to open sort menu - keeping default sort order")
                # Try to reset state by clicking elsewhere
                try:
                    ActionChains(driver).move_by_offset(50, 50).click().perform()
                except:
                    pass
                return False

            # 3. Find and click the desired sort option in the menu

            # Selectors for menu items with focus on the exact HTML structure
            menu_item_selectors = [
                # Exact Google Maps menu item selectors
                'div[role="menuitemradio"]',
                'div.fxNQSd[role="menuitemradio"]',
                'div[role="menuitemradio"] div.mLuXec',  # Inner text container

                # Generic menu item selectors (fallback)
                '[role="menuitemradio"]',
                '[role="menuitem"]',
                'div[role="menu"] > div'
            ]

            # Combined selector for efficiency
            combined_selector = ", ".join(menu_item_selectors)

            try:
                # Wait for menu items to appear
                menu_items = WebDriverWait(driver, 5).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, combined_selector))
                )

                # Process menu items to find matches
                visible_items = []

                for item in menu_items:
                    try:
                        # Skip invisible items
                        if not item.is_displayed():
                            continue

                        # Handle different element types
                        if item.get_attribute('role') == 'menuitemradio':
                            # This is a top-level menu item
                            try:
                                # Try to find text in the inner div.mLuXec element first
                                text_elements = item.find_elements(By.CSS_SELECTOR, 'div.mLuXec')
                                if text_elements and text_elements[0].is_displayed():
                                    text = text_elements[0].text.strip()
                                    visible_items.append((item, text))
                                else:
                                    # Fall back to the item's own text
                                    text = item.text.strip()
                                    visible_items.append((item, text))
                            except:
                                # Last resort - use the item's own text
                                text = item.text.strip()
                                visible_items.append((item, text))
                        elif 'mLuXec' in (item.get_attribute('class') or ''):
                            # This is the text container element - get its parent menuitemradio
                            try:
                                text = item.text.strip()
                                parent = driver.execute_script(
                                    "return arguments[0].closest('[role=\"menuitemradio\"]');",
                                    item
                                )
                                if parent:
                                    visible_items.append((parent, text))
                            except:
                                continue
                        else:
                            # Generic menu item handling
                            text = item.text.strip()
                            visible_items.append((item, text))
                    except Exception as e:
                        log.debug(f"Error processing menu item: {e}")
                        continue

                # Deduplicate: keep one entry per underlying DOM element,
                # skip container elements whose text spans multiple labels
                seen_elems = set()
                deduped = []
                for elem, text in visible_items:
                    eid = elem.id  # Selenium's internal element id (stable per session)
                    if eid in seen_elems or not text or "\n" in text:
                        continue
                    seen_elems.add(eid)
                    deduped.append((elem, text))
                visible_items = deduped

                log.info(f"Found {len(visible_items)} menu items: {[t for _, t in visible_items]}")

                # --- Strategy A: text-first matching (robust against reordering) ---
                target_item = None
                matched_text = None
                wanted_labels = [lbl.lower() for lbl in SORT_OPTIONS.get(method, [])]

                for item, text in visible_items:
                    if text.lower() in wanted_labels:
                        target_item = item
                        matched_text = text
                        log.info(f"Matched sort '{method}' by text: '{text}'")
                        break

                # --- Strategy B: position fallback (only if text match failed) ---
                if not target_item:
                    position_map = {
                        "relevance": 0,
                        "newest": 1,
                        "highest": 2,
                        "lowest": 3,
                    }
                    pos = position_map.get(method, -1)
                    if 0 <= pos < len(visible_items):
                        target_item, matched_text = visible_items[pos]
                        log.info(f"Position fallback {pos + 1}: '{matched_text}' for '{method}'")
                    else:
                        log.warning(f"Could not find sort '{method}' by text or position")

                # 3. If target found, click it
                if target_item:
                    # Ensure item is in view
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_item)
                    time.sleep(0.3)

                    # Try multiple click methods
                    click_success = False
                    click_methods = [
                        # Method 1: JavaScript click
                        lambda: driver.execute_script("arguments[0].click();", target_item),

                        # Method 2: Direct click
                        lambda: target_item.click(),

                        # Method 3: ActionChains click
                        lambda: ActionChains(driver).move_to_element(target_item).click().perform(),

                        # Method 4: Center click
                        lambda: ActionChains(driver).move_to_element_with_offset(
                            target_item, target_item.size['width'] // 2, target_item.size['height'] // 2
                        ).click().perform(),

                        # Method 5: JavaScript click with custom event
                        lambda: driver.execute_script("""
                            var el = arguments[0];
                            var evt = new MouseEvent('click', {
                                bubbles: true,
                                cancelable: true,
                                view: window
                            });
                            el.dispatchEvent(evt);
                        """, target_item)
                    ]

                    for i, click_method in enumerate(click_methods):
                        try:
                            click_method()
                            time.sleep(1.5)  # Wait for sort to take effect

                            # Try to verify sort happened by checking if menu closed
                            still_open = self.check_if_menu_opened(driver)
                            if not still_open:
                                click_success = True
                                log.info(f"Successfully clicked menu item with method {i + 1}")
                                break
                        except Exception as e:
                            log.debug(f"Menu item click method {i + 1} failed: {e}")
                            continue

                    if click_success:
                        # Validate: does the matched text belong to our wanted labels?
                        if matched_text and matched_text.lower() in wanted_labels:
                            log.info(f"Sort confirmed: '{method}'")
                            return True
                        log.warning(
                            f"Sort clicked '{matched_text}' but could not confirm it matches '{method}'"
                        )
                        return False
                    else:
                        log.warning(f"Failed to click menu item - keeping default sort order")
                else:
                    log.warning(f"No matching menu item found for '{method}'")

                # If we get here, we failed - try to close the menu by clicking elsewhere
                try:
                    ActionChains(driver).move_by_offset(50, 50).click().perform()
                except:
                    pass

                return False

            except TimeoutException:
                log.warning("Timeout waiting for menu items")
                return False
            except Exception as e:
                log.warning(f"Error in menu item selection: {e}")
                return False

        except Exception as e:
            log.warning(f"Error in set_sort method: {e}")
            return False

    def check_if_menu_opened(self, driver):
        """
        Check if a sort menu has been opened after clicking the sort button.
        Uses multiple detection strategies optimized for Google Maps dropdowns.
        Returns True if menu is detected, False otherwise.
        """
        try:
            # 1. First check for exact menu container selectors from the latest Google Maps UI
            specific_menu_selectors = [
                'div[role="menu"][id="action-menu"]',  # Exact match from provided HTML
                'div.fontBodyLarge.yu5kgd[role="menu"]',  # Classes from provided HTML
                'div.fxNQSd[role="menuitemradio"]',  # Menu item class
                'div.yu5kgd[role="menu"]'  # Alternate class
            ]

            for selector in specific_menu_selectors:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for element in elements:
                    try:
                        if element.is_displayed():
                            return True
                    except:
                        continue

            # 2. Check for generic menu containers
            generic_menu_selectors = [
                'div[role="menu"]',
                'ul[role="menu"]',
                '[role="listbox"]'
            ]

            for selector in generic_menu_selectors:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for element in elements:
                    try:
                        if element.is_displayed():
                            return True
                    except:
                        continue

            # 3. Look for menu items
            menu_item_selectors = [
                'div[role="menuitemradio"]',  # Google Maps specific
                'div.fxNQSd',  # Class-based detection
                'div.mLuXec',  # Text container class
                '[role="menuitem"]',  # Generic menu items
                '[role="option"]'  # Alternative role
            ]

            visible_items = 0
            for selector in menu_item_selectors:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for element in elements:
                    try:
                        if element.is_displayed():
                            visible_items += 1
                            if visible_items >= 2:  # At least 2 menu items should be visible
                                return True
                    except:
                        continue

            # 4. Advanced detection with JavaScript
            # Checks if there are newly visible elements with menu-related roles or classes
            try:
                js_detection = """
                return (function() {
                    // Check for visible menu elements
                    var menuElements = document.querySelectorAll('div[role="menu"], div[role="menuitemradio"], div.fxNQSd');
                    for (var i = 0; i < menuElements.length; i++) {
                        var style = window.getComputedStyle(menuElements[i]);
                        if (style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0') {
                            return true;
                        }
                    }

                    // Check for any recently appeared elements that might be a menu
                    var possibleMenus = document.querySelectorAll('div.yu5kgd, div.fontBodyLarge');
                    for (var i = 0; i < possibleMenus.length; i++) {
                        var style = window.getComputedStyle(possibleMenus[i]);
                        var rect = possibleMenus[i].getBoundingClientRect();
                        // Check if element is visible and has a meaningful size
                        if (style.display !== 'none' && style.visibility !== 'hidden' && 
                            rect.width > 50 && rect.height > 50) {
                            return true;
                        }
                    }

                    return false;
                })();
                """
                menu_detected = driver.execute_script(js_detection)
                if menu_detected:
                    return True
            except Exception as js_error:
                log.debug(f"Error in JavaScript menu detection: {js_error}")

            # 5. Last resort: check if any positioning styles were applied to elements
            # This can detect menu containers that have been positioned absolutely
            try:
                position_check = """
                return (function() {
                    // Look for absolutely positioned elements that appeared recently
                    var elements = document.querySelectorAll('div[style*="position: absolute"]');
                    for (var i = 0; i < elements.length; i++) {
                        var el = elements[i];
                        var style = window.getComputedStyle(el);
                        var hasMenuItems = el.querySelectorAll('div[role="menuitemradio"], div.fxNQSd').length > 0;

                        if (style.display !== 'none' && style.visibility !== 'hidden' && hasMenuItems) {
                            return true;
                        }
                    }
                    return false;
                })();
                """
                position_detected = driver.execute_script(position_check)
                if position_detected:
                    return True
            except:
                pass

            return False

        except Exception as e:
            log.debug(f"Error checking menu state: {e}")
            return False

    def scrape(self):
        """Main scraper method"""
        start_time = time.time()

        url = self.config.get("url")
        headless = self.config.get("headless", True)
        sort_by = self.config.get("sort_by", "relevance")
        stop_threshold = self.config.get("stop_threshold", 3)
        max_reviews = self.config.get("max_reviews", 0)
        max_scroll_attempts = self.config.get("max_scroll_attempts", 50)
        scroll_idle_limit = self.config.get("scroll_idle_limit", 15)

        log.info(f"Starting scraper with settings: headless={headless}, sort_by={sort_by}")
        log.info(f"URL: {url}")

        place_id = None
        session_id = None
        batch_stats = {"new": 0, "updated": 0, "restored": 0, "unchanged": 0}
        changed_ids = set()  # Track IDs that actually changed for efficient sync

        driver = None
        try:
            driver = self.setup_driver(headless)
            wait = WebDriverWait(driver, 20)  # Reduced from 40 to 20 for faster timeout

            # Navigate using limited-view bypass (search-based navigation)
            self.navigate_to_place(driver, url, wait)

            # Extract place ID and register in database
            resolved_url = driver.current_url
            place_name = ""
            try:
                title = driver.title or ""
                place_name = title.replace(" - Google Maps", "").strip()
            except Exception:
                pass
            place_id = extract_place_id(url, resolved_url)
            lat, lng = self._extract_place_coords(resolved_url)
            lat_f = float(lat) if lat else None
            lng_f = float(lng) if lng else None
            place_id = self.review_db.upsert_place(
                place_id, place_name, url, resolved_url, lat_f, lng_f
            )
            session_id = self.review_db.start_session(place_id, sort_by)
            log.info(f"Registered place: {place_id} ({place_name})")

            # Load seen IDs from DB (empty for full mode to re-process everything)
            if self.scrape_mode == "full":
                seen = set()
            else:
                seen = self.review_db.get_review_ids(place_id)

            self.dismiss_cookies(driver)
            self.click_reviews_tab(driver)

            # Extra wait after clicking reviews tab to ensure page loads
            log.info("Waiting for reviews page to fully load...")
            time.sleep(3)

            # Wait for page to be fully interactive
            try:
                wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
                log.info("Page DOM is ready")
            except:
                log.debug("Could not verify page ready state")

            # Verify we're on a reviews page before proceeding
            if "review" not in driver.current_url.lower():
                log.warning("URL doesn't contain 'review' - might not be on reviews page")

            # Try to set sort - but don't fail if it doesn't work
            sort_ok = False
            try:
                sort_ok = bool(self.set_sort(driver, sort_by))
            except Exception as sort_error:
                log.warning(f"Sort failed but continuing: {sort_error}")

            # Early-stop only makes sense when reviews are sorted by newest.
            # If sort failed or sort_by isn't "newest", disable it.
            if stop_threshold > 0 and (not sort_ok or sort_by != "newest"):
                log.warning(
                    "Disabling early stop (stop_threshold=%d) — "
                    "reviews are not confirmed sorted by newest",
                    stop_threshold,
                )
                stop_threshold = 0

            # Add a longer wait after setting sort to allow results to load
            log.info("Waiting for reviews to render...")
            time.sleep(3)

            # Use try-except to handle cases where the pane is not found
            # Try multiple selectors for the reviews pane
            pane = None
            pane_selectors = [
                PANE_SEL,  # Primary selector
                'div[role="main"] div.m6QErb',  # Simplified version
                'div.m6QErb.DxyBCb',  # Even more simplified
                'div[role="main"]'  # Most generic
            ]

            for selector in pane_selectors:
                try:
                    log.info(f"Trying to find reviews pane with selector: {selector}")
                    pane = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                    if pane:
                        log.info(f"Found reviews pane with selector: {selector}")
                        break
                except TimeoutException:
                    log.debug(f"Pane not found with selector: {selector}")
                    continue

            if not pane:
                log.warning("Could not find reviews pane with any selector. Page structure might have changed.")
                return False

            progress = Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}"),
                BarColumn(),
                MofNCompleteColumn(),
                transient=False,
            )
            progress.start()
            task_id = progress.add_task("Scraped", total=None, completed=len(seen))
            idle = 0
            processed_ids = set()
            consecutive_matched_batches = 0

            # Prefetch selector to avoid repeated lookups
            try:
                driver.execute_script("window.scrollablePane = arguments[0];", pane)
                scroll_script = "window.scrollablePane.scrollBy(0, window.scrollablePane.scrollHeight);"
            except Exception as e:
                log.warning(f"Error setting up scroll script: {e}")
                scroll_script = "window.scrollBy(0, 300);"  # Fallback to simple scrolling

            max_attempts = max_scroll_attempts
            attempts = 0
            max_idle = scroll_idle_limit
            consecutive_no_cards = 0  # Track how many times we find zero cards
            last_scroll_position = 0
            scroll_stuck_count = 0

            while attempts < max_attempts:
                if self.cancel_event.is_set():
                    log.info("Scrape cancelled by user request")
                    raise InterruptedError("Scrape cancelled")

                try:
                    cards = pane.find_elements(By.CSS_SELECTOR, CARD_SEL)
                    fresh_cards: List[WebElement] = []

                    # Check for valid cards
                    if len(cards) == 0:
                        consecutive_no_cards += 1
                        log.info(f"No review cards found in this iteration (consecutive: {consecutive_no_cards})")

                        # If we keep finding no cards, might have hit the end
                        if consecutive_no_cards > 5:
                            log.warning("No cards found for 5+ iterations - might be at end of reviews")
                            break

                        attempts += 1
                        # Try aggressive scrolling
                        driver.execute_script(scroll_script)
                        time.sleep(1)
                        driver.execute_script("window.scrollBy(0, 1000);")  # Extra scroll
                        time.sleep(1.5)
                        continue
                    else:
                        consecutive_no_cards = 0  # Reset counter when we find cards

                    batch_seen_count = 0  # Cards already in DB (for batch stop)
                    for c in cards:
                        try:
                            cid = c.get_attribute("data-review-id")
                            if not cid or cid in processed_ids:
                                continue
                            processed_ids.add(cid)
                            if cid in seen:
                                batch_seen_count += 1
                                continue
                            fresh_cards.append(c)
                        except StaleElementReferenceException:
                            continue
                        except Exception as e:
                            log.debug(f"Error getting review ID: {e}")
                            continue

                    batch_total = len(fresh_cards) + batch_seen_count
                    batch_unchanged = batch_seen_count

                    for card in fresh_cards:
                        try:
                            raw = RawReview.from_card(card)
                        except StaleElementReferenceException:
                            continue
                        except Exception:
                            log.warning("parse error - storing stub\n%s",
                                        traceback.format_exc(limit=1).strip())
                            try:
                                raw_id = card.get_attribute("data-review-id") or ""
                                raw = RawReview(id=raw_id, text="", lang="und")
                            except StaleElementReferenceException:
                                continue

                        review_dict = {
                            "review_id": raw.id,
                            "text": raw.text,
                            "rating": raw.rating,
                            "likes": raw.likes,
                            "lang": raw.lang,
                            "date": raw.date,
                            "review_date": raw.review_date,
                            "author": raw.author,
                            "profile": raw.profile,
                            "avatar": raw.avatar,
                            "owner_text": raw.owner_text,
                            "photos": raw.photos,
                        }
                        result = self.review_db.upsert_review(
                            place_id, review_dict, session_id,
                            scrape_mode=self.scrape_mode,
                        )
                        batch_stats[result] = batch_stats.get(result, 0) + 1
                        if result != "unchanged":
                            changed_ids.add(raw.id)
                        if result == "unchanged":
                            batch_unchanged += 1
                        seen.add(raw.id)
                        progress.advance(task_id)
                        idle = 0
                        attempts = 0

                        if max_reviews > 0 and len(seen) >= max_reviews:
                            log.info("Reached max_reviews limit (%d), stopping.", max_reviews)
                            idle = 999
                            break

                    # Batch-level stop: entire scroll iteration was unchanged.
                    # Require min 3 reviews in the batch to avoid false stops
                    # from tiny tail batches during lazy loading.
                    if stop_threshold > 0 and batch_total >= 3:
                        if batch_unchanged == batch_total:
                            consecutive_matched_batches += 1
                            log.info("Fully matched batch %d/%d (%d reviews)",
                                     consecutive_matched_batches, stop_threshold, batch_total)
                            if consecutive_matched_batches >= stop_threshold:
                                log.info("Stopping: %d consecutive fully-matched batches",
                                         stop_threshold)
                                idle = 999
                        else:
                            consecutive_matched_batches = 0

                    if idle >= max_idle:
                        log.info(f"Stopping: No new reviews found after {max_idle} scroll attempts")
                        break

                    if not fresh_cards:
                        idle += 1
                        attempts += 1
                        log.info(f"No new reviews in this iteration (idle: {idle}/{max_idle}, attempts: {attempts}/{max_attempts}, total seen: {len(seen)})")

                        # When no new reviews, scroll more aggressively
                        try:
                            # Try multiple scroll methods
                            driver.execute_script(scroll_script)
                            time.sleep(0.5)
                            driver.execute_script("window.scrollBy(0, 500);")  # Extra scroll
                            time.sleep(0.5)
                        except Exception as e:
                            log.warning(f"Error scrolling: {e}")
                    else:
                        log.info(f"Found {len(fresh_cards)} new reviews in this iteration")

                    # Check if we're actually scrolling or stuck
                    try:
                        current_scroll = driver.execute_script("return arguments[0].scrollTop;", pane)
                        if current_scroll == last_scroll_position and len(fresh_cards) == 0:
                            scroll_stuck_count += 1
                            log.warning(f"Scroll position hasn't changed (stuck at {current_scroll}px, stuck count: {scroll_stuck_count})")

                            if scroll_stuck_count > 5:
                                log.warning("Scroll is stuck - trying alternative scroll method")
                                # Try clicking the last visible review to force loading
                                try:
                                    driver.execute_script("arguments[0].lastElementChild.scrollIntoView();", pane)
                                    time.sleep(2)
                                except:
                                    pass
                                scroll_stuck_count = 0
                        else:
                            scroll_stuck_count = 0
                            last_scroll_position = current_scroll
                    except:
                        pass

                    # Use JavaScript for smoother scrolling
                    try:
                        driver.execute_script(scroll_script)
                    except Exception as e:
                        log.warning(f"Error scrolling: {e}")
                        # Try a simpler scroll method
                        driver.execute_script("window.scrollBy(0, 300);")

                    # Dynamic sleep: sleep less when processing many reviews, more when finding none
                    if len(fresh_cards) > 5:
                        sleep_time = 0.7
                    elif len(fresh_cards) == 0:
                        sleep_time = 2.0  # Wait longer when finding nothing (let page load)
                    else:
                        sleep_time = 1.0
                    time.sleep(sleep_time)

                except StaleElementReferenceException:
                    # The pane or other element went stale, try to re-find
                    log.debug("Stale element encountered, re-finding elements")
                    try:
                        pane = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, PANE_SEL)))
                        driver.execute_script("window.scrollablePane = arguments[0];", pane)
                    except Exception:
                        log.warning("Could not re-find reviews pane after stale element")
                        break
                except Exception as e:
                    log.warning(f"Error during review processing: {e}")
                    attempts += 1
                    time.sleep(1)

            progress.stop()

            # End session with stats
            total_found = sum(batch_stats.values())
            if session_id:
                self.review_db.end_session(
                    session_id, "completed",
                    reviews_found=total_found,
                    reviews_new=batch_stats.get("new", 0),
                    reviews_updated=(
                        batch_stats.get("updated", 0)
                        + batch_stats.get("restored", 0)
                    ),
                )

            # Post-scrape pipeline: process once, write to all targets
            reviews = self.review_db.get_reviews(place_id) if place_id else []
            if reviews:
                legacy_docs = {
                    r["review_id"]: self._db_review_to_legacy(r) for r in reviews
                }
                runner = PostScrapeRunner(self.config)
                try:
                    runner.run(legacy_docs, place_id, seen=seen)
                finally:
                    runner.close()

            log.info(
                "Finished - new: %d, updated: %d, restored: %d, unchanged: %d",
                batch_stats["new"], batch_stats["updated"],
                batch_stats["restored"], batch_stats["unchanged"],
            )
            log.info("Total unique reviews in DB: %d", len(reviews))

            end_time = time.time()
            elapsed_time = end_time - start_time
            log.info(f"Execution completed in {elapsed_time:.2f} seconds")

            return True

        except Exception as e:
            if session_id:
                self.review_db.end_session(session_id, "failed", error=str(e))
            log.error(f"Error during scraping: {e}")
            log.error(traceback.format_exc())
            return False

        finally:
            if driver is not None:
                try:
                    driver.quit()
                except Exception:
                    pass

# """
# Selenium scraping logic for Google Maps Reviews.
# """
#
# import os
# import time
# import logging
# import traceback
# import platform
# from typing import Dict, Any, List
#
# import undetected_chromedriver as uc
# from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
# from selenium.webdriver import Chrome
# from selenium.webdriver.common.by import By
# from selenium.webdriver.remote.webelement import WebElement
# from selenium.webdriver.support import expected_conditions as EC
# from selenium.webdriver.support.ui import WebDriverWait
# from tqdm import tqdm
#
# from modules.models import RawReview
# from modules.data_storage import MongoDBStorage, JSONStorage, merge_review
#
# # Logger
# log = logging.getLogger("scraper")
#
# # CSS Selectors
# PANE_SEL = 'div[role="main"] div.m6QErb.DxyBCb.kA9KIf.dS8AEf'
# CARD_SEL = "div[data-review-id]"
# COOKIE_BTN = ('button[aria-label*="Accept" i],'
#               'button[jsname="hZCF7e"],'
#               'button[data-mdc-dialog-action="accept"]')
# SORT_BTN = 'button[aria-label="Sort reviews" i], button[aria-label="Sort" i]'
# MENU_ITEMS = 'div[role="menu"] [role="menuitem"], li[role="menuitem"]'
#
# SORT_LABELS = {  # text shown in Google Maps' menu
#     "newest": ("Newest", "החדשות ביותר", "ใหม่ที่สุด"),
#     "highest": ("Highest rating", "הדירוג הגבוה ביותר", "คะแนนสูงสุด"),
#     "lowest": ("Lowest rating", "הדירוג הנמוך ביותר", "คะแนนต่ำสุด"),
#     "relevance": ("Most relevant", "רלוונטיות ביותר", "เกี่ยวข้องมากที่สุด"),
# }
#
# REVIEW_WORDS = {"reviews", "review", "ביקורות", "รีวิว", "avis", "reseñas",
#                 "recensioni", "bewertungen", "口コミ", "レビュー",
#                 "리뷰", "評論", "评论", "рецензии", "ביקורת"}
#
#
# class GoogleReviewsScraper:
#     """Main scraper class for Google Maps reviews"""
#
#     def __init__(self, config: Dict[str, Any]):
#         """Initialize scraper with configuration"""
#         self.config = config
#         self.use_mongodb = config.get("use_mongodb", True)
#         self.mongodb = MongoDBStorage(config) if self.use_mongodb else None
#         self.json_storage = JSONStorage(config)
#         self.backup_to_json = config.get("backup_to_json", True)
#         self.overwrite_existing = config.get("overwrite_existing", False)
#
#     def setup_driver(self, headless: bool) -> Chrome:
#         """
#         Set up and configure Chrome driver with flexibility for different environments.
#         Works in both Docker containers and on regular OS installations (Windows, Mac, Linux).
#         """
#         # Determine if we're running in a container
#         in_container = os.environ.get('CHROME_BIN') is not None
#
#         # Create Chrome options
#         opts = uc.ChromeOptions()
#         opts.add_argument("--window-size=1400,900")
#         opts.add_argument("--ignore-certificate-errors")
#         opts.add_argument("--disable-gpu")  # Improves performance
#         opts.add_argument("--disable-dev-shm-usage")  # Helps with stability
#         opts.add_argument("--no-sandbox")  # More stable in some environments
#
#         # Use headless mode if requested
#         if headless:
#             opts.add_argument("--headless=new")
#
#         # Log platform information for debugging
#         log.info(f"Platform: {platform.platform()}")
#         log.info(f"Python version: {platform.python_version()}")
#
#         # If in container, use environment-provided binaries
#         if in_container:
#             chrome_binary = os.environ.get('CHROME_BIN')
#             chromedriver_path = os.environ.get('CHROMEDRIVER_PATH')
#
#             log.info(f"Container environment detected")
#             log.info(f"Chrome binary: {chrome_binary}")
#             log.info(f"ChromeDriver path: {chromedriver_path}")
#
#             if chrome_binary and os.path.exists(chrome_binary):
#                 log.info(f"Using Chrome binary from environment: {chrome_binary}")
#                 opts.binary_location = chrome_binary
#
#             try:
#                 # Try creating Chrome driver with undetected_chromedriver
#                 log.info("Attempting to create undetected_chromedriver instance")
#                 driver = uc.Chrome(options=opts)
#                 log.info("Successfully created undetected_chromedriver instance")
#             except Exception as e:
#                 # Fall back to regular Selenium if undetected_chromedriver fails
#                 log.warning(f"Failed to create undetected_chromedriver instance: {e}")
#                 log.info("Falling back to regular Selenium Chrome")
#
#                 # Import Selenium webdriver here to avoid potential import issues
#                 from selenium import webdriver
#                 from selenium.webdriver.chrome.service import Service
#
#                 if chromedriver_path and os.path.exists(chromedriver_path):
#                     log.info(f"Using ChromeDriver from path: {chromedriver_path}")
#                     service = Service(executable_path=chromedriver_path)
#                     driver = webdriver.Chrome(service=service, options=opts)
#                 else:
#                     log.info("Using default ChromeDriver")
#                     driver = webdriver.Chrome(options=opts)
#         else:
#             # On regular OS, use default undetected_chromedriver
#             log.info("Using standard undetected_chromedriver setup")
#             driver = uc.Chrome(options=opts)
#
#         # Set page load timeout to avoid hanging
#         driver.set_page_load_timeout(30)
#         log.info("Chrome driver setup completed successfully")
#         return driver
#
#     def dismiss_cookies(self, driver: Chrome):
#         """
#         Dismiss cookie consent dialogs if present.
#         Handles stale element references by re-finding elements if needed.
#         """
#         try:
#             # Use WebDriverWait with expected_conditions to handle stale elements
#             WebDriverWait(driver, 3).until(
#                 EC.presence_of_element_located((By.CSS_SELECTOR, COOKIE_BTN))
#             )
#             log.info("Cookie consent dialog found, attempting to dismiss")
#
#             # Get elements again after waiting to avoid stale references
#             elements = driver.find_elements(By.CSS_SELECTOR, COOKIE_BTN)
#             for elem in elements:
#                 try:
#                     if elem.is_displayed():
#                         elem.click()
#                         log.info("Cookie dialog dismissed")
#                         return True
#                 except Exception as e:
#                     log.debug(f"Error clicking cookie button: {e}")
#                     continue
#         except TimeoutException:
#             # This is expected if no cookie dialog is present
#             log.debug("No cookie consent dialog detected")
#         except Exception as e:
#             log.debug(f"Error handling cookie dialog: {e}")
#
#         return False
#
#     def is_reviews_tab(self, tab: WebElement) -> bool:
#         """Check if a tab is the reviews tab"""
#         try:
#             label = (tab.get_attribute("aria-label") or tab.text or "").lower()
#             return tab.get_attribute("data-tab-index") == "1" or any(w in label for w in REVIEW_WORDS)
#         except StaleElementReferenceException:
#             return False
#         except Exception as e:
#             log.debug(f"Error checking if tab is reviews tab: {e}")
#             return False
#
#     def click_reviews_tab(self, driver: Chrome):
#         """
#         Click on the reviews tab in Google Maps with improved stale element handling.
#         """
#         end = time.time() + 15  # Timeout after 15 seconds
#         while time.time() < end:
#             try:
#                 # Find all tab elements
#                 tabs = driver.find_elements(By.CSS_SELECTOR, '[role="tab"], button[aria-label]')
#
#                 for tab in tabs:
#                     try:
#                         # Check if this is the reviews tab
#                         label = (tab.get_attribute("aria-label") or tab.text or "").lower()
#                         is_review_tab = tab.get_attribute("data-tab-index") == "1" or any(
#                             w in label for w in REVIEW_WORDS)
#
#                         if is_review_tab:
#                             # Scroll the tab into view
#                             driver.execute_script("arguments[0].scrollIntoView({block:\"center\"});", tab)
#                             time.sleep(0.2)  # Small wait after scrolling
#
#                             # Try to click the tab
#                             log.info("Found reviews tab, attempting to click")
#                             tab.click()
#                             log.info("Successfully clicked reviews tab")
#                             return True
#                     except Exception as e:
#                         # Element might be stale or not clickable, try the next one
#                         log.debug(f"Error with tab element: {str(e)}")
#                         continue
#
#                 # If we get here, we didn't find a suitable tab in this iteration
#                 log.debug("No reviews tab found in this iteration, waiting...")
#                 time.sleep(0.5)  # Wait before next attempt
#
#             except Exception as e:
#                 # General exception handling
#                 log.debug(f"Exception while looking for reviews tab: {str(e)}")
#                 time.sleep(0.5)
#
#         # If we exit the loop, we've timed out
#         log.warning("Timeout while looking for reviews tab")
#         raise TimeoutException("Reviews tab not found")
#
#     def set_sort(self, driver: Chrome, method: str):
#         """
#         Set the sorting method for reviews with improved error handling.
#         """
#         if method == "relevance":
#             return True  # Default order, no need to change
#
#         log.info(f"Attempting to set sort order to '{method}'")
#
#         try:
#             # First try to find and click the sort button
#             sort_buttons = driver.find_elements(By.CSS_SELECTOR, SORT_BTN)
#             if not sort_buttons:
#                 log.warning(f"Sort button not found - keeping default sort order")
#                 return False
#
#             # Try to click the first visible sort button
#             for sort_button in sort_buttons:
#                 try:
#                     if sort_button.is_displayed() and sort_button.is_enabled():
#                         sort_button.click()
#                         log.info("Clicked sort button")
#                         time.sleep(0.5)  # Wait for menu to appear
#                         break
#                 except Exception as e:
#                     log.debug(f"Error clicking sort button: {e}")
#                     continue
#             else:
#                 log.warning("No clickable sort button found")
#                 return False
#
#             # Now find and click the menu item for the desired sort method
#             wanted = SORT_LABELS[method]
#             menu_items = WebDriverWait(driver, 3).until(
#                 EC.presence_of_all_elements_located((By.CSS_SELECTOR, MENU_ITEMS))
#             )
#
#             for item in menu_items:
#                 try:
#                     label = item.text.strip()
#                     if label in wanted:
#                         item.click()
#                         log.info(f"Selected sort option: {label}")
#                         time.sleep(0.5)  # Wait for sorting to take effect
#                         return True
#                 except Exception as e:
#                     log.debug(f"Error clicking menu item: {e}")
#                     continue
#
#             log.warning(f"Sort option '{method}' not found in menu - keeping default")
#             return False
#
#         except Exception as e:
#             log.warning(f"Error setting sort order: {e}")
#             return False
#
#     def scrape(self):
#         """Main scraper method"""
#         start_time = time.time()
#
#         url = self.config.get("url")
#         headless = self.config.get("headless", True)
#         sort_by = self.config.get("sort_by", "relevance")
#         stop_on_match = self.config.get("stop_on_match", False)
#
#         log.info(f"Starting scraper with settings: headless={headless}, sort_by={sort_by}")
#         log.info(f"URL: {url}")
#
#         # Initialize storage
#         # If not overwriting, load existing data
#         if self.overwrite_existing:
#             docs = {}
#             seen = set()
#         else:
#             # Try to get from MongoDB first if enabled
#             docs = {}
#             if self.use_mongodb and self.mongodb:
#                 docs = self.mongodb.fetch_existing_reviews()
#
#             # If backup_to_json is enabled, also load from JSON for merging
#             if self.backup_to_json:
#                 json_docs = self.json_storage.load_json_docs()
#                 # Merge JSON docs with MongoDB docs
#                 for review_id, review in json_docs.items():
#                     if review_id not in docs:
#                         docs[review_id] = review
#
#             # Load seen IDs from file
#             seen = self.json_storage.load_seen()
#
#         driver = None
#         try:
#             driver = self.setup_driver(headless)
#             wait = WebDriverWait(driver, 20)  # Reduced from 40 to 20 for faster timeout
#
#             driver.get(url)
#             wait.until(lambda d: "google.com/maps" in d.current_url)
#
#             self.dismiss_cookies(driver)
#             self.click_reviews_tab(driver)
#             self.set_sort(driver, sort_by)
#
#             # Add a wait after setting sort to allow results to load
#             time.sleep(1)
#
#             # Use try-except to handle cases where the pane is not found
#             try:
#                 pane = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, PANE_SEL)))
#             except TimeoutException:
#                 log.warning("Could not find reviews pane. Page structure might have changed.")
#                 return False
#
#             pbar = tqdm(desc="Scraped", ncols=80, initial=len(seen))
#             idle = 0
#             processed_ids = set()  # Track processed IDs in current session
#
#             # Prefetch selector to avoid repeated lookups
#             try:
#                 driver.execute_script("window.scrollablePane = arguments[0];", pane)
#                 scroll_script = "window.scrollablePane.scrollBy(0, window.scrollablePane.scrollHeight);"
#             except Exception as e:
#                 log.warning(f"Error setting up scroll script: {e}")
#                 scroll_script = "window.scrollBy(0, 300);"  # Fallback to simple scrolling
#
#             max_attempts = 10  # Limit the number of attempts to find reviews
#             attempts = 0
#
#             while attempts < max_attempts:
#                 try:
#                     cards = pane.find_elements(By.CSS_SELECTOR, CARD_SEL)
#                     fresh_cards: List[WebElement] = []
#
#                     # Check for valid cards
#                     if len(cards) == 0:
#                         log.debug("No review cards found in this iteration")
#                         attempts += 1
#                         # Try scrolling anyway
#                         driver.execute_script(scroll_script)
#                         time.sleep(1)
#                         continue
#
#                     for c in cards:
#                         try:
#                             cid = c.get_attribute("data-review-id")
#                             if not cid or cid in seen or cid in processed_ids:
#                                 if stop_on_match and cid and (cid in seen or cid in processed_ids):
#                                     idle = 999
#                                     break
#                                 continue
#                             fresh_cards.append(c)
#                         except StaleElementReferenceException:
#                             continue
#                         except Exception as e:
#                             log.debug(f"Error getting review ID: {e}")
#                             continue
#
#                     for card in fresh_cards:
#                         try:
#                             raw = RawReview.from_card(card)
#                             processed_ids.add(raw.id)  # Track this ID to avoid re-processing
#                         except StaleElementReferenceException:
#                             continue
#                         except Exception:
#                             log.warning("⚠️ parse error – storing stub\n%s",
#                                         traceback.format_exc(limit=1).strip())
#                             try:
#                                 raw_id = card.get_attribute("data-review-id") or ""
#                                 raw = RawReview(id=raw_id, text="", lang="und")
#                                 processed_ids.add(raw_id)
#                             except StaleElementReferenceException:
#                                 continue
#
#                         docs[raw.id] = merge_review(docs.get(raw.id), raw)
#                         seen.add(raw.id)
#                         pbar.update(1)
#                         idle = 0
#                         attempts = 0  # Reset attempts counter when we successfully process a review
#
#                     if idle >= 3:
#                         break
#
#                     if not fresh_cards:
#                         idle += 1
#                         attempts += 1
#
#                     # Use JavaScript for smoother scrolling
#                     try:
#                         driver.execute_script(scroll_script)
#                     except Exception as e:
#                         log.warning(f"Error scrolling: {e}")
#                         # Try a simpler scroll method
#                         driver.execute_script("window.scrollBy(0, 300);")
#
#                     # Dynamic sleep: sleep less when processing many reviews
#                     sleep_time = 0.7 if len(fresh_cards) > 5 else 1.0
#                     time.sleep(sleep_time)
#
#                 except StaleElementReferenceException:
#                     # The pane or other element went stale, try to re-find
#                     log.debug("Stale element encountered, re-finding elements")
#                     try:
#                         pane = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, PANE_SEL)))
#                         driver.execute_script("window.scrollablePane = arguments[0];", pane)
#                     except Exception:
#                         log.warning("Could not re-find reviews pane after stale element")
#                         break
#                 except Exception as e:
#                     log.warning(f"Error during review processing: {e}")
#                     attempts += 1
#                     time.sleep(1)
#
#             pbar.close()
#
#             # Save to MongoDB if enabled
#             if self.use_mongodb and self.mongodb:
#                 log.info("Saving reviews to MongoDB...")
#                 self.mongodb.save_reviews(docs)
#
#             # Backup to JSON if enabled
#             if self.backup_to_json:
#                 log.info("Backing up to JSON...")
#                 self.json_storage.save_json_docs(docs)
#                 self.json_storage.save_seen(seen)
#
#             log.info("✅ Finished – total unique reviews: %s", len(docs))
#
#             end_time = time.time()
#             elapsed_time = end_time - start_time
#             log.info(f"Execution completed in {elapsed_time:.2f} seconds")
#
#             return True
#
#         except Exception as e:
#             log.error(f"Error during scraping: {e}")
#             log.error(traceback.format_exc())
#             return False
#
#         finally:
#             if driver is not None:
#                 try:
#                     driver.quit()
#                 except Exception:
#                     pass
#
#             if self.mongodb:
#                 try:
#                     self.mongodb.close()
#                 except Exception:
#                     pass
#
# # """
# # Selenium scraping logic for Google Maps Reviews.
# # """
# #
# # import re
# # import time
# # import logging
# # import traceback
# # from typing import Dict, Any, Set, List
# #
# # import undetected_chromedriver as uc
# # from selenium.common.exceptions import TimeoutException
# # from selenium.webdriver import Chrome
# # from selenium.webdriver.common.by import By
# # from selenium.webdriver.remote.webelement import WebElement
# # from selenium.webdriver.support import expected_conditions as EC
# # from selenium.webdriver.support.ui import WebDriverWait
# # from tqdm import tqdm
# #
# # from modules.models import RawReview
# # from modules.data_storage import MongoDBStorage, JSONStorage, merge_review
# # from modules.utils import click_if
# #
# # # Logger
# # log = logging.getLogger("scraper")
# #
# # # CSS Selectors
# # PANE_SEL = 'div[role="main"] div.m6QErb.DxyBCb.kA9KIf.dS8AEf'
# # CARD_SEL = "div[data-review-id]"
# # COOKIE_BTN = ('button[aria-label*="Accept" i],'
# #               'button[jsname="hZCF7e"],'
# #               'button[data-mdc-dialog-action="accept"]')
# # SORT_BTN = 'button[aria-label="Sort reviews" i], button[aria-label="Sort" i]'
# # MENU_ITEMS = 'div[role="menu"] [role="menuitem"], li[role="menuitem"]'
# #
# # SORT_LABELS = {  # text shown in Google Maps' menu
# #     "newest": ("Newest", "החדשות ביותר", "ใหม่ที่สุด"),
# #     "highest": ("Highest rating", "הדירוג הגבוה ביותר", "คะแนนสูงสุด"),
# #     "lowest": ("Lowest rating", "הדירוג הנמוך ביותר", "คะแนนต่ำสุด"),
# #     "relevance": ("Most relevant", "רלוונטיות ביותר", "เกี่ยวข้องมากที่สุด"),
# # }
# #
# # REVIEW_WORDS = {"reviews", "review", "ביקורות", "รีวิว", "avis", "reseñas",
# #                 "recensioni", "bewertungen", "口コミ", "レビュー",
# #                 "리뷰", "評論", "评论", "рецензии"}
# #
# #
# # class GoogleReviewsScraper:
# #     """Main scraper class for Google Maps reviews"""
# #
# #     def __init__(self, config: Dict[str, Any]):
# #         """Initialize scraper with configuration"""
# #         self.config = config
# #         self.use_mongodb = config.get("use_mongodb", True)
# #         self.mongodb = MongoDBStorage(config) if self.use_mongodb else None
# #         self.json_storage = JSONStorage(config)
# #         self.backup_to_json = config.get("backup_to_json", True)
# #         self.overwrite_existing = config.get("overwrite_existing", False)
# #
# #     def setup_driver(self, headless: bool) -> Chrome:
# #         """Set up and configure Chrome driver"""
# #         opts = uc.ChromeOptions()
# #         opts.add_argument("--window-size=1400,900")
# #         opts.add_argument("--ignore-certificate-errors")
# #         opts.add_argument("--disable-gpu")  # Improves performance
# #         opts.add_argument("--disable-dev-shm-usage")  # Helps with stability
# #         opts.add_argument("--no-sandbox")  # More stable in some environments
# #
# #         if headless:
# #             opts.add_argument("--headless=new")
# #
# #         driver = uc.Chrome(options=opts)
# #         # Set page load timeout to avoid hanging
# #         driver.set_page_load_timeout(30)
# #         return driver
# #
# #     def dismiss_cookies(self, driver: Chrome):
# #         """Dismiss cookie consent dialogs"""
# #         click_if(driver, COOKIE_BTN, timeout=3.0)  # Reduced timeout for faster operation
# #
# #     def is_reviews_tab(self, tab: WebElement) -> bool:
# #         """Check if a tab is the reviews tab"""
# #         label = (tab.get_attribute("aria-label") or tab.text or "").lower()
# #         return tab.get_attribute("data-tab-index") == "1" or any(w in label for w in REVIEW_WORDS)
# #
# #     def click_reviews_tab(self, driver: Chrome):
# #         """Click on the reviews tab in Google Maps"""
# #         end = time.time() + 15  # Reduced timeout from 30 to 15 seconds
# #         while time.time() < end:
# #             for tab in driver.find_elements(By.CSS_SELECTOR,
# #                                             '[role="tab"], button[aria-label]'):
# #                 if self.is_reviews_tab(tab):
# #                     driver.execute_script("arguments[0].scrollIntoView({block:\"center\"});", tab)
# #                     try:
# #                         tab.click()
# #                         return
# #                     except Exception:
# #                         continue
# #             time.sleep(.2)  # Reduced sleep time from 0.4 to 0.2
# #         raise TimeoutException("Reviews tab not found")
# #
# #     def set_sort(self, driver: Chrome, method: str):
# #         """Set the sorting method for reviews"""
# #         if method == "relevance":
# #             return  # default order
# #         if not click_if(driver, SORT_BTN):
# #             return
# #
# #         wanted = SORT_LABELS[method]
# #
# #         for item in driver.find_elements(By.CSS_SELECTOR, MENU_ITEMS):
# #             label = item.text.strip()
# #             if label in wanted:
# #                 item.click()
# #                 time.sleep(0.5)  # Reduced wait time from 1.0 to 0.5
# #                 return
# #         log.warning("⚠️  sort option %s not found – keeping default", method)
# #
# #     def scrape(self):
# #         """Main scraper method"""
# #         start_time = time.time()
# #
# #         url = self.config.get("url")
# #         headless = self.config.get("headless", True)
# #         sort_by = self.config.get("sort_by", "relevance")
# #         stop_on_match = self.config.get("stop_on_match", False)
# #
# #         log.info(f"Starting scraper with settings: headless={headless}, sort_by={sort_by}")
# #         log.info(f"URL: {url}")
# #
# #         # Initialize storage
# #         # If not overwriting, load existing data
# #         if self.overwrite_existing:
# #             docs = {}
# #             seen = set()
# #         else:
# #             # Try to get from MongoDB first if enabled
# #             docs = {}
# #             if self.use_mongodb and self.mongodb:
# #                 docs = self.mongodb.fetch_existing_reviews()
# #
# #             # If backup_to_json is enabled, also load from JSON for merging
# #             if self.backup_to_json:
# #                 json_docs = self.json_storage.load_json_docs()
# #                 # Merge JSON docs with MongoDB docs
# #                 for review_id, review in json_docs.items():
# #                     if review_id not in docs:
# #                         docs[review_id] = review
# #
# #             # Load seen IDs from file
# #             seen = self.json_storage.load_seen()
# #
# #         driver = self.setup_driver(headless)
# #         wait = WebDriverWait(driver, 20)  # Reduced from 40 to 20 for faster timeout
# #
# #         try:
# #             driver.get(url)
# #             wait.until(lambda d: "google.com/maps" in d.current_url)
# #
# #             self.dismiss_cookies(driver)
# #             self.click_reviews_tab(driver)
# #             self.set_sort(driver, sort_by)
# #
# #             pane = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, PANE_SEL)))
# #             pbar = tqdm(desc="Scraped", ncols=80, initial=len(seen))
# #             idle = 0
# #             processed_ids = set()  # Track processed IDs in current session
# #
# #             # Prefetch selector to avoid repeated lookups
# #             driver.execute_script("window.scrollablePane = arguments[0];", pane)
# #             scroll_script = "window.scrollablePane.scrollBy(0, window.scrollablePane.scrollHeight);"
# #
# #             while True:
# #                 cards = pane.find_elements(By.CSS_SELECTOR, CARD_SEL)
# #                 fresh_cards: List[WebElement] = []
# #
# #                 for c in cards:
# #                     cid = c.get_attribute("data-review-id")
# #                     if cid in seen or cid in processed_ids:
# #                         if stop_on_match:
# #                             idle = 999
# #                             break
# #                         continue
# #                     fresh_cards.append(c)
# #
# #                 for card in fresh_cards:
# #                     try:
# #                         raw = RawReview.from_card(card)
# #                         processed_ids.add(raw.id)  # Track this ID to avoid re-processing
# #                     except Exception:
# #                         log.warning("⚠️ parse error – storing stub\n%s",
# #                                     traceback.format_exc(limit=1).strip())
# #                         raw_id = card.get_attribute("data-review-id") or ""
# #                         raw = RawReview(id=raw_id, text="", lang="und")
# #                         processed_ids.add(raw_id)
# #
# #                     docs[raw.id] = merge_review(docs.get(raw.id), raw)
# #                     seen.add(raw.id)
# #                     pbar.update(1)
# #                     idle = 0
# #
# #                 if idle >= 3:
# #                     break
# #
# #                 if not fresh_cards:
# #                     idle += 1
# #
# #                 # Use JavaScript for smoother scrolling
# #                 driver.execute_script(scroll_script)
# #
# #                 # Dynamic sleep: sleep less when processing many reviews
# #                 sleep_time = 0.7 if len(fresh_cards) > 5 else 1.0
# #                 time.sleep(sleep_time)
# #
# #             pbar.close()
# #
# #             # Save to MongoDB if enabled
# #             if self.use_mongodb and self.mongodb:
# #                 log.info("Saving reviews to MongoDB...")
# #                 self.mongodb.save_reviews(docs)
# #
# #             # Backup to JSON if enabled
# #             if self.backup_to_json:
# #                 log.info("Backing up to JSON...")
# #                 self.json_storage.save_json_docs(docs)
# #                 self.json_storage.save_seen(seen)
# #
# #             log.info("✅ Finished – total unique reviews: %s", len(docs))
# #
# #             end_time = time.time()
# #             elapsed_time = end_time - start_time
# #             log.info(f"Execution completed in {elapsed_time:.2f} seconds")
# #
# #         finally:
# #             driver.quit()
# #             if self.mongodb:
# #                 self.mongodb.close()
