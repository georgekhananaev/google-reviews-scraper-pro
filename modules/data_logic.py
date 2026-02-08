"""
Review merge logic extracted from data_storage.py.

Provides merge_review() and merge_review_with_translation() as pure functions
that combine raw scraped data with existing review documents. Extracted to its
own module to prevent circular imports when review_db.py needs merge logic.
"""

from typing import Dict, Any

from modules.models import RawReview
from modules.utils import detect_lang, get_current_iso_date


def merge_review(existing: Dict[str, Any] | None, raw: RawReview) -> Dict[str, Any]:
    """
    Merge a raw review with an existing review document.
    Creates a new document if existing is None.
    """
    if not existing:
        existing = {
            "review_id": raw.id,
            "author": raw.author,
            "rating": raw.rating,
            "description": {},
            "likes": raw.likes,
            "user_images": list(raw.photos),
            "author_profile_url": raw.profile,
            "profile_picture": raw.avatar,
            "owner_responses": {},
            "created_date": get_current_iso_date(),
            "review_date": raw.review_date or "",
        }
    else:
        # Handle existing reviews with old field names - migrate them
        if "texts" in existing and "description" not in existing:
            existing["description"] = existing.pop("texts")

        if "photo_urls" in existing and "user_images" not in existing:
            existing["user_images"] = existing.pop("photo_urls")

        if "profile_link" in existing and "author_profile_url" not in existing:
            existing["author_profile_url"] = existing.pop("profile_link")

        if "avatar_url" in existing and "profile_picture" not in existing:
            existing["profile_picture"] = existing.pop("avatar_url")

        if "created_date" not in existing:
            existing["created_date"] = get_current_iso_date()

        if "review_date" not in existing:
            existing["review_date"] = raw.review_date or ""

        if "date" in existing:
            del existing["date"]

    if raw.text:
        existing["description"][raw.lang] = raw.text

    if not existing.get("rating"):
        existing["rating"] = raw.rating

    if raw.likes > existing.get("likes", 0):
        existing["likes"] = raw.likes

    existing["user_images"] = list({*existing.get("user_images", []), *raw.photos})

    if raw.avatar and (
            not existing.get("profile_picture") or len(raw.avatar) > len(existing.get("profile_picture", ""))):
        existing["profile_picture"] = raw.avatar

    if raw.owner_text:
        lang = detect_lang(raw.owner_text)
        existing.setdefault("owner_responses", {})[lang] = {
            "text": raw.owner_text,
        }

    existing["last_modified_date"] = get_current_iso_date()

    return existing


def merge_review_with_translation(existing: Dict[str, Any] | None, raw: RawReview, append_translations: bool = False) -> Dict[str, Any]:
    """
    Enhanced merge function that supports translation mode.
    When append_translations is True, it adds new language versions to existing reviews.
    """
    merged = merge_review(existing, raw)

    if append_translations and existing and raw.text:
        merged["description"][raw.lang] = raw.text

        if raw.owner_text:
            owner_lang = detect_lang(raw.owner_text)
            merged.setdefault("owner_responses", {})[owner_lang] = {
                "text": raw.owner_text,
            }

        merged.setdefault("translation_history", []).append({
            "language": raw.lang,
            "added_date": get_current_iso_date(),
            "source": "regional_scraping"
        })

    return merged
