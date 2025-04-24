"""
Data models for Google Maps Reviews Scraper.
"""
import re
from dataclasses import dataclass, field

from selenium.webdriver.remote.webelement import WebElement

from modules.utils import (try_find, first_text, first_attr, safe_int, detect_lang, parse_date_to_iso)


@dataclass
class RawReview:
    """
    Data class representing a raw review extracted from Google Maps.
    """
    id: str = ""
    author: str = ""
    rating: float = 0.0
    date: str = ""
    lang: str = "und"
    text: str = ""
    likes: int = 0
    photos: list[str] = field(default_factory=list)
    profile: str = ""
    avatar: str = ""  # URL to profile picture
    owner_date: str = ""
    owner_text: str = ""
    review_date: str = ""  # ISO format date

    # CSS Selectors for review elements
    MORE_BTN = "button.kyuRq"
    LIKE_BTN = 'button[jsaction*="toggleThumbsUp" i]'
    PHOTO_BTN = "button.Tya61d"
    OWNER_RESP = "div.CDe7pd"

    @classmethod
    def from_card(cls, card: WebElement) -> "RawReview":
        """Factory method to create a RawReview from a WebElement"""
        # expand "More" - non-blocking approach
        for b in try_find(card, cls.MORE_BTN, all=True):
            try:
                b.click()
            except Exception:
                pass

        rid = card.get_attribute("data-review-id") or ""
        author = first_text(card, 'div[class*="d4r55"]')
        profile = first_attr(card, 'button[data-review-id]', "data-href")
        avatar = first_attr(card, 'button[data-review-id] img', "src")

        label = first_attr(card, 'span[role="img"]', "aria-label")
        num = re.search(r"[\d\.]+", label.replace(",", ".")) if label else None
        rating = float(num.group()) if num else 0.0

        date = first_text(card, 'span[class*="rsqaWe"]')
        # Parse the date string to ISO format
        review_date = parse_date_to_iso(date)

        text = ""
        for sel in ('span[jsname="bN97Pc"]',
                    'span[jsname="fbQN7e"]',
                    'div.MyEned span.wiI7pd'):
            text = first_text(card, sel)
            if text: break
        lang = detect_lang(text)

        likes = 0
        if (btn := try_find(card, cls.LIKE_BTN)):
            likes = safe_int(btn[0].text or btn[0].get_attribute("aria-label"))

        photos: list[str] = []
        for btn in try_find(card, cls.PHOTO_BTN, all=True):
            if (m := re.search(r'url\("([^"]+)"', btn.get_attribute("style") or "")):
                photos.append(m.group(1))

        owner_date = owner_text = ""
        if (box := try_find(card, cls.OWNER_RESP)):
            box = box[0]
            owner_date = first_text(box, "span.DZSIDd")
            owner_text = first_text(box, "div.wiI7pd")

        return cls(rid, author, rating, date, lang, text, likes,
                   photos, profile, avatar, owner_date, owner_text, review_date)
