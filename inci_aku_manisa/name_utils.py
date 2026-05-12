"""Bayi adı temizleme + isim eşleşme + telefon/koordinat yardımcıları."""

import math
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

# Anlamsız ortak: hem inciaku hem Google adında geçse bile bayi eşleşmesini
# ispatlamayan jenerik kelimeler (şehir + sektör adları). normalize edilmiş
# (ascii-fold, küçük harf) hâlleriyle saklanır.
_GENERIC_COMMON_WORDS = {
    # şehirler
    "manisa", "izmir", "istanbul", "ankara", "bursa", "antalya",
    "konya", "adana", "gaziantep", "kayseri", "mersin",
    # genel sektör / tür
    "otomotiv", "servis", "servisi", "merkez", "merkezi",
    # ticari ekler
    "ticaret", "ticari", "sanayi", "anonim", "limited",
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


def normalize_phone(s):
    """Tek bir Türkiye telefon numarasını son 10 haneye indir.
    '+90 236 123 45 67', '0236 1234567', '236-123-45-67' → '2361234567'.
    """
    if not s:
        return ""
    digits = re.sub(r"\D", "", str(s))
    if digits.startswith("90") and len(digits) > 10:
        digits = digits[2:]
    if digits.startswith("0"):
        digits = digits[1:]
    return digits[-10:] if len(digits) >= 10 else digits


def normalize_phones(value):
    """String veya liste-of-string'den normalize edilmiş telefon set'i çıkar.

    inciaku bazı bayilerde tek string ('5358443519') verir, bazılarında
    liste (['02365 233 25 10', '0533 167 36 58']). İkisini de set olarak
    döndürür.
    """
    if not value:
        return set()
    items = value if isinstance(value, (list, tuple, set)) else [value]
    out = set()
    for item in items:
        if not item:
            continue
        n = normalize_phone(item)
        if len(n) >= 10:
            out.add(n)
    return out


def haversine_km(lat1, lng1, lat2, lng2):
    """İki coğrafi nokta arası km. None değer varsa float('inf') döner."""
    if None in (lat1, lng1, lat2, lng2):
        return float("inf")
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def score_candidate(dealer, candidate):
    """Bayi (inciaku) vs aday (Google Maps) için multi-signal skor.

    Sinyaller:
      - telefon eşleşmesi: +100 (kesinlik bonusu)
      - mesafe         : <100m +50, <500m +30, <2km +10
      - name similarity: 0..1 → 0..30
      - ortak 4+ harf kelime: her biri +10 (max 30)

    Eşikler:
      - phone_match              → high
      - total >= 70              → high
      - anlamlı ortak kelime var + total >= 35 → high
      - total >= 35              → medium
      - aksi                     → low

    "Anlamlı" = jenerik (şehir/sektör) sayılmayan kelime. 'manisa' veya
    'otomotiv' iki kayıtta geçse bile bayi eşleşmesini ispatlamaz; 'pekar'
    veya 'eksioglu' gibi özgün kelimeler ispatlar.

    Dönüş: (toplam_skor: int, confidence: str, breakdown: dict)
    """
    cleaned = dealer.get("cleaned_name") or dealer.get("firma_adi") or ""
    sim_label, sim, common = match_confidence(cleaned, candidate.get("name"))
    name_pts = round(sim * 30)
    common_pts = min(len(common), 3) * 10
    meaningful_common = [w for w in common if w not in _GENERIC_COMMON_WORDS]

    dist_km = haversine_km(
        dealer.get("lat"), dealer.get("lng"),
        candidate.get("lat"), candidate.get("lng"),
    )
    if dist_km < 0.1:
        dist_pts = 50
    elif dist_km < 0.5:
        dist_pts = 30
    elif dist_km < 2.0:
        dist_pts = 10
    else:
        dist_pts = 0

    dealer_phones = normalize_phones(dealer.get("telefon"))
    cand_phones = normalize_phones(candidate.get("phone"))
    matched_phones = dealer_phones & cand_phones
    phone_match = bool(matched_phones)
    phone_pts = 100 if phone_match else 0

    total = name_pts + common_pts + dist_pts + phone_pts
    # Anlamlı ortak kelime tek başına yetmez; ya yüksek isim benzerliği
    # ya da yakın koordinat ile desteklenmeli. Aksi halde "MANİSA OPEL
    # SERVİSİ İNCİ OTOMOTİV" gibi false-positive çıkıyor.
    common_supported = bool(meaningful_common) and (sim >= 0.6 or dist_km < 0.5)
    if phone_match:
        confidence = "high"
    elif total >= 70:
        confidence = "high"
    elif common_supported:
        confidence = "high"
    elif total >= 35:
        confidence = "medium"
    else:
        confidence = "low"

    breakdown = {
        "name_pts": name_pts,
        "common_pts": common_pts,
        "dist_pts": dist_pts,
        "phone_pts": phone_pts,
        "dist_km": round(dist_km, 2) if dist_km != float("inf") else None,
        "name_sim": round(sim, 3),
        "common_words": common,
        "meaningful_common": meaningful_common,
        "phone_match": phone_match,
        "dealer_phones": sorted(dealer_phones),
        "cand_phones": sorted(cand_phones),
        "matched_phones": sorted(matched_phones),
    }
    return total, confidence, breakdown
