"""Aşama 2: Bayi → Google Maps URL (multi-signal scoring).

Sinyaller (her bayi için inciaku'da mevcut):
  - koordinat (lat/lng)  → search URL'i koordinat civarına yönlendirir
                          + her adayın mesafesine göre puan
  - telefon              → adayın panelinden okunup karşılaştırılır;
                          eşleşme tek başına high confidence verir
  - isim                 → temizlenmiş bayi adı vs Google işletme adı

Akış:
  1. /maps/search/<q>/@<lat>,<lng>,15z aç (koord-biased)
  2. Sponsor olmayan ilk N organik adayı topla (ad + href'ten lat/lng)
  3. Her aday için (isim+mesafe) ön skor
  4. En iyi adayı tıkla, panel'den telefonu da oku, yeniden skorla
  5. Skora göre auto / manual kovasına ayır

Resume: data/urls_resolved_raw.json mevcutsa atlanır.
Sıfırdan başlamak için bu dosyayı sil.

Kullanım:
    python resolve_urls.py
    python resolve_urls.py --headless
    python resolve_urls.py --limit 5
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
os.environ.setdefault("REQUESTS_CA_BUNDLE", "")
os.environ.setdefault("CURL_CA_BUNDLE", "")

sys.path.insert(0, str(Path(__file__).parent))
from name_utils import clean_dealer_name, normalize_phone, score_candidate  # noqa: E402

from seleniumbase import SB  # noqa: E402

DATA_DIR = Path(__file__).parent / "data"
DEALERS_PATH = DATA_DIR / "dealers.json"
RAW_PATH = DATA_DIR / "urls_resolved_raw.json"
AUTO_PATH = DATA_DIR / "urls_auto.json"
MANUAL_CSV_PATH = DATA_DIR / "manual_review.csv"

MAX_CANDIDATES = 5
PHONE_CHECK_TOPN = 3        # bayide telefon varsa kaç adayda panel kontrolü yapılsın
LIST_WAIT_S = 8
COOKIE_LABELS = ("Tümünü kabul et", "Hepsini kabul et", "Tümünü reddet", "Accept all")
NAME_BLACKLIST = ("Sonuçlar", "Results", "Sponsorlu", "Sponsored", "Reklam")


# ---------------------------------------------------------------------------
# Selenium yardımcıları
# ---------------------------------------------------------------------------

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


_LATLNG_RE = re.compile(r"@(-?\d+\.\d+),(-?\d+\.\d+)")


def parse_latlng(url):
    m = _LATLNG_RE.search(url or "")
    if not m:
        return None, None
    return float(m.group(1)), float(m.group(2))


def collect_candidates(sb):
    """Search liste'sinden sponsor olmayan ilk MAX_CANDIDATES adayı topla.
    Her aday: {idx, href, name, lat, lng}.
    """
    return sb.execute_script(
        """
        const MAX = arguments[0];
        const out = [];
        const links = Array.from(document.querySelectorAll('a.hfpxzc'));
        for (const a of links) {
            const card = a.closest('[role="article"], div[jsaction]') || a.parentElement;
            const txt = ((card && card.innerText) || '').toLowerCase();
            if (txt.includes('sponsorlu') || txt.includes('sponsored')) continue;
            const m = (a.href || '').match(/@(-?\\d+\\.\\d+),(-?\\d+\\.\\d+)/);
            out.push({
                idx: out.length,
                href: a.href,
                name: (a.getAttribute('aria-label') || '').trim(),
                lat: m ? parseFloat(m[1]) : null,
                lng: m ? parseFloat(m[2]) : null,
            });
            if (out.length >= MAX) break;
        }
        return out;
        """,
        MAX_CANDIDATES,
    ) or []


def click_candidate_by_idx(sb, idx):
    """Sponsor olmayan idx. organik sonucu tıkla."""
    return sb.execute_script(
        """
        const target = arguments[0];
        const links = Array.from(document.querySelectorAll('a.hfpxzc'));
        let count = 0;
        for (const a of links) {
            const card = a.closest('[role="article"], div[jsaction]') || a.parentElement;
            const txt = ((card && card.innerText) || '').toLowerCase();
            if (txt.includes('sponsorlu') || txt.includes('sponsored')) continue;
            if (count === target) {
                a.scrollIntoView({block:'center'});
                a.click();
                return true;
            }
            count++;
        }
        return false;
        """,
        idx,
    )


def wait_for_place_url(sb, timeout):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if "/maps/place/" in sb.get_current_url():
            return True
        time.sleep(0.3)
    return "/maps/place/" in sb.get_current_url()


def wait_for_list_or_place(sb, timeout=LIST_WAIT_S):
    """Liste yüklendi veya direkt place'e gittik."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if "/maps/place/" in sb.get_current_url():
            return "place"
        try:
            if sb.is_element_visible("a.hfpxzc"):
                return "list"
        except Exception:
            pass
        time.sleep(0.3)
    return "place" if "/maps/place/" in sb.get_current_url() else "none"


