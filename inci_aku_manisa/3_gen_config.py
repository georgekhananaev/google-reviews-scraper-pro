"""Aşama 3: Onaylı URL'lerden repo için config.yaml üret.

Girdi:
    data/urls_auto.json       — high confidence (otomatik kabul)
    data/manual_review.csv    — sen approved=Y/override_url ile doldurduktan sonra

Çıktı:
    inci_aku_config.yaml      — proje kökünde

Sonraki adım:
    python start.py scrape --config inci_aku_config.yaml
"""

import csv
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).parent.parent
DATA_DIR = Path(__file__).parent / "data"
AUTO_PATH = DATA_DIR / "urls_auto.json"
MANUAL_CSV_PATH = DATA_DIR / "manual_review.csv"
OUT_PATH = ROOT / "inci_aku_config.yaml"

# Repo defaults — sade tutuyoruz, sadece akü bayilerini analiz için lazım olanlar.
BASE_CONFIG = {
    "headless": True,
    "sort_by": "newest",
    "scrape_mode": "update",
    "stop_threshold": 3,
    "max_reviews": 0,
    "convert_dates": True,
    "download_images": False,   # akü analizi için resme gerek yok
    "use_mongodb": False,
    "use_s3": False,
    "backup_to_json": False,
    "db_path": "inci_aku_reviews.db",
    "resilience": {
        "retry_on_session_death": 1,
        "retry_backoff_base_seconds": 3,
        "rate_limit_cooldown_seconds": 60,
    },
}


def load_auto():
    if not AUTO_PATH.exists():
        return []
    return json.loads(AUTO_PATH.read_text(encoding="utf-8"))


def load_manual_approved():
    """manual_review.csv'den approved=Y olanları al.
    override_url doluysa onu kullan, yoksa google_url.

    Excel TR locale CSV'yi noktalı virgül ile kaydedebildiği için
    delimiter auto-detect ediyoruz (Sniffer , ve ;'ye bakar).
    """
    if not MANUAL_CSV_PATH.exists():
        return []
    out = []
    with MANUAL_CSV_PATH.open(encoding="utf-8") as f:
        sample = f.read(4096)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        for row in csv.DictReader(f, dialect=dialect):
            if row.get("approved", "").strip().upper() != "Y":
                continue
            url = (row.get("override_url") or "").strip() or row.get("google_url", "").strip()
            if not url:
                continue
            out.append({
                "dealer_id": row["dealer_id"],
                "firma_adi": row["firma_adi"],
                "cleaned_name": row["cleaned_name"],
                "ilce": row["ilce"],
                "kategori": row["kategori"],
                "google_url": url,
                "google_name": row.get("google_name"),
                "match_confidence": "manual",
            })
    return out


def build_business_entry(rec):
    """Repo'nun beklediği businesses[] formatı.

    custom_params'a koyduğumuz her şey reviews tablosunda saklanmasa da
    places kayıtlarıyla ilişkilendirebilmek için dealer_id'yi de yazıyoruz
    (4_score.py URL canonicalize ederek eşliyor, dealer_id sadece insan
    okuması için).
    """
    return {
        "url": rec["google_url"],
        "custom_params": {
            "dealer_id": rec["dealer_id"],
            "firma_adi": rec["firma_adi"],
            "cleaned_name": rec.get("cleaned_name") or "",
            "ilce": rec.get("ilce") or "",
            "kategori": rec.get("kategori") or "",
            "match_confidence": rec.get("match_confidence") or "",
            "source": "inciaku.com",
        },
    }


def main():
    auto = load_auto()
    manual = load_manual_approved()

    seen_urls = set()
    businesses = []
    for rec in auto + manual:
        url = rec["google_url"]
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        businesses.append(build_business_entry(rec))

    if not businesses:
        print("HATA: businesses listesi boş. Önce 2_resolve_urls.py çalıştır "
              "ve manual_review.csv'yi doldur.", file=sys.stderr)
        sys.exit(1)

    config = {**BASE_CONFIG, "businesses": businesses}
    OUT_PATH.write_text(
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False, width=120),
        encoding="utf-8",
    )
    print(f"[done] {len(businesses)} bayi → {OUT_PATH}")
    print(f"  auto: {len(auto)}  manual-approved: {len(manual)}")
    print(f"\nSonraki: python start.py scrape --config {OUT_PATH.name}")


if __name__ == "__main__":
    main()
