"""Akü ve yan-iş keyword listeleri."""

BATTERY = [
    "akü", "aku", "batarya", "marş", "mars",
    "şarj", "sarj", "takviye", "amper", "volt",
    "kontak", "ölçüm", "olcum",
    "inci akü", "mutlu akü", "varta", "bosch akü",
]

OTHER_BUSINESS = [
    "lastik", "balans", "rot", "kaporta", "boya",
    "egzoz", "yağ değişimi", "yag degisimi",
    "periyodik bakım", "fren", "klima",
    "oto elektrik", "elektrikçi", "mekanik",
    "continental", "michelin", "pirelli", "goodyear",
    "bridgestone", "hankook", "petlas",
]


def contains_any(text, words):
    if not text:
        return []
    low = text.lower()
    return [w for w in words if w.lower() in low]
