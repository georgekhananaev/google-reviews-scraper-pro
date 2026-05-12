"""Aşama 4: Scrape edilmiş yorumları akü/yan-iş keyword'leri ile skorla.

Girdi:
    inci_aku_config.yaml         — bayi listesi + URL'ler
    inci_aku_reviews.db          — repo'nun scrape çıktısı

Çıktı:
    data/dealers_scored.json     — bayi başına yorum analizi
    Konsol özet tablosu.
"""

import json
import sqlite3
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from keywords import BATTERY, OTHER_BUSINESS, contains_any  # noqa: E402

# Repo modülü — URL eşlemesi için
sys.path.insert(0, str(Path(__file__).parent.parent))
from modules.place_id import canonicalize_url  # noqa: E402

ROOT = Path(__file__).parent.parent
CONFIG_PATH = ROOT / "inci_aku_config.yaml"
OUT_PATH = Path(__file__).parent / "data" / "dealers_scored.json"

# Akü-bayisi heuristic eşikleri
PURE_BATTERY_BAT_RATIO = 0.30
PURE_BATTERY_MAX_OTHER = 0.20


def find_place_id(conn, url):
    """Bayi URL'ini DB'deki place_id'ye eşle.
    Önce tam eşleşme, sonra canonicalize edilmiş eşleşme, sonra alias tablosu."""
    cur = conn.cursor()

    # 1) Tam eşleşme (original_url veya resolved_url)
    row = cur.execute(
        "SELECT place_id FROM places "
        "WHERE original_url = ? OR resolved_url = ? LIMIT 1",
        (url, url),
    ).fetchone()
    if row:
        return row[0]

    # 2) Canonicalize edip dolaş
    target = canonicalize_url(url)
    for pid, orig, resolved in cur.execute(
        "SELECT place_id, original_url, resolved_url FROM places"
    ):
        if canonicalize_url(orig) == target or (
            resolved and canonicalize_url(resolved) == target
        ):
            return pid

    # 3) Aliases
    row = cur.execute(
        "SELECT canonical_id FROM place_aliases WHERE original_url = ? LIMIT 1",
        (url,),
    ).fetchone()
    if row:
        return row[0]
    return None


def fetch_reviews(conn, place_id):
    rows = conn.execute(
        "SELECT review_id, author, rating, review_text, review_date, raw_date "
        "FROM reviews WHERE place_id = ? AND COALESCE(is_deleted, 0) = 0",
        (place_id,),
    ).fetchall()
    return [
        {
            "review_id": r[0],
            "author": r[1],
            "rating": r[2],
            "text": r[3] or "",
            "review_date": r[4],
            "raw_date": r[5],
        }
        for r in rows
    ]


def analyze(reviews):
    total = len(reviews)
    if total == 0:
        return {
            "total_reviews": 0,
            "battery_reviews": 0,
            "other_business_reviews": 0,
            "battery_ratio": 0.0,
            "other_business_ratio": 0.0,
            "avg_rating_overall": None,
            "avg_rating_battery": None,
            "is_likely_pure_battery_dealer": False,
            "battery_only_reviews": [],
        }

    all_ratings, bat_ratings = [], []
    n_bat = n_oth = 0
    battery_only = []
    for r in reviews:
        text = r.get("text") or ""
        bk = contains_any(text, BATTERY)
        ok = contains_any(text, OTHER_BUSINESS)
        if r.get("rating") is not None:
            all_ratings.append(r["rating"])
        if bk:
            n_bat += 1
            if r.get("rating") is not None:
                bat_ratings.append(r["rating"])
            # Akü kelimesi varsa al, yan-iş de geçse dahil et.
            battery_only.append({
                **r,
                "battery_keywords": bk,
                "other_business_keywords": ok,
            })
        if ok:
            n_oth += 1

    bat_ratio = n_bat / total
    oth_ratio = n_oth / total
    avg_all = sum(all_ratings) / len(all_ratings) if all_ratings else None
    avg_bat = sum(bat_ratings) / len(bat_ratings) if bat_ratings else None
    return {
        "total_reviews": total,
        "battery_reviews": n_bat,
        "other_business_reviews": n_oth,
        "battery_ratio": round(bat_ratio, 3),
        "other_business_ratio": round(oth_ratio, 3),
        "avg_rating_overall": round(avg_all, 2) if avg_all is not None else None,
        "avg_rating_battery": round(avg_bat, 2) if avg_bat is not None else None,
        "is_likely_pure_battery_dealer": (
            bat_ratio >= PURE_BATTERY_BAT_RATIO and oth_ratio < PURE_BATTERY_MAX_OTHER
        ),
        "battery_only_reviews": battery_only,
    }


def print_summary(scored):
    print("\n" + "=" * 132)
    print(f"{'BAYİ':<38} {'İLÇE':<11} {'GOOGLE ADI':<28} "
          f"{'YORUM':>6} {'AKÜ':>11} {'YAN-İŞ':>11} {'PURE?':>6}")
    print("=" * 132)
    for s in scored:
        name = s["firma_adi"][:36]
        ilce = (s.get("ilce") or "")[:9]
        g = (s.get("google_name") or "?")[:26]
        t = s["total_reviews"]
        if t:
            bat = f"{s['battery_reviews']} ({s['battery_ratio']:.0%})"
            oth = f"{s['other_business_reviews']} ({s['other_business_ratio']:.0%})"
        else:
            bat = oth = "-"
        pure = "EVET" if s["is_likely_pure_battery_dealer"] else "hayır"
        print(f"{name:<38} {ilce:<11} {g:<28} {t:>6} {bat:>11} {oth:>11} {pure:>6}")
    print("=" * 132)


def main():
    if not CONFIG_PATH.exists():
        print(f"HATA: {CONFIG_PATH} yok. Önce 3_gen_config.py.", file=sys.stderr)
        sys.exit(1)
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    db_path = ROOT / config.get("db_path", "reviews.db")
    if not db_path.exists():
        print(f"HATA: {db_path} yok. Önce python start.py scrape --config "
              f"{CONFIG_PATH.name} çalıştır.", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(str(db_path))
    scored = []
    unmatched = []
    for biz in config.get("businesses", []):
        params = biz.get("custom_params") or {}
        url = biz["url"]
        pid = find_place_id(conn, url)
        if not pid:
            unmatched.append(params.get("firma_adi") or url)
            scored.append({
                **params,
                "url": url,
                "place_id": None,
                "google_name": None,
                **analyze([]),
                "status": "not_found_in_db",
            })
            continue
        place_name = conn.execute(
            "SELECT place_name FROM places WHERE place_id = ?", (pid,)
        ).fetchone()
        reviews = fetch_reviews(conn, pid)
        scored.append({
            **params,
            "url": url,
            "place_id": pid,
            "google_name": place_name[0] if place_name else None,
            **analyze(reviews),
            "status": "ok",
        })
    conn.close()

    OUT_PATH.parent.mkdir(exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(scored, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[done] {len(scored)} bayi → {OUT_PATH}")
    if unmatched:
        print(f"\n⚠ DB'de bulunamayan {len(unmatched)} bayi (henüz scrape edilmemiş?):")
        for n in unmatched[:10]:
            print(f"   - {n}")
        if len(unmatched) > 10:
            print(f"   ... +{len(unmatched) - 10}")
    print_summary(scored)


if __name__ == "__main__":
    main()
