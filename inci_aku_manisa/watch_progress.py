"""Scrape'in canlı ilerlemesini başka PowerShell'de göster (Rich dashboard).

Üç panel:
  - Üstte: hedef + progress bar (bayi sayısı / yüzde)
  - Ortada: istatistik (hız, ort yorum, akü-marka yorum sayısı, ETA)
  - Altta: son scrape edilen 10 bayinin tablosu (yorum sayılarıyla)

Read-only SQLite bağlantısı kullandığı için scrape'e hiç dokunmaz.

Kullanım:
    python watch_progress.py            # 5 sn yenileme
    python watch_progress.py --every 3  # 3 sn yenileme
    python watch_progress.py --no-live  # tek snapshot, çıkar
"""

import argparse
import sqlite3
import sys
import time
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path

import yaml
from rich.align import Align
from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TextColumn
from rich.table import Table
from rich.text import Text


# inci akü, EAS akü, Hugel akü markaları (NFKD normalize ile her yazımı yakalar)
BATTERY_BRANDS = [
    "inci akü",
    "inciaku",
    "eas akü",
    "eas akümülatör",
    "hugel akü",
]


def _tr_fold(s: str) -> str:
    if not s:
        return ""
    s = s.lower()
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


def review_has_brand(text: str) -> bool:
    if not text:
        return False
    low = _tr_fold(text)
    return any(_tr_fold(b) in low for b in BATTERY_BRANDS)


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


def find_total_dealers():
    for p in (
        Path(r"c:\Users\stjot2\Desktop\inci_aku_config.yaml"),
        Path(r"c:\Users\stjot2\Desktop\scraper-repo\inci_aku_config.yaml"),
        Path.cwd() / "inci_aku_config.yaml",
        Path.cwd().parent / "inci_aku_config.yaml",
    ):
        if p.exists():
            try:
                cfg = yaml.safe_load(p.read_text(encoding="utf-8"))
                return len(cfg.get("businesses") or [])
            except Exception:
                pass
    return 0


def fmt_duration(seconds):
    if seconds is None or seconds < 0:
        return "—"
    if seconds < 60:
        return f"{int(seconds)}s"
    td = timedelta(seconds=int(seconds))
    return str(td)


def query_snapshot(conn):
    """DB'den anlık veri."""
    cur = conn.cursor()
    places = cur.execute("SELECT COUNT(*) FROM places").fetchone()[0]
    reviews_total = cur.execute(
        "SELECT COUNT(*) FROM reviews WHERE COALESCE(is_deleted,0)=0"
    ).fetchone()[0]

    # Akü markası geçen yorum sayısı
    battery_count = 0
    if reviews_total > 0:
        # Sample değil, tam tarama (DB'miz küçük)
        for (text,) in cur.execute(
            "SELECT review_text FROM reviews WHERE COALESCE(is_deleted,0)=0"
        ):
            if review_has_brand(text or ""):
                battery_count += 1

    # Son 10 bayi (her birinin yorum sayısı)
    recent = cur.execute(
        """
        SELECT p.place_name,
               p.last_scraped,
               COUNT(CASE WHEN COALESCE(r.is_deleted,0)=0 THEN 1 END) AS nrev
        FROM places p
        LEFT JOIN reviews r ON r.place_id = p.place_id
        WHERE p.last_scraped IS NOT NULL
        GROUP BY p.place_id
        ORDER BY p.last_scraped DESC
        LIMIT 10
        """
    ).fetchall()

    return {
        "places": places,
        "reviews_total": reviews_total,
        "battery_count": battery_count,
        "recent": recent,
    }


def make_progress_bar(places, total):
    pct = (places / total * 100) if total else 0
    pb = Progress(
        TextColumn("[bold cyan]Bayiler", justify="left"),
        BarColumn(bar_width=None, complete_style="green", finished_style="bold green"),
        TextColumn("[bold]{task.completed}/{task.total}"),
        TextColumn(f"[yellow]({pct:.1f}%)"),
        expand=True,
    )
    pb.add_task("bayiler", total=total or 1, completed=places)
    return pb


