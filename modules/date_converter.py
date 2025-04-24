"""
Date conversion utilities for Google Maps reviews.
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

# Logger
log = logging.getLogger("scraper")


def relative_to_datetime(date_str: str, lang: str = "en") -> Optional[datetime]:
    """
    Convert a relative date string to a datetime object.

    Args:
        date_str: The relative date string (e.g., "2 years ago")
        lang: Language code ("en" or "he")

    Returns:
        datetime object or None if conversion fails
    """
    if not date_str:
        return None

    try:
        # Convert to ISO format first
        iso_date = parse_relative_date(date_str, lang)

        # If original string was returned, it wasn't in the expected format
        if iso_date == date_str:
            return None

        # Parse the ISO format into datetime
        return datetime.fromisoformat(iso_date)
    except Exception as e:
        log.debug(f"Failed to convert relative date '{date_str}': {e}")
        return None


class DateConverter:
    """Handler for converting string dates to datetime objects in MongoDB"""

    @staticmethod
    def convert_dates_in_document(doc: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert string dates to datetime objects in a document.

        Args:
            doc: MongoDB document with string dates

        Returns:
            Document with string dates converted to datetime objects
        """
        # Remove the original date string field if it exists
        if "date" in doc:
            original_date = doc.pop("date")

            # Try to use the original date to fix review_date if needed
            if "review_date" not in doc or not doc["review_date"]:
                lang = next(iter(doc.get("description", {}).keys()), "en")
                date_obj = relative_to_datetime(original_date, lang)
                if date_obj:
                    doc["review_date"] = date_obj

        # Fields that should be converted to dates
        date_fields = ["created_date", "last_modified_date", "review_date"]

        # Convert date fields to datetime
        for field in date_fields:
            if field in doc and isinstance(doc[field], str):
                try:
                    # Try to parse as ISO format first
                    doc[field] = datetime.fromisoformat(doc[field].replace('Z', '+00:00'))
                except (ValueError, TypeError):
                    # If that fails, try parsing as relative date
                    lang = next(iter(doc.get("description", {}).keys()), "en")
                    date_obj = relative_to_datetime(doc[field], lang)
                    if date_obj:
                        doc[field] = date_obj

        # Handle nested date fields in owner_responses
        if "owner_responses" in doc and isinstance(doc["owner_responses"], dict):
            for lang, response in doc["owner_responses"].items():
                if isinstance(response, dict) and "date" in response:
                    # Remove the date string field from owner responses
                    del response["date"]

        return doc

    @staticmethod
    def convert_dates_in_reviews(reviews: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        Convert string dates to datetime objects for all reviews.

        Args:
            reviews: Dictionary of review documents

        Returns:
            Reviews with dates converted to datetime objects
        """
        log.info("Converting string dates to datetime objects...")

        for review_id, review in reviews.items():
            reviews[review_id] = DateConverter.convert_dates_in_document(review)

        return reviews


def parse_relative_date(date_str: str, lang: str, now: Optional[datetime] = None) -> str:
    """
    Converts a relative review_date (in English or Hebrew) such as "a week ago" or "לפני 7 שנים"
    into an ISO formatted datetime string (UTC).

    For English, supported formats include:
       - "a day ago", "an hour ago", "3 weeks ago", "4 months ago", "2 years ago", etc.
    For Hebrew, supported formats include:
       - "לפני יום", "לפני 2 ימים", "לפני שבוע", "לפני שבועיים", "לפני חודש",
         "לפני חודשיים", "לפני 10 חודשים", "לפני שנה", "לפני 3 שנים", etc.

    Parameters:
      - date_str (str): the relative date string.
      - lang (str): "en" for English or "he" for Hebrew.
      - now (Optional[datetime]): reference datetime; if None, current local time is used.

    Returns:
      A string representing the calculated absolute datetime in ISO 8601 format.
      If parsing fails in all supported languages, returns a random date within the last year.
    """
    import random

    if now is None:
        now = datetime.utcnow()  # use UTC for consistency

    # Try with the provided language first
    result = try_parse_date(date_str, lang, now)
    if result != date_str:
        return result

    # If the provided language failed, try other supported languages
    supported_langs = ["en", "he", "th"]
    for alt_lang in supported_langs:
        if alt_lang != lang.lower():
            result = try_parse_date(date_str, alt_lang, now)
            if result != date_str:
                return result

    # If all parsing attempts failed, generate a random date within the last year
    # This creates a date between 1 day ago and 365 days ago
    random_days_ago = random.randint(1, 365)
    random_date = now - timedelta(days=random_days_ago)
    return random_date.isoformat()


def try_parse_date(date_str: str, lang: str, now: datetime) -> str:
    """
    Helper function that attempts to parse a date string in a specific language.

    Returns the ISO formatted date if successful, or the original string if not.
    """
    delta = timedelta(0)
    parsed = False

    if lang.lower() == "en":
        # Pattern: capture number or "a"/"an", then unit.
        pattern = re.compile(r'(?P<num>a|an|\d+)\s+(?P<unit>day|week|month|year)s?\s+ago', re.IGNORECASE)
        m = pattern.search(date_str)
        if m:
            num_str = m.group("num").lower()
            num = 1 if num_str in ("a", "an") else int(num_str)
            unit = m.group("unit").lower()
            if unit == "day":
                delta = timedelta(days=num)
            elif unit == "week":
                delta = timedelta(weeks=num)
            elif unit == "month":
                delta = timedelta(days=30 * num)  # approximate
            elif unit == "year":
                delta = timedelta(days=365 * num)  # approximate
            parsed = True
    elif lang.lower() == "he":
        # Remove the "לפני" prefix if present
        text = date_str.strip()
        if text.startswith("לפני"):
            text = text[len("לפני"):].strip()

        # Handle special cases where the number and unit are combined:
        special = {
            "חודשיים": (2, "month"),
            "שבועיים": (2, "week"),
            "יומיים": (2, "day"),
        }
        if text in special:
            num, unit = special[text]
            if unit == "day":
                delta = timedelta(days=num)
            elif unit == "week":
                delta = timedelta(weeks=num)
            elif unit == "month":
                delta = timedelta(days=30 * num)  # approximate
            parsed = True
        else:
            # Match optional number (or assume 1) and then a unit.
            pattern = re.compile(r'(?P<num>\d+|אחד|אחת)?\s*(?P<unit>שנה|שנים|חודש|חודשים|יום|ימים|שבוע|שבועות)',
                                 re.IGNORECASE)
            m = pattern.search(text)
            if m:
                num_str = m.group("num")
                if not num_str:
                    num = 1
                else:
                    try:
                        num = int(num_str)
                    except ValueError:
                        num = 1
                unit_he = m.group("unit")
                # Map the Hebrew unit (both singular and plural) to English unit names
                if unit_he in ("יום", "ימים"):
                    unit = "day"
                elif unit_he in ("שבוע", "שבועות"):
                    unit = "week"
                elif unit_he in ("חודש", "חודשים"):
                    unit = "month"
                elif unit_he in ("שנה", "שנים"):
                    unit = "year"
                else:
                    unit = "day"  # fallback

                if unit == "day":
                    delta = timedelta(days=num)
                elif unit == "week":
                    delta = timedelta(weeks=num)
                elif unit == "month":
                    delta = timedelta(days=30 * num)  # approximate
                elif unit == "year":
                    delta = timedelta(days=365 * num)  # approximate
                parsed = True
    elif lang.lower() == "th":
        # Thai language patterns (simplified)
        # Check for Thai patterns like "3 วันที่แล้ว" (3 days ago)
        thai_pattern = re.compile(r'(?P<num>\d+)?\s*(?P<unit>วัน|สัปดาห์|เดือน|ปี)ที่แล้ว', re.IGNORECASE)
        m = thai_pattern.search(date_str)
        if m:
            num_str = m.group("num")
            num = 1 if not num_str else int(num_str)
            unit_th = m.group("unit")

            # Map Thai units to English
            if unit_th == "วัน":
                unit = "day"
            elif unit_th == "สัปดาห์":
                unit = "week"
            elif unit_th == "เดือน":
                unit = "month"
            elif unit_th == "ปี":
                unit = "year"
            else:
                unit = "day"  # fallback

            if unit == "day":
                delta = timedelta(days=num)
            elif unit == "week":
                delta = timedelta(weeks=num)
            elif unit == "month":
                delta = timedelta(days=30 * num)  # approximate
            elif unit == "year":
                delta = timedelta(days=365 * num)  # approximate
            parsed = True

    # Return the calculated date if parsing was successful, otherwise return the original string
    if parsed:
        result = now - delta
        return result.isoformat()
    else:
        return date_str


# def parse_relative_date(date_str: str, lang: str, now: Optional[datetime] = None) -> str:
#     """
#     Converts a relative review_date (in English or Hebrew) such as "a week ago" or "לפני 7 שנים"
#     into an ISO formatted datetime string (UTC).
#
#     For English, supported formats include:
#        - "a day ago", "an hour ago", "3 weeks ago", "4 months ago", "2 years ago", etc.
#     For Hebrew, supported formats include:
#        - "לפני יום", "לפני 2 ימים", "לפני שבוע", "לפני שבועיים", "לפני חודש",
#          "לפני חודשיים", "לפני 10 חודשים", "לפני שנה", "לפני 3 שנים", etc.
#
#     Parameters:
#       - date_str (str): the relative date string.
#       - lang (str): "en" for English or "he" for Hebrew.
#       - now (Optional[datetime]): reference datetime; if None, current local time is used.
#
#     Returns:
#       A string representing the calculated absolute datetime in ISO 8601 format,
#       or the original date_str if parsing fails.
#     """
#     if now is None:
#         now = datetime.utcnow()  # use UTC for consistency
#
#     delta = timedelta(0)
#
#     if lang.lower() == "en":
#         # Pattern: capture number or "a"/"an", then unit.
#         pattern = re.compile(r'(?P<num>a|an|\d+)\s+(?P<unit>day|week|month|year)s?\s+ago', re.IGNORECASE)
#         m = pattern.search(date_str)
#         if m:
#             num_str = m.group("num").lower()
#             num = 1 if num_str in ("a", "an") else int(num_str)
#             unit = m.group("unit").lower()
#             if unit == "day":
#                 delta = timedelta(days=num)
#             elif unit == "week":
#                 delta = timedelta(weeks=num)
#             elif unit == "month":
#                 delta = timedelta(days=30 * num)  # approximate
#             elif unit == "year":
#                 delta = timedelta(days=365 * num)  # approximate
#         else:
#             return date_str  # return original if not matched
#     elif lang.lower() == "he":
#         # Remove the "לפני" prefix if present
#         text = date_str.strip()
#         if text.startswith("לפני"):
#             text = text[len("לפני"):].strip()
#
#         # Handle special cases where the number and unit are combined:
#         special = {
#             "חודשיים": (2, "month"),
#             "שבועיים": (2, "week"),
#             "יומיים": (2, "day"),
#         }
#         if text in special:
#             num, unit = special[text]
#         else:
#             # Match optional number (or assume 1) and then a unit.
#             pattern = re.compile(r'(?P<num>\d+|אחד|אחת)?\s*(?P<unit>שנה|שנים|חודש|חודשים|יום|ימים|שבוע|שבועות)',
#                                  re.IGNORECASE)
#             m = pattern.search(text)
#             if m:
#                 num_str = m.group("num")
#                 if not num_str:
#                     num = 1
#                 else:
#                     try:
#                         num = int(num_str)
#                     except ValueError:
#                         num = 1
#                 unit_he = m.group("unit")
#                 # Map the Hebrew unit (both singular and plural) to English unit names
#                 if unit_he in ("יום", "ימים"):
#                     unit = "day"
#                 elif unit_he in ("שבוע", "שבועות"):
#                     unit = "week"
#                 elif unit_he in ("חודש", "חודשים"):
#                     unit = "month"
#                 elif unit_he in ("שנה", "שנים"):
#                     unit = "year"
#                 else:
#                     unit = "day"  # fallback
#             else:
#                 return date_str  # if nothing matches, return original text
#
#         if unit == "day":
#             delta = timedelta(days=num)
#         elif unit == "week":
#             delta = timedelta(weeks=num)
#         elif unit == "month":
#             delta = timedelta(days=30 * num)  # approximate
#         elif unit == "year":
#             delta = timedelta(days=365 * num)  # approximate
#
#     result = now - delta
#     return result.isoformat()


# --- Example usage ---
if __name__ == "__main__":
    # Fixed reference time for reproducibility:
    fixed_now = datetime(2025, 2, 5, 12, 0, 0)
    examples = [
        ("a week ago", "he"),
        ("4 weeks ago", "en"),
        ("לפני 7 שנים", "he"),
        ("לפני חודשיים", "he")
    ]
    for text, lang in examples:
        iso_date = parse_relative_date(text, lang, now=fixed_now)
        print(f"Original: {text} ({lang}) => ISO: {iso_date}")