def get_panel_name(sb):
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
    except Exception:
        return None
    for n in names:
        if n and not any(bad in n for bad in NAME_BLACKLIST):
            return n
    return None


def get_panel_phone(sb):
    """İşletme panelinden telefon bilgisini çek (ham metin)."""
    try:
        return sb.execute_script(
            """
            const sels = [
                'button[data-item-id^="phone:"]',
                'button[aria-label^="Telefon:"]',
                'button[aria-label^="Phone:"]',
            ];
            for (const s of sels) {
                const el = document.querySelector(s);
                if (el) {
                    return (el.getAttribute('aria-label') || el.innerText || '').trim();
                }
            }
            return '';
            """
        ) or None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Ana resolve akışı
# ---------------------------------------------------------------------------

def build_search_url(dealer, query):
    """Bayi koordinatı varsa koord-biased URL, yoksa düz arama."""
    encoded = quote(query)
    lat, lng = dealer.get("lat"), dealer.get("lng")
    if lat and lng:
        return f"https://www.google.com/maps/search/{encoded}/@{lat},{lng},15z?hl=tr"
    return f"https://www.google.com/maps/search/?api=1&hl=tr&query={encoded}"


def read_current_panel(sb, fallback_url):
    """Açık place sayfasından (ad, lat, lng, telefon, url) tuple döndür."""
    cur = sb.get_current_url() or fallback_url
    name = get_panel_name(sb)
    phone = get_panel_phone(sb)
    lat, lng = parse_latlng(cur)
    return {"name": name, "lat": lat, "lng": lng, "phone": phone, "url": cur}


def back_to_list(sb, search_url):
    """Place panelinden liste view'a dön. history.back() öncelikli;
    başarısızsa arama URL'ini yeniden açar."""
    try:
        sb.execute_script("history.back()")
    except Exception:
        pass
    deadline = time.time() + 5
    while time.time() < deadline:
        try:
            if sb.is_element_visible("a.hfpxzc"):
                return True
        except Exception:
            pass
        time.sleep(0.3)
    sb.open(search_url)
    sb.sleep(1.5)
    return wait_for_list_or_place(sb) == "list"


def visit_candidate(sb, dealer_with_clean, cand):
    """Adayı tıkla, panel'den (ad, koord, telefon) oku, yeniden skor üret.
    Başarısızsa None döner."""
    if not click_candidate_by_idx(sb, cand["idx"]):
        return None
    if not wait_for_place_url(sb, timeout=8):
        return None
    sb.sleep(1.0)
    panel = read_current_panel(sb, cand.get("href") or "")
    merged = {
        "idx": cand["idx"],
        "name": panel["name"] or cand.get("name"),
        "lat": panel["lat"] if panel["lat"] is not None else cand.get("lat"),
        "lng": panel["lng"] if panel["lng"] is not None else cand.get("lng"),
        "phone": panel["phone"],
        "url": panel["url"],
        "href": cand.get("href"),
    }
    total, conf, bd = score_candidate(dealer_with_clean, merged)
    return {**merged, "score": total, "confidence": conf, "breakdown": bd}