def make_stats_panel(snap, total, elapsed, rate):
    places = snap["places"]
    reviews = snap["reviews_total"]
    battery = snap["battery_count"]
    avg = (reviews / places) if places else 0
    bat_pct = (battery / reviews * 100) if reviews else 0
    remaining = (total - places) if total else None
    eta_sec = (remaining / rate) if (rate > 0 and remaining is not None) else None
    eta_dt = (datetime.now() + timedelta(seconds=eta_sec)) if eta_sec else None

    t = Table.grid(padding=(0, 2), expand=True)
    t.add_column(style="bold cyan", justify="right", ratio=1)
    t.add_column(style="white", ratio=2)
    t.add_column(style="bold cyan", justify="right", ratio=1)
    t.add_column(style="white", ratio=2)

    t.add_row(
        "Toplam yorum:", f"[bold yellow]{reviews}",
        "Geçen:", fmt_duration(elapsed),
    )
    t.add_row(
        "Ort/bayi:", f"{avg:.1f}",
        "Kalan:", fmt_duration(eta_sec),
    )
    t.add_row(
        "Akü markası:", f"[bold green]{battery}  [dim]({bat_pct:.1f}%)",
        "Tahmini bitiş:", eta_dt.strftime("%H:%M") if eta_dt else "—",
    )
    t.add_row(
        "Hız:", f"{rate * 60:.2f} bayi/dk",
        "", "",
    )
    return Panel(t, title="📊 İstatistik", border_style="cyan", padding=(1, 2))


def make_recent_panel(recent):
    table = Table(
        expand=True, show_lines=False, box=None,
        title_style="bold", title="🕐 Son scrape edilen 10 bayi",
    )
    table.add_column("Saat", style="dim", width=10)
    table.add_column("Bayi", style="white", overflow="ellipsis")
    table.add_column("Yorum", style="bold yellow", justify="right", width=8)

    if not recent:
        table.add_row("—", "(henüz scrape edilmiş bayi yok)", "—")
    else:
        for name, ts, nrev in recent:
            try:
                tt = datetime.fromisoformat((ts or "").replace("Z", "+00:00")).strftime("%H:%M:%S")
            except Exception:
                tt = (ts or "")[:8]
            table.add_row(tt, (name or "?")[:55], str(nrev))

    return Panel(table, border_style="blue", padding=(0, 1))


def render(snap, total, elapsed, rate):
    progress = make_progress_bar(snap["places"], total)
    header_panel = Panel(
        progress,
        title=f"🔋 İnci Akü Scrape — {datetime.now().strftime('%H:%M:%S')}",
        border_style="bold magenta",
        padding=(0, 1),
    )
    return Group(
        header_panel,
        make_stats_panel(snap, total, elapsed, rate),
        make_recent_panel(snap["recent"]),
        Align.center(
            Text("⏱  Otomatik yenileniyor   ·   Ctrl+C ile çık", style="dim"),
        ),
    )


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--every", type=int, default=5, help="Yenileme aralığı (sn)")
    ap.add_argument("--no-live", action="store_true",
                    help="Tek snapshot bas ve çık")
    args = ap.parse_args()

    db = find_db()
    if not db:
        Console().print("[red]HATA: inci_aku_reviews.db bulunamadı.[/]", file=sys.stderr)
        sys.exit(1)
    total = find_total_dealers()
    console = Console()

    if args.no_live:
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        snap = query_snapshot(conn)
        conn.close()
        console.print(render(snap, total, 0, 0))
        return

    start_time = time.time()
    start_places = None
    try:
        with Live(console=console, refresh_per_second=2, screen=True) as live:
            while True:
                try:
                    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
                    snap = query_snapshot(conn)
                    conn.close()
                except sqlite3.OperationalError:
                    time.sleep(1)
                    continue

                if start_places is None:
                    start_places = snap["places"]

                elapsed = time.time() - start_time
                done = max(snap["places"] - start_places, 0)
                rate = done / elapsed if elapsed > 0 else 0
                live.update(render(snap, total, elapsed, rate))
                time.sleep(args.every)
    except KeyboardInterrupt:
        console.print("\n[dim]Çıkıldı.[/]")


if __name__ == "__main__":
    main()
