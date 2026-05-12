"""Aşama 2: Bayi adı → Google Maps URL eşlemesi (karma yaklaşım).

Her bayi için Google Maps'te '{temiz_ad} {ilçe} {şehir}' aranır,
/maps/place/ URL'i ve işletme adı çekilir. İsim benzerliğine göre 3 kova:

  high   → urls_auto.json (otomatik onaylı)
  medium → manual_review.csv (manuel onay gerekli)
  low    → manual_review.csv (manuel onay gerekli)

Resume: data/urls_resolved_raw.json mevcutsa orada bulunan bayiler atlanır.
Sıfırdan başlamak için bu dosyayı sil.

Kullanım:
    python inci_aku_manisa/2_resolve_urls.py             # tüm bayiler
    python inci_aku_manisa/2_resolve_urls.py --headless  # arka planda
    python inci_aku_manisa/2_resolve_urls.py --limit 5   # test için 5 bayi
"""

import argparse
import csv
import json
import re
import sys
import time
from pathlib import Path

# Komut satırından çalışınca paket içindeki kardeş modüller import edilebilsin
sys.path.insert(0, str(Path(__file__).parent))
from name_utils import clean_dealer_name, match_confidence  # noqa: E402

from seleniumbase import SB  # noqa: E402

DATA_DIR = Path(__file__).parent / "data"
DEALERS_PATH = DATA_DIR / "dealers.json"
RAW_PATH = DATA_DIR / "urls_resolved_raw.json"
AUTO_PATH = DATA_DIR / "urls_auto.json"
MANUAL_CSV_PATH = DATA_DIR / "manual_review.csv"

NAV_TIMEOUT_S = 12
COOKIE_LABELS = ("Tümünü kabul et", "Hepsini kabul et", "Tümünü reddet", "Accept all")


def dealer_key(d):
    return d.get("id") or f"{d['firma_adi']}|{d.get('ilce') or ''}"


def accept_cookies(sb):
    for label in COOKIE_LABELS:
        try:
            sb.click(f'button:contains("{label}")', timeout=2)
            sb.sleep(0.8)
            return
        except Exception:
            continue


def wait_for_place(sb, total_timeout=NAV_TIMEOUT_S):
    """Maps arama sonrası /maps/place/ URL'i veya liste görünümünü bekle.
    Liste görünümündeyse ilk sonuca tıkla.
    """
    deadline = time.time() + total_timeout
    while time.time() < deadline:
        url = sb.get_current_url()
        if "/maps/place/" in url:
            return True
        # Liste görünümü: a.hfpxzc ilk sonuç linki
        try:
            if sb.is_element_visible("a.hfpxzc"):
                sb.click("a.hfpxzc", timeout=3)
                # Tıklama sonrası place URL'ine geçişi bekle
                inner_deadline = time.time() + 6
                while time.time() < inner_deadline:
                    if "/maps/place/" in sb.get_current_url():
                        return True
                    time.sleep(0.3)
                break
        except Exception:
            pass
        time.sleep(0.4)
    return "/maps/place/" in sb.get_current_url()


def get_place_name(sb):
    """İşletme panelinden gerçek adı al. 'Sonuçlar' liste başlığını atla."""
    try:
        names = sb.execute_script(
            """
            const out = [];
            document.querySelectorAll('h1').forEach(h => {
                const t = (h.innerText || '').trim();
                if (t) out.push(t);
            });
            return out;
            """
        ) or []
        for n in names:
            if n and n not in ("Sonuçlar", "Results"):
                return n
    except Exception:
        pass
    return None


def resolve_one(sb, query):
    """Tek bir bayi için arama yap, URL + ad döndür."""
    search_url = (
        "https://www.google.com/maps/search/?api=1&hl=tr&query="
        + re.sub(r"\s+", "+", query.strip())
    )
    sb.open(search_url)
    sb.sleep(2.0)
    accept_cookies(sb)
    sb.sleep(1.0)

    on_place = wait_for_place(sb)
    current = sb.get_current_url()
    if not on_place:
        return {"google_url": None, "google_name": None, "final_url": current}

    sb.sleep(1.0)  # panel yüklemesi
    return {
        "google_url": current,
        "google_name": get_place_name(sb),
        "final_url": current,
    }


def load_raw():
    if RAW_PATH.exists():
        return json.loads(RAW_PATH.read_text(encoding="utf-8"))
    return {}


