"""Aşama 1: inciaku.com'dan il bayilerini çek.

Site JSON API'sini kullanıyor:
    GET /clockwork/surface/bayiler/Get?kategori=...&sehir=...

Çıktı: data/dealers.json
"""

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


def main():
    sehir = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SEHIR
    OUT_DIR.mkdir(exist_ok=True)

    session = requests.Session()
    # Cookie ısınması
    session.get(REFERER, headers={"User-Agent": HEADERS["User-Agent"]}, timeout=30)

    all_rows = []
    seen = set()
    for kategori in KATEGORILER:
        print(f"[fetch] {kategori} / {sehir}", flush=True)
        rows = fetch(session, kategori, sehir)
        print(f"  → {len(rows)} kayıt")
        for row in rows:
            norm = normalize(row, kategori)
            key = (norm["firma_adi"], norm["adres"])
            if key in seen:
                continue
            seen.add(key)
            all_rows.append(norm)
        time.sleep(1.0)

    OUT_PATH.write_text(
        json.dumps(all_rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n[done] {len(all_rows)} benzersiz bayi → {OUT_PATH}")


if __name__ == "__main__":
    try:
        main()
    except requests.HTTPError as e:
        print(f"HTTP hatası: {e}", file=sys.stderr)
        sys.exit(1)
