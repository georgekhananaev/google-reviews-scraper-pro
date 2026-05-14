"""Aşama 1: inciaku.com'dan bayileri çek (tek il, çoklu il, veya 81 il).

Site JSON API'sini kullanıyor:
    GET /clockwork/surface/bayiler/Get?kategori=...&sehir=...

Kullanım:
    python 1_fetch_dealers.py                       # tek il (default MANİSA)
    python 1_fetch_dealers.py İSTANBUL              # tek il
    python 1_fetch_dealers.py --cities İST,İZMİR    # virgülle ayrılmış
    python 1_fetch_dealers.py --all                 # 81 il (uzun: ~5 dk)

Çıktı: data/dealers.json (tek liste, tüm illerin birleşimi)
"""

import argparse
import json
import sys
import time
from pathlib import Path

import requests

BASE = "https://www.inciaku.com"
LIST_URL = f"{BASE}/clockwork/surface/bayiler/Get"
REFERER = f"{BASE}/tr/bayiler-ve-servisler/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": REFERER,
}

KATEGORILER = ("Otomotiv", "Endüstri̇yel")
DEFAULT_SEHIR = "MANİSA"

# 81 il, inciaku dropdown'ında geçen büyük harfli formda. Site Türkçe
# karakterleri olduğu gibi alıyor; hatalı eşleşme olursa boş liste döner.
TR_CITIES_81 = [
    "ADANA", "ADIYAMAN", "AFYONKARAHİSAR", "AĞRI", "AKSARAY", "AMASYA",
    "ANKARA", "ANTALYA", "ARDAHAN", "ARTVİN", "AYDIN", "BALIKESİR",
    "BARTIN", "BATMAN", "BAYBURT", "BİLECİK", "BİNGÖL", "BİTLİS",
    "BOLU", "BURDUR", "BURSA", "ÇANAKKALE", "ÇANKIRI", "ÇORUM",
    "DENİZLİ", "DİYARBAKIR", "DÜZCE", "EDİRNE", "ELAZIĞ", "ERZİNCAN",
    "ERZURUM", "ESKİŞEHİR", "GAZİANTEP", "GİRESUN", "GÜMÜŞHANE",
    "HAKKARİ", "HATAY", "IĞDIR", "ISPARTA", "İSTANBUL", "İZMİR",
    "KAHRAMANMARAŞ", "KARABÜK", "KARAMAN", "KARS", "KASTAMONU",
    "KAYSERİ", "KİLİS", "KIRIKKALE", "KIRKLARELİ", "KIRŞEHİR", "KOCAELİ",
    "KONYA", "KÜTAHYA", "MALATYA", "MANİSA", "MARDİN", "MERSİN",
    "MUĞLA", "MUŞ", "NEVŞEHİR", "NİĞDE", "ORDU", "OSMANİYE", "RİZE",
    "SAKARYA", "SAMSUN", "SİİRT", "SİNOP", "ŞIRNAK", "SİVAS",
    "ŞANLIURFA", "TEKİRDAĞ", "TOKAT", "TRABZON", "TUNCELİ", "UŞAK",
    "VAN", "YALOVA", "YOZGAT", "ZONGULDAK",
]

OUT_DIR = Path(__file__).parent / "data"
OUT_PATH = OUT_DIR / "dealers.json"


def decode_coord(raw):
    """Site lat/lng'yi '3856...' gibi nokta'sız saklıyor.
    JS davranışı: substring(0,2) + '.' + substring(2), sonra '..' → '.'.
    """
    if not raw:
        return None
    s = str(raw).strip()
    if not s:
        return None
    if "." in s:
        try:
            return float(s)
        except ValueError:
            return None
    if len(s) < 3:
        return None
    decoded = (s[:2] + "." + s[2:]).replace("..", ".")
    try:
        return float(decoded)
    except ValueError:
        return None


def fetch(session, kategori, sehir):
    params = {"kategori": kategori, "sehir": sehir, "ilce": "", "turu": ""}
    r = session.get(LIST_URL, params=params, headers=HEADERS, timeout=30)
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, list):
        raise RuntimeError(f"Beklenmeyen response tipi: {type(data)}")
    return data


def normalize(row, kategori):
    return {
        "id": row.get("Name"),
        "firma_adi": row.get("FirmaAdi"),
        "adres": row.get("Adres"),
        "telefon": row.get("Telefon"),
        "turu": row.get("Turu"),
        "kategori": kategori,
        "sehir": row.get("Sehir") or row.get("sehir"),
        "ilce": row.get("Ilce") or row.get("ilce"),
        "lat": decode_coord(row.get("Enlem")),
        "lng": decode_coord(row.get("Boylam")),
    }


def fetch_city(session, sehir):
    """Bir il için her iki kategoriden bayileri çek, dedup'la."""
    rows = []
    seen = set()
    for kategori in KATEGORILER:
        try:
            data = fetch(session, kategori, sehir)
        except requests.HTTPError as e:
            print(f"  ✗ {kategori}: {e}")
            continue
        for row in data:
            norm = normalize(row, kategori)
            key = (norm["firma_adi"], norm["adres"])
            if key in seen:
                continue
            seen.add(key)
            rows.append(norm)
        time.sleep(0.5)
    return rows


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("city", nargs="?", default=None, help="Tek il (varsayılan MANİSA)")
    ap.add_argument("--cities", help="Virgülle ayrılmış il listesi (örn İST,İZMİR)")
    ap.add_argument("--all", action="store_true", help="Tüm 81 il (~5 dk)")
    ap.add_argument("--delay", type=float, default=1.0,
                    help="İller arası gecikme (sn). Default 1.0")
    return ap.parse_args()


def main():
    args = parse_args()
    if args.all:
        cities = TR_CITIES_81
    elif args.cities:
        cities = [c.strip() for c in args.cities.split(",") if c.strip()]
    elif args.city:
        cities = [args.city]
    else:
        cities = [DEFAULT_SEHIR]

    OUT_DIR.mkdir(exist_ok=True)

    session = requests.Session()
    session.get(REFERER, headers={"User-Agent": HEADERS["User-Agent"]}, timeout=30)

    all_rows = []
    seen_global = set()
    per_city = {}

    for i, sehir in enumerate(cities, 1):
        print(f"[{i}/{len(cities)}] {sehir}", flush=True)
        try:
            city_rows = fetch_city(session, sehir)
        except Exception as e:
            print(f"  ✗ {sehir}: {e}")
            per_city[sehir] = 0
            continue
        added = 0
        for row in city_rows:
            key = (row["firma_adi"], row["adres"])
            if key in seen_global:
                continue
            seen_global.add(key)
            all_rows.append(row)
            added += 1
        per_city[sehir] = added
        print(f"  → {len(city_rows)} kayıt, {added} yeni (toplam {len(all_rows)})")
        if i < len(cities):
            time.sleep(args.delay)

    OUT_PATH.write_text(
        json.dumps(all_rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n[done] {len(all_rows)} benzersiz bayi → {OUT_PATH}")
    print(f"      {len(cities)} il tarandı, en yoğun:")
    top = sorted(per_city.items(), key=lambda x: -x[1])[:10]
    for c, n in top:
        print(f"        {c:25} {n:>4}")


if __name__ == "__main__":
    try:
        main()
    except requests.HTTPError as e:
        print(f"HTTP hatası: {e}", file=sys.stderr)
        sys.exit(1)