def save_raw(raw):
    RAW_PATH.write_text(
        json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def build_outputs(raw, dealers):
    """Raw resolution sonuçlarını high/medium/low kovalarına ayır."""
    auto = []
    manual = []
    for d in dealers:
        key = dealer_key(d)
        entry = raw.get(key)
        if not entry:
            continue
        cleaned = clean_dealer_name(d["firma_adi"])
        confidence, sim, common = match_confidence(cleaned, entry.get("google_name"))
        record = {
            "dealer_id": key,
            "firma_adi": d["firma_adi"],
            "cleaned_name": cleaned,
            "ilce": d.get("ilce"),
            "sehir": d.get("sehir"),
            "kategori": d.get("kategori"),
            "google_name": entry.get("google_name"),
            "google_url": entry.get("google_url"),
            "name_sim": round(sim, 3),
            "match_confidence": confidence,
            "common_words": common,
        }
        if confidence == "high":
            auto.append(record)
        else:
            manual.append(record)
    return auto, manual


def write_outputs(auto, manual):
    AUTO_PATH.write_text(
        json.dumps(auto, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    fields = [
        "dealer_id", "firma_adi", "cleaned_name", "ilce", "kategori",
        "google_name", "google_url", "name_sim", "match_confidence",
        "approved", "override_url",
    ]
    with MANUAL_CSV_PATH.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in manual:
            w.writerow({
                "dealer_id": r["dealer_id"],
                "firma_adi": r["firma_adi"],
                "cleaned_name": r["cleaned_name"],
                "ilce": r["ilce"] or "",
                "kategori": r["kategori"] or "",
                "google_name": r["google_name"] or "",
                "google_url": r["google_url"] or "",
                "name_sim": r["name_sim"],
                "match_confidence": r["match_confidence"],
                "approved": "",     # Y / N — sen doldur
                "override_url": "", # doğru Maps URL'i biliyorsan yapıştır
            })


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="0 = limitsiz")
    ap.add_argument("--sleep", type=float, default=2.5, help="bayiler arası gecikme (sn)")
    args = ap.parse_args()

    if not DEALERS_PATH.exists():
        print(f"HATA: {DEALERS_PATH} yok. Önce 1_fetch_dealers.py çalıştır.",
              file=sys.stderr)
        sys.exit(1)

    dealers = json.loads(DEALERS_PATH.read_text(encoding="utf-8"))
    if args.limit:
        dealers = dealers[:args.limit]

    raw = load_raw()
    todo = [d for d in dealers if dealer_key(d) not in raw]
    print(f"Toplam: {len(dealers)} | önceden çözülmüş: {len(raw)} | yapılacak: {len(todo)}")

    if todo:
        with SB(uc=True, locale="tr", headless=args.headless) as sb:
            for i, d in enumerate(todo, 1):
                cleaned = clean_dealer_name(d["firma_adi"])
                ilce = d.get("ilce") or ""
                sehir = d.get("sehir") or "Manisa"
                query = re.sub(r"\s+", " ", f"{cleaned} {ilce} {sehir}").strip()
                print(f"[{i}/{len(todo)}] {d['firma_adi'][:50]} → q={query!r}")
                try:
                    result = resolve_one(sb, query)
                    confidence, sim, _ = match_confidence(cleaned, result.get("google_name"))
                    print(f"    → {result.get('google_name')!r} "
                          f"[{confidence} sim={sim:.2f}]")
                    raw[dealer_key(d)] = {
                        **result,
                        "query": query,
                        "cleaned_name": cleaned,
                    }
                except Exception as e:
                    print(f"    ✗ HATA: {e}")
                    raw[dealer_key(d)] = {
                        "google_url": None, "google_name": None,
                        "error": str(e), "query": query,
                    }
                save_raw(raw)
                if i < len(todo):
                    time.sleep(args.sleep)

    auto, manual = build_outputs(raw, dealers)
    write_outputs(auto, manual)
    print(f"\n[done]")
    print(f"  auto (high confidence)  : {len(auto):3d} → {AUTO_PATH}")
    print(f"  manual review needed    : {len(manual):3d} → {MANUAL_CSV_PATH}")
    print(f"\nŞimdi {MANUAL_CSV_PATH.name} dosyasını aç, her satır için:")
    print("  - google_url doğruysa  → approved=Y")
    print("  - yanlış işletme       → approved=N")
    print("  - başka URL biliyorsan → override_url'e yapıştır, approved=Y")
    print("Sonra 3_gen_config.py çalıştır.")


if __name__ == "__main__":
    main()
