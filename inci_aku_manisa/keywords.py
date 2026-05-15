"""Bayilerde aranacak akü markaları + yan-iş işaretleri.

NOT: BATTERY listesi MARKA-bazlı dar filtre. 'akü/marş/takviye' gibi
jenerik kelimeler artık burada YOK; sadece bu üç markanın geçtiği
yorumlar `battery_only_reviews`'a girer.
"""

import unicodedata

BATTERY = [
    # NOT: contains_any NFKD normalize uyguladığı için 'akü' = 'aku',
    # 'İnci' = 'inci'. Tek varyant yeterli; tüm yazımlar match olur.
    "inci akü",
    "inciaku",
    "eas akü",
    "eas akümülatör",
    "hugel akü",
]

OTHER_BUSINESS = [
    "lastik", "balans", "rot", "kaporta", "boya",
    "egzoz", "yağ değişimi", "yag degisimi",
    "periyodik bakım", "fren", "klima",
    "oto elektrik", "elektrikçi", "mekanik",
    "continental", "michelin", "pirelli", "goodyear",
    "bridgestone", "hankook", "petlas",
]


def _tr_lower(s):
    """Türkçe-aware lowercase. 'İnci'.lower() default'ta 'i̇nci' (combining
    dot) verir; bu da düz ASCII 'inci' ile eşleşmez. NFKD + combining
    silme ile normalize ediyoruz."""
    if not s:
        return ""
    s = s.lower()
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


def contains_any(text, words):
    if not text:
        return []
    low = _tr_lower(text)
    return [w for w in words if _tr_lower(w) in low]