def resolve_one(sb, dealer):
    cleaned = clean_dealer_name(dealer["firma_adi"])
    ilce = dealer.get("ilce") or ""
    sehir = dealer.get("sehir") or "Manisa"
    query = re.sub(r"\s+", " ", f"{cleaned} {ilce} {sehir}").strip()

    sb.open(build_search_url({**dealer, "cleaned_name": cleaned}, query))
    sb.sleep(2.0)
    accept_cookies(sb)
    sb.sleep(1.0)

    state = wait_for_list_or_place(sb)

    # A) Google tek sonuç bulup direkt place'e gittiyse
    if state == "place":
        panel = read_current_panel(sb, "")
        cand = {**panel}
        cand["idx"] = 0
        scored = [{
            **cand,
            **dict(zip(("score", "confidence", "breakdown"),
                       score_candidate({**dealer, "cleaned_name": cleaned}, cand))),
        }]
        best = scored[0]
        return {
            "query": query,
            "cleaned_name": cleaned,
            "google_url": panel["url"],
            "google_name": panel["name"],
            "google_phone": panel["phone"],
            "score": best["score"],
            "confidence": best["confidence"],
            "breakdown": best["breakdown"],
            "all_candidates": scored,
            "mode": "direct_place",
        }

    # B) Liste yok
    if state != "list":
        return {
            "query": query,
            "cleaned_name": cleaned,
            "google_url": None,
            "google_name": None,
            "google_phone": None,
            "score": 0,
            "confidence": "low",
            "breakdown": {},
            "all_candidates": [],
            "mode": "no_results",
        }

    # C) Liste var → adayları topla, ön skorla
    cands = collect_candidates(sb)
    if not cands:
        return {
            "query": query, "cleaned_name": cleaned,
            "google_url": None, "google_name": None, "google_phone": None,
            "score": 0, "confidence": "low", "breakdown": {},
            "all_candidates": [], "mode": "list_empty",
        }

    dealer_with_clean = {**dealer, "cleaned_name": cleaned}
    pre_scored = []
    for c in cands:
        total, conf, bd = score_candidate(dealer_with_clean, c)
        pre_scored.append({**c, "score": total, "confidence": conf, "breakdown": bd})
    pre_scored.sort(key=lambda x: x["score"], reverse=True)

    # D) Bayinin telefonu varsa: ön skor sırasıyla ilk N adayda telefon kontrolü.
    #    Eşleşme bulduğum an dururum; bulamazsam ziyaret edilenler arasından
    #    en yüksek skorlu adayı seçerim. Telefon yoksa eski "best'i tıkla" akışı.
    search_url = build_search_url(dealer_with_clean, query)
    dealer_has_phone = bool(normalize_phone(dealer.get("telefon")))
    visited = []
    phone_winner = None
    mode_tag = "list_pick"

    if dealer_has_phone and pre_scored:
        candidates_to_check = pre_scored[:PHONE_CHECK_TOPN]
        for i, c in enumerate(candidates_to_check):
            visit = visit_candidate(sb, dealer_with_clean, c)
            if visit is None:
                # tıklama veya place geçişi başarısız → sıradakine
                if i < len(candidates_to_check) - 1:
                    back_to_list(sb, search_url)
                continue
            visited.append(visit)
            if visit["breakdown"].get("phone_match"):
                phone_winner = visit
                mode_tag = "phone_match"
                break
            if i < len(candidates_to_check) - 1:
                back_to_list(sb, search_url)

    if phone_winner is not None:
        best = phone_winner
    elif visited:
        best = max(visited, key=lambda x: x["score"])
        mode_tag = "best_visited"
    else:
        # Bayide telefon yok veya hiç ziyaret edemedik → en iyi ön skoru tıkla
        best = pre_scored[0]
        visit = visit_candidate(sb, dealer_with_clean, best)
        if visit is not None:
            best = visit

    return {
        "query": query,
        "cleaned_name": cleaned,
        "google_url": best.get("url") or best.get("href"),
        "google_name": best.get("name"),
        "google_phone": best.get("phone"),
        "score": best["score"],
        "confidence": best["confidence"],
        "breakdown": best["breakdown"],
        "all_candidates": pre_scored,
        "mode": mode_tag,
    }


# ---------------------------------------------------------------------------
# Persist + raporlama
# ---------------------------------------------------------------------------

def load_raw():
    if RAW_PATH.exists():
        return json.loads(RAW_PATH.read_text(encoding="utf-8"))
    return {}


def save_raw(raw):
    RAW_PATH.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")


