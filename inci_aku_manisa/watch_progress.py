"""Scrape'in canlı ilerlemesini başka PowerShell'de göster.

Her 10 saniyede bir DB'yi sorgular:
  - Kaç place / kaç review yazıldı
  - Son scrape edilen bayi
  - Bayi başına ortalama yorum
  - Geçen süre + tahmini kalan süre

Ctrl+C ile çık.

Kullanım:
    python watch_progress.py            # 10 sn aralık
    python watch_progress.py --every 5  # 5 sn aralık
"""

import argparse
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path


def find_db():
    for p in (
        Path(r"c:\Users\stjot2\Desktop\scraper-repo\inci_aku_reviews.db"),
        Path(r"c:\Users\stjot2\Desktop\inci_aku_reviews.db"),
        Path.cwd() / "inci_aku_reviews.db",
        Path.cwd().parent / "inci_aku_reviews.db",
    ):
        if p.exists():
            return p
    return None


def find_config_total():
    """inci_aku_config.yaml'dan toplam bayi sayısı (hedef)."""
    import yaml
    for p in (
        Path(r"c:\Users\stjot2\Desktop\inci_aku_config.yaml"),
        Path(r"c:\Users\stjot2\Desktop\scraper-repo\inci_aku_config.yaml"),
        Path.cwd() / "inci_aku_config.yaml",
    ):
        if p.exists():
            try:
                cfg = yaml.safe_load(p.read_text(encoding="utf-8"))
                return len(cfg.get("businesses") or [])
            except Exception:
                return None
    return None


def fmt_duration(seconds):
    if seconds is None or seconds < 0:
        return "?"
    return str(timedelta(seconds=int(seconds)))


def snapshot(conn):
    cur = conn.cursor()
    places = cur.execute("SELECT COUNT(*) FROM places").fetchone()[0]
    reviews = cur.execute(
        "SELECT COUNT(*) FROM reviews WHERE COALESCE(is_deleted,0)=0"
    ).fetchone()[0]
    last = cur.execute(
        "SELECT place_name, last_scraped FROM places "
        "WHERE last_scraped IS NOT NULL "
        "ORDER BY last_scraped DESC LIMIT 1"
    ).fetchone()
    return places, reviews, last


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--every", type=int, default=10, help="Yenileme aralığı (sn)")
    args = ap.parse_args()

    db = find_db()
    if not db:
        print("HATA: inci_aku_reviews.db bulunamadı.", file=sys.stderr)
        sys.exit(1)
    total = find_config_total()

    print(f"DB: {db}")
    print(f"Hedef: {total or '?'} bayi")
    print(f"Yenileme: {args.every} sn  (Ctrl+C ile çık)\n")

    start_time = time.time()
    start_places = None
    try:
        while True:
            try:
                conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
                places, reviews, last = snapshot(conn)
                conn.close()
            except sqlite3.OperationalError as e:
                print(f"\r[DB locked - retry] {e}", end="", flush=True)
                time.sleep(args.every)
                continue

            if start_places is None:
                start_places = places
                start_reviews = reviews

            elapsed = time.time() - start_time
            done_since_start = max(places - start_places, 0)
            rate = done_since_start / elapsed if elapsed > 0 else 0
            avg_reviews = (reviews / places) if places > 0 else 0
            pct = (places / total * 100) if total else 0
            remaining = total - places if total else None
            eta_sec = (remaining / rate) if (rate > 0 and remaining is not None) else None

            now = datetime.now().strftime("%H:%M:%S")
            last_name = last[0] if last else "?"
            last_time = last[1] if last else "?"

            # Tek satır clear + bilgi blok
            print("\033[H\033[J", end="")  # ekran temizle
            print(f"=== {now}  |  geçen süre {fmt_duration(elapsed)} ===")
            print()
            print(f"  Bayiler        : {places:>4} / {total or '?'}  ({pct:5.1f}%)")
            print(f"  Yorumlar       : {reviews:>4}  (bayi başına ort {avg_reviews:.1f})")
            print(f"  Hız            : {rate * 60:.2f} bayi/dakika")
            print(f"  Tahmini kalan  : {fmt_duration(eta_sec)}")
            print(f"  Tahmini bitiş  : {(datetime.now() + timedelta(seconds=eta_sec)).strftime('%H:%M') if eta_sec else '?'}")
            print()
            print(f"  Son bayi       : {last_name[:60]}")
            print(f"  Son güncelleme : {last_time}")
            print()
            print(f"  (yenileme {args.every}sn, Ctrl+C ile çık)")

            time.sleep(args.every)
    except KeyboardInterrupt:
        print("\n\nÇıkıldı.")


if __name__ == "__main__":
    main()
