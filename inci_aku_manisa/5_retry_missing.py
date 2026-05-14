"""Aşama 4.5: DB'de eksik veya yorumu olmayan bayiler için mini config üret.

Bazı bayilerde scrape başarısız olur (Maps URL açılamadı, panel okunamadı,
yorum sekmesi açılmadı). Bu helper:

  1. inci_aku_config.yaml'daki tüm bayilere bak
  2. Her biri için inci_aku_reviews.db'de:
       a. places kaydı var mı?
       b. en az 1 yorum var mı?
  3. İkisinden biri yoksa → "eksik" listesine ekle
  4. Eksiklerden mini config (eksikler_config.yaml) üret

Sonra:
    cd <scraper-repo>
    python start.py scrape --config eksikler_config.yaml

Aynı db_path'i kullandığı için ana DB'ye eklenir; yeniden full pipeline'a
gerek kalmaz.
"""

import sqlite3
import sys
from pathlib import Path

import yaml

CONFIG_NAME = "inci_aku_config.yaml"
DB_NAME = "inci_aku_reviews.db"
OUT_NAME = "eksikler_config.yaml"


def _find(name):
    for p in (Path.cwd() / name, Path.cwd().parent / name,
              Path.cwd().parent.parent / name,
              Path(__file__).parent.parent / name):
        if p.exists():
            return p
    return None


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    config_path = _find(CONFIG_NAME)
    if not config_path:
        print(f"HATA: {CONFIG_NAME} bulunamadı.", file=sys.stderr)
        sys.exit(1)
    db_path = _find(DB_NAME)
    if not db_path:
        print(f"HATA: {DB_NAME} bulunamadı.", file=sys.stderr)
        sys.exit(1)
    print(f"[config] {config_path}")
    print(f"[db]     {db_path}")

    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    conn = sqlite3.connect(str(db_path))

    missing = []
    ok_count = 0
    for biz in config.get("businesses", []):
        url = biz["url"]
        name = (biz.get("custom_params") or {}).get("firma_adi") or url
        row = conn.execute(
            "SELECT p.place_id, COUNT(r.review_id) "
            "FROM places p "
            "LEFT JOIN reviews r ON r.place_id = p.place_id "
            "  AND COALESCE(r.is_deleted, 0) = 0 "
            "WHERE p.original_url = ? OR p.resolved_url = ? "
            "GROUP BY p.place_id",
            (url, url),
        ).fetchone()
        if not row:
            missing.append((biz, "no_place"))
        elif row[1] == 0:
            missing.append((biz, "no_reviews"))
        else:
            ok_count += 1
    conn.close()

    print(f"\n{ok_count} bayi tamam, {len(missing)} eksik.")
    if not missing:
        print("Hepsi tamam, retry'a gerek yok.")
        return

    print("\nEksik bayiler:")
    for biz, reason in missing:
        firma = (biz.get("custom_params") or {}).get("firma_adi") or "?"
        print(f"  - {firma[:50]:50}  [{reason}]")

    mini = {
        "headless": config.get("headless", True),
        "sort_by": config.get("sort_by", "newest"),
        "scrape_mode": "update",
        "stop_threshold": config.get("stop_threshold", 3),
        "convert_dates": config.get("convert_dates", True),
        "download_images": False,
        "use_mongodb": False,
        "use_s3": False,
        "backup_to_json": False,
        "db_path": config.get("db_path", DB_NAME),
        "resilience": config.get("resilience"),
        "businesses": [b for b, _ in missing],
    }
    mini = {k: v for k, v in mini.items() if v is not None}

    out_path = config_path.parent / OUT_NAME
    out_path.write_text(
        yaml.safe_dump(mini, allow_unicode=True, sort_keys=False, width=120),
        encoding="utf-8",
    )
    print(f"\n[done] {len(missing)} bayi → {out_path}")
    print(f"\nSonraki:")
    print(f"  cd <scraper-repo>")
    print(f"  Copy-Item {out_path} .")
    print(f"  python start.py scrape --config {OUT_NAME}")


if __name__ == "__main__":
    main()
