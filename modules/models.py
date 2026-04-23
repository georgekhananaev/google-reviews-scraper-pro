"""
Data models for Google Maps Reviews Scraper.
"""
import logging
import re
from dataclasses import dataclass, field

from selenium.webdriver.remote.webelement import WebElement

from modules.sub_rating_labels import canonicalize_category
from modules.utils import (try_find, first_text, first_attr, safe_int, detect_lang, parse_date_to_iso)

log = logging.getLogger("scraper")


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
    avatar: str = ""
    owner_date: str = ""
    owner_text: str = ""
    review_date: str = ""
    sub_ratings: dict = field(default_factory=dict)
    translations: dict = field(default_factory=dict)

    # CSS selector candidates — tried in order, first match wins.
    MORE_BTN = (
        "button.kyuRq",
        'button[jsaction*="expandReview"]',
        'button[aria-expanded="false"][jsaction*="review" i]',
    )
    LIKE_BTN = 'button[jsaction*="toggleThumbsUp" i]'
    PHOTO_BTN_SELECTORS = (
        "button.Tya61d",
        'button[aria-label*="Photo" i][style*="url"]',
        'button[data-photo-index]',
    )
    OWNER_RESP_SELECTORS = (
        "div.CDe7pd",
        'div[class*="owner" i]',
    )
    OWNER_DATE_SELECTORS = (
        "span.DZSIDd",
        'span[class*="ownerdate" i]',
    )
    OWNER_TEXT_SELECTORS = (
        "div.wiI7pd",
        'div[class*="ownerresp" i]',
    )
    TEXT_SELECTORS = (
        'span[jsname="bN97Pc"]',
        'span[jsname="fbQN7e"]',
        'div.MyEned span.wiI7pd',
    )
    RATING_SELECTORS = (
        'span[role="img"][aria-label]',
        'span[class*="kvMYJc" i]',
    )
    DATE_SELECTORS = (
        'span[class*="rsqaWe"]',
        'span[class*="xRkPPb" i]',
    )
    SUB_RATING_SELECTORS = (
        'div.PBK6be',
        'div[class*="rating" i][aria-label*="/5" i]',
    )

    @classmethod
    def from_card(cls, card: WebElement) -> "RawReview":
        """Factory method to create a RawReview from a WebElement."""
        for sel in cls.MORE_BTN:
            buttons = try_find(card, sel, all=True)
            if buttons:
                for b in buttons:
                    try:
                        b.click()
                    except Exception:
                        pass
                break

        rid = card.get_attribute("data-review-id") or ""
        author = first_text(card, 'div[class*="d4r55"]')
        profile = first_attr(card, 'button[data-review-id]', "data-href")
        avatar = first_attr(card, 'button[data-review-id] img', "src")

        rating = 0.0
        for sel in cls.RATING_SELECTORS:
            label = first_attr(card, sel, "aria-label")
            if label:
                num = re.search(r"[\d\.]+", label.replace(",", "."))
                if num:
                    try:
                        rating = float(num.group())
                        if 0 < rating <= 5:
                            break
                    except ValueError:
                        continue

        date = ""
        for sel in cls.DATE_SELECTORS:
            date = first_text(card, sel)
            if date:
                break
        review_date = parse_date_to_iso(date)

        text = ""
        for sel in cls.TEXT_SELECTORS:
            text = first_text(card, sel)
            if text:
                break
        lang = detect_lang(text)

        likes = 0
        if (btn := try_find(card, cls.LIKE_BTN)):
            likes = safe_int(btn[0].text or btn[0].get_attribute("aria-label"))

        photos: list[str] = []
        for sel in cls.PHOTO_BTN_SELECTORS:
            found = try_find(card, sel, all=True)
            if not found:
                continue
            for btn in found:
                style = btn.get_attribute("style") or ""
                m = re.search(r'url\(["\']?([^"\')]+)', style)
                if m:
                    url = m.group(1)
                    if url not in photos:
                        photos.append(url)
            if photos:
                break

        owner_date = owner_text = ""
        for sel in cls.OWNER_RESP_SELECTORS:
            box_list = try_find(card, sel)
            if not box_list:
                continue
            box = box_list[0]
            for d_sel in cls.OWNER_DATE_SELECTORS:
                owner_date = first_text(box, d_sel)
                if owner_date:
                    break
            for t_sel in cls.OWNER_TEXT_SELECTORS:
                owner_text = first_text(box, t_sel)
                if owner_text:
                    break
            break

        sub_ratings = cls._extract_sub_ratings(card)

        return cls(
            id=rid,
            author=author,
            rating=rating,
            date=date,
            lang=lang,
            text=text,
            likes=likes,
            photos=photos,
            profile=profile,
            avatar=avatar,
            owner_date=owner_date,
            owner_text=owner_text,
            review_date=review_date,
            sub_ratings=sub_ratings,
        )

    @classmethod
    def _extract_sub_ratings(cls, card: WebElement) -> dict:
        """Extract per-category sub-ratings (e.g. Service 5/5, Food 4/5)."""
        result: dict = {}
        for sel in cls.SUB_RATING_SELECTORS:
            blocks = try_find(card, sel, all=True)
            if not blocks:
                continue
            for block in blocks:
                try:
                    label = (block.get_attribute("aria-label") or block.text or "").strip()
                    if not label:
                        continue
                    m = re.match(r"(.+?)[:\s]+(\d)\s*/\s*5", label)
                    if not m:
                        continue
                    raw_cat = m.group(1).strip(" :.").lower()
                    score = int(m.group(2))
                    if score < 0 or score > 5:
                        continue
                    canonical = canonicalize_category(raw_cat)
                    if canonical:
                        result[canonical] = score
                    else:
                        result.setdefault("_other", {})[raw_cat] = score
                except (ValueError, AttributeError):
                    continue
            if result:
                break
        return result
