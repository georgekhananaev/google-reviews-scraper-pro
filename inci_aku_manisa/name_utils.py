"""Bayi adı temizleme + isim eşleşme güven skorlama."""

import re
import unicodedata
from difflib import SequenceMatcher

# inciaku adlarında sahip eki sık geçer. Tail'de bu kelimeler varsa
# işletmenin gerçek adının parçası kabul edilir (sıyrılmaz).
_BIZ_WORDS = {
    "SERVİS", "SERVIS", "SERVİSİ", "SERVISI",
    "OTO", "AKÜ", "AKU", "BAYİ", "BAYI",
    "MERKEZİ", "MERKEZI", "MERKEZ",
    "OTOMOTİV", "OTOMOTIV", "ELEKTRİK", "ELEKTRIK",
    "LASTİK", "LASTIK", "TEKNİK", "TEKNIK",
    "SAN", "TİC", "LTD", "ŞTİ",
}


def clean_dealer_name(name: str) -> str:
    """inciaku 'BARIŞ OTO - RECEP KERMEN' formatından sahip adını sıyır."""
    if not name:
        return ""
    n = name.strip()
    # ' -SAHIP-' deseni (sonda)
    n = re.sub(r"\s*-\s*[A-ZÇĞİÖŞÜa-zçğıöşü\s\.]+-\s*$", "", n)

    if " - " in n:
        head, _, tail = n.partition(" - ")
        tail_words = {w.upper() for w in re.split(r"\W+", tail) if w}
        if not (tail_words & _BIZ_WORDS):
            n = head
    return re.sub(r"\s+", " ", n).strip()


def _normalize(s: str) -> str:
    """Türkçe karakterleri ascii'leştir, küçük harf yap."""
    s = s.lower()
    # Türkçe özel dönüşümler
    s = s.replace("ı", "i").replace("ş", "s").replace("ğ", "g")
    s = s.replace("ü", "u").replace("ö", "o").replace("ç", "c")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s


def match_confidence(cleaned_name: str, google_name: str | None) -> tuple[str, float, list[str]]:
    """İnciaku adı vs Google adı için güven skoru.

    high   : 4+ harflik ortak kelime VAR
    medium : ortak yok ama similarity >= 0.5
    low    : aksi halde (veya google_name yoksa)
    """
    if not google_name:
        return ("low", 0.0, [])
    c = _normalize(cleaned_name)
    g = _normalize(google_name)
    sim = SequenceMatcher(None, c, g).ratio()
    words_c = {w for w in re.split(r"\W+", c) if len(w) > 3}
    words_g = {w for w in re.split(r"\W+", g) if len(w) > 3}
    common = sorted(words_c & words_g)
    if common:
        return ("high", sim, common)
    if sim >= 0.5:
        return ("medium", sim, [])
    return ("low", sim, [])
