"""
Canonical category mapping for review sub-ratings.

Google Maps shows category sub-ratings (Service 5/5, Food 4/5, etc.) on
hotels, restaurants, spas, and similar venues. Labels are localized per user
locale — we map them to a stable canonical set and leave unknowns untouched
in `_other`.
"""

CANONICAL_CATEGORIES = (
    "service",
    "food",
    "atmosphere",
    "cleanliness",
    "value",
    "rooms",
    "location",
    "comfort",
    "staff",
    "facilities",
    "breakfast",
    "amenities",
)

# Label → canonical. Lowercase match; multi-language coverage will grow via PRs.
_LABEL_MAP = {
    # English
    "service": "service",
    "food": "food",
    "atmosphere": "atmosphere",
    "cleanliness": "cleanliness",
    "value": "value",
    "rooms": "rooms",
    "room": "rooms",
    "location": "location",
    "comfort": "comfort",
    "staff": "staff",
    "facilities": "facilities",
    "breakfast": "breakfast",
    "amenities": "amenities",

    # French
    "service": "service",
    "cuisine": "food",
    "nourriture": "food",
    "ambiance": "atmosphere",
    "propreté": "cleanliness",
    "rapport qualité-prix": "value",
    "chambres": "rooms",
    "emplacement": "location",
    "confort": "comfort",
    "personnel": "staff",
    "équipements": "facilities",
    "petit-déjeuner": "breakfast",

    # German
    "essen": "food",
    "ambiente": "atmosphere",
    "sauberkeit": "cleanliness",
    "preis-leistungs-verhältnis": "value",
    "zimmer": "rooms",
    "lage": "location",
    "komfort": "comfort",
    "personal": "staff",
    "frühstück": "breakfast",
    "ausstattung": "amenities",

    # Spanish
    "servicio": "service",
    "comida": "food",
    "ambiente": "atmosphere",
    "limpieza": "cleanliness",
    "calidad-precio": "value",
    "habitaciones": "rooms",
    "ubicación": "location",
    "comodidad": "comfort",
    "personal": "staff",
    "instalaciones": "facilities",
    "desayuno": "breakfast",

    # Italian
    "servizio": "service",
    "cibo": "food",
    "atmosfera": "atmosphere",
    "pulizia": "cleanliness",
    "rapporto qualità-prezzo": "value",
    "camere": "rooms",
    "posizione": "location",

    # Portuguese
    "serviço": "service",
    "comida": "food",
    "ambiente": "atmosphere",
    "limpeza": "cleanliness",
    "custo-benefício": "value",
    "quartos": "rooms",
    "localização": "location",

    # Russian
    "обслуживание": "service",
    "еда": "food",
    "атмосфера": "atmosphere",
    "чистота": "cleanliness",
    "цена": "value",
    "номера": "rooms",
    "расположение": "location",

    # Hebrew
    "שירות": "service",
    "אוכל": "food",
    "אווירה": "atmosphere",
    "ניקיון": "cleanliness",
    "תמורה": "value",
    "חדרים": "rooms",
    "מיקום": "location",

    # Thai
    "บริการ": "service",
    "อาหาร": "food",
    "บรรยากาศ": "atmosphere",
    "ความสะอาด": "cleanliness",
    "คุ้มค่า": "value",
    "ห้องพัก": "rooms",
    "ทำเลที่ตั้ง": "location",
}


def canonicalize_category(label: str) -> str:
    """Return canonical category name for a raw label, or '' if unknown."""
    if not label:
        return ""
    key = label.strip().lower()
    if key in _LABEL_MAP:
        return _LABEL_MAP[key]
    for known_label, canonical in _LABEL_MAP.items():
        if known_label in key:
            return canonical
    return ""