def build_outputs(raw, dealers):
    auto, manual = [], []
    for d in dealers:
        entry = raw.get(dealer_key(d))
        if not entry:
            continue
        record = {
            "dealer_id": dealer_key(d),
            "firma_adi": d["firma_adi"],
            "cleaned_name": entry.get("cleaned_name") or clean_dealer_name(d["firma_adi"]),
            "ilce": d.get("ilce"),
            "sehir": d.get("sehir"),
            "kategori": d.get("kategori"),
            "google_name": entry.get("google_name"),
            "google_url": entry.get("google_url"),
            "google_phone": entry.get("google_phone"),
            "score": entry.get("score", 0),
            "match_confidence": entry.get("confidence", "low"),
            "breakdown": entry.get("breakdown", {}),
        }
        if record["match_confidence"] == "high" and record["google_url"]:
            auto.append(record)
        else:
            manual.append(record)
    return auto, manual


def write_outputs(auto, manual):
    AUTO_PATH.write_text(json.dumps(auto, ensure_ascii=False, indent=2), encoding="utf-8")
    fields = [
        "dealer_id", "firma_adi", "cleaned_name", "ilce", "kategori",
        "google_name", "google_url", "google_phone",
        "score", "match_confidence",
        "name_pts", "dist_pts", "phone_pts", "dist_km", "phone_match",
        "approved", "override_url",
    ]
    with MANUAL_CSV_PATH.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in manual:
            bd = r.get("breakdown") or {}
            w.writerow({
                "dealer_id": r["dealer_id"],
                "firma_adi": r["firma_adi"],
                "cleaned_name": r["cleaned_name"],
                "ilce": r["ilce"] or "",
                "kategori": r["kategori"] or "",
                "google_name": r["google_name"] or "",
                "google_url": r["google_url"] or "",
                "google_phone": r["google_phone"] or "",
                "score": r["score"],
                "match_confidence": r["match_confidence"],
                "name_pts": bd.get("name_pts", ""),
                "dist_pts": bd.get("dist_pts", ""),
                "phone_pts": bd.get("phone_pts", ""),
                "dist_km": bd.get("dist_km", ""),
                "phone_match": bd.get("phone_match", ""),
                "approved": "",
                "override_url": "",
            })


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--sleep", type=float, default=2.5)
    ap.add_argument("--uc", action="store_true", help="undetected-chromedriver modu")
    args = ap.parse_args()

    if not DEALERS_PATH.exists():
        print(f"HATA: {DEALERS_PATH} yok. Önce 1_fetch_dealers.py.", file=sys.stderr)
        sys.exit(1)

    dealers = json.loads(DEALERS_PATH.read_text(encoding="utf-8"))
    if args.limit:
        dealers = dealers[:args.limit]

    raw = load_raw()
    todo = [d for d in dealers if dealer_key(d) not in raw]
    print(f"Toplam: {len(dealers)} | önceden çözülmüş: {len(raw)} | yapılacak: {len(todo)}")

    if todo:
        with SB(uc=args.uc, locale="tr", headless=args.headless) as sb:
            for i, d in enumerate(todo, 1):
                print(f"[{i}/{len(todo)}] {d['firma_adi'][:60]}")
                try:
                    result = resolve_one(sb, d)
                    bd = result.get("breakdown") or {}
                    print(
                        f"    → {result.get('google_name')!r}\n"
                        f"      score={result['score']} ({result['confidence']})  "
                        f"name={bd.get('name_pts')} dist={bd.get('dist_pts')} "
                        f"phone={bd.get('phone_pts')} d={bd.get('dist_km')}km "
                        f"phone_match={bd.get('phone_match')}  "
                        f"mode={result.get('mode')}"
                    )
                    raw[dealer_key(d)] = result
                except Exception as e:
                    print(f"    ✗ HATA: {e}")
                    raw[dealer_key(d)] = {
                        "google_url": None, "google_name": None,
                        "score": 0, "confidence": "low", "breakdown": {},
                        "error": str(e),
                    }
                save_raw(raw)
                if i < len(todo):
                    time.sleep(args.sleep)

    auto, manual = build_outputs(raw, dealers)
    write_outputs(auto, manual)
    print(f"\n[done]")
    print(f"  auto (high confidence)  : {len(auto):3d} → {AUTO_PATH}")
    print(f"  manual review needed    : {len(manual):3d} → {MANUAL_CSV_PATH}")
    print(f"\nManuel review için {MANUAL_CSV_PATH.name} aç. Score düşükse")
    print("  - yanlış işletme yakalanmış olabilir → approved=N")
    print("  - doğru URL'i biliyorsan override_url'e yapıştır + approved=Y")
    print("\nSonra: python 3_gen_config.py")


if __name__ == "__main__":
    main()
