"""manual_review.csv satırlarını terminal'de tek tek gözden geçir.

Her bayi için:
  1. inciaku adı, Google'ın yakaladığı ad, skor, URL gösterilir
  2. webbrowser.open() ile Google Maps URL'i tarayıcıda açılır
  3. Sen karar verirsin: (Y)es, (N)o, (O)verride URL, (S)kip, (Q)uit

CSV her seçimden sonra **anında** kaydedilir. Ctrl+C / Q ile her an
çıkabilirsin, kalan yerden devam ederim.

Çoktan approved=Y veya N olan satırlar atlanır.

Kullanım:
    python 6_manual_review_helper.py
    python 6_manual_review_helper.py --only-low      # sadece low confidence
    python 6_manual_review_helper.py --only-medium   # sadece medium
"""

import argparse
import csv
import json
import sys
import webbrowser
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
CSV_PATH = DATA_DIR / "manual_review.csv"
DEALERS_PATH = DATA_DIR / "dealers.json"


def load_sehir_lookup():
    """dealers.json'dan dealer_id veya firma_adi+ilce → sehir map'i.
    CSV'de eski format kullanılıyorsa (sehir kolonu yok) fallback."""
    if not DEALERS_PATH.exists():
        return {}
    try:
        dealers = json.loads(DEALERS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    lookup = {}
    for d in dealers:
        sehir = d.get("sehir") or ""
        if not sehir:
            continue
        if d.get("id"):
            lookup[d["id"]] = sehir
        firma = d.get("firma_adi") or ""
        ilce = d.get("ilce") or ""
        lookup[f"{firma}|{ilce}"] = sehir
    return lookup


def read_csv():
    if not CSV_PATH.exists():
        print(f"HATA: {CSV_PATH} yok.", file=sys.stderr)
        sys.exit(1)
    text = CSV_PATH.read_text(encoding="utf-8-sig")
    lines = text.splitlines()
    if not lines:
        return [], ","
    delim = ";" if ";" in lines[0] else ","
    rows = list(csv.DictReader(lines, delimiter=delim))
    return rows, delim


def write_csv(rows, delim):
    if not rows:
        return
    fields = list(rows[0].keys())
    with CSV_PATH.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter=delim)
        w.writeheader()
        w.writerows(rows)


def google_search_url(firma_adi, ilce):
    """Yakaladığımız google_url yanlışsa, alternatif arama için kullanıcı
    tarayıcıda Google Maps ana sayfasında elle arayabilir."""
    from urllib.parse import quote
    q = quote(f"{firma_adi} {ilce or ''}".strip())
    return f"https://www.google.com/maps/search/?api=1&query={q}"


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--only-low", action="store_true", help="Sadece low confidence")
    ap.add_argument("--only-medium", action="store_true", help="Sadece medium confidence")
    ap.add_argument("--no-browser", action="store_true",
                    help="Tarayıcıyı otomatik açma (URL'i sen kopyalarsın)")
    args = ap.parse_args()

    rows, delim = read_csv()
    if not rows:
        print("CSV boş.")
        return

    sehir_lookup = load_sehir_lookup()

    def get_sehir(row):
        """CSV'de sehir varsa onu, yoksa dealers.json'dan fallback."""
        s = (row.get("sehir") or "").strip()
        if s:
            return s
        # Önce dealer_id ile dene
        if row.get("dealer_id") and row["dealer_id"] in sehir_lookup:
            return sehir_lookup[row["dealer_id"]]
        # firma_adi + ilce kombinasyonu
        key = f"{row.get('firma_adi', '')}|{row.get('ilce', '')}"
        return sehir_lookup.get(key, "?")

    # Pending = approved boş veya kafa karıştırıcı bir şey
    def is_pending(r):
        v = (r.get("approved") or "").strip().upper()
        return v not in ("Y", "N")

    pending = [r for r in rows if is_pending(r)]
    if args.only_low:
        pending = [r for r in pending if r.get("match_confidence") == "low"]
    elif args.only_medium:
        pending = [r for r in pending if r.get("match_confidence") == "medium"]

    print(f"Toplam {len(rows)} satır CSV'de, {len(pending)} işlenmeyi bekliyor.")
    if not pending:
        print("Tümü zaten karar verilmiş.")
        return
    print("\nKomutlar:")
    print("  Y  → onay (mevcut google_url kullanılır)")
    print("  N  → reddet (atılır)")
    print("  O  → yeni URL yapıştır (override) + onay")
    print("  M  → Google Maps'te yeniden ara (tarayıcı açar)")
    print("  S  → sonra (atla, sıradakine geç)")
    print("  Q  → çık (mevcut ilerleme kaydedildi)")
    print()

    for i, row in enumerate(pending, 1):
        print("=" * 88)
        print(f"[{i}/{len(pending)}]  {row.get('firma_adi','?')}")
        print(f"  Şehir / İlçe : {get_sehir(row)} / {row.get('ilce', '?')}")
        print(f"  Confidence   : {row.get('match_confidence', '?')}  "
              f"(score={row.get('score', '?')})")
        gn = row.get('google_name') or "?"
        print(f"  Google adı   : {gn}")
        url = row.get("google_url") or ""
        print(f"  Google URL   : {url[:110]}")
        gphone = row.get("google_phone") or ""
        if gphone:
            print(f"  Google tel   : {gphone}")
        pm = row.get("phone_match")
        if pm and str(pm).lower() == "true":
            print(f"  ⚠ Telefon eşleşmesi var — büyük olasılıkla doğru bayi")
        print()

        if url and not args.no_browser:
            try:
                webbrowser.open(url, new=2)
            except Exception as e:
                print(f"  (tarayıcı açılamadı: {e})")

        while True:
            try:
                choice = input("  > Y/N/O/M/S/Q ? ").strip().upper()
            except (EOFError, KeyboardInterrupt):
                print("\n  Çıkılıyor, mevcut ilerleme kaydedildi.")
                write_csv(rows, delim)
                return
            if choice in ("Y", "N", "S", "Q"):
                break
            if choice == "M":
                search = google_search_url(row.get("firma_adi", ""), row.get("ilce", ""))
                print(f"    Yeniden arama: {search}")
                try:
                    webbrowser.open(search, new=2)
                except Exception:
                    pass
                continue  # sor tekrar
            if choice == "O":
                new_url = input("    Yeni Maps URL: ").strip()
                if new_url:
                    row["override_url"] = new_url
                    row["approved"] = "Y"
                    break
                print("    Boş bırakıldı, atla.")
                continue
            print("    Anlaşılmadı; Y/N/O/M/S/Q içinden seç.")

        if choice == "Q":
            write_csv(rows, delim)
            print("\nÇıkıldı. CSV güncel.")
            return
        if choice == "Y":
            row["approved"] = "Y"
        elif choice == "N":
            row["approved"] = "N"
        # S = boş bırak (pending kalır)

        write_csv(rows, delim)
        print()

    print("=" * 88)
    print(f"Tamam — {len(pending)} satır gözden geçirildi.")
    yes_count = sum(1 for r in rows if (r.get("approved") or "").upper() == "Y")
    no_count = sum(1 for r in rows if (r.get("approved") or "").upper() == "N")
    print(f"  approved=Y : {yes_count}")
    print(f"  approved=N : {no_count}")
    print(f"  hala boş   : {len(rows) - yes_count - no_count}")
    print("\nSonraki: python gen_config.py")


if __name__ == "__main__":
    main()
