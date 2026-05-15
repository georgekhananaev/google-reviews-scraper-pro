"""inci_aku_config.yaml'ı N parçaya böl ki paralel scrape edilebilsin.

Tüm parçalar aynı db_path'i kullanır → repo'nun SQLite WAL mode'u
sayesinde paralel yazma sorunsuz (concurrent readers + 1 writer).

Kullanım:
    python 7_split_config.py            # default 5 parça
    python 7_split_config.py -n 3       # 3 parça
    python 7_split_config.py --max-reviews 30  # her parça için max_reviews override

Çıktı: inci_aku_config_part_1.yaml, _part_2.yaml, ... (config dosyasının yanına)
"""

import argparse
import sys
from pathlib import Path

import yaml


def find_config():
    for p in (Path.cwd() / "inci_aku_config.yaml",
              Path.cwd().parent / "inci_aku_config.yaml",
              Path.cwd().parent.parent / "inci_aku_config.yaml",
              Path(__file__).parent.parent / "inci_aku_config.yaml"):
        if p.exists():
            return p
    return None


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("-n", "--num-parts", type=int, default=5,
                    help="Kaç parçaya bölünsün (default 5)")
    ap.add_argument("--max-reviews", type=int,
                    help="Her parça için max_reviews override")
    ap.add_argument("--after", help="Date filter, örn 2023-01-01")
    args = ap.parse_args()

    config_path = find_config()
    if not config_path:
        print("HATA: inci_aku_config.yaml bulunamadı. Önce gen_config.py.",
              file=sys.stderr)
        sys.exit(1)

    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    businesses = config.get("businesses") or []
    if not businesses:
        print("HATA: config'de businesses listesi yok.", file=sys.stderr)
        sys.exit(1)

    n = max(1, args.num_parts)
    if n > len(businesses):
        n = len(businesses)
        print(f"Uyarı: parça sayısı bayi sayısına düşürüldü → {n}")

    # Pay düzgün olsun, round-robin değil basit slice
    size = (len(businesses) + n - 1) // n
    print(f"{len(businesses)} bayi → {n} parça (her parça ~{size} bayi)")
    print(f"Hedef klasör: {config_path.parent}")
    print()

    # Override'lar
    if args.max_reviews is not None:
        config["max_reviews"] = args.max_reviews
        print(f"Override max_reviews={args.max_reviews}")
    if args.after:
        df = config.setdefault("date_filter", {})
        df["after"] = args.after
        df.setdefault("mode", "early_stop")
        print(f"Override date_filter.after={args.after} (early_stop mode)")

    out_files = []
    for i in range(n):
        start, end = i * size, min((i + 1) * size, len(businesses))
        if start >= end:
            break
        shard_config = {k: v for k, v in config.items() if k != "businesses"}
        shard_config["businesses"] = businesses[start:end]
        out_path = config_path.parent / f"inci_aku_config_part_{i + 1}.yaml"
        out_path.write_text(
            yaml.safe_dump(shard_config, allow_unicode=True, sort_keys=False, width=120),
            encoding="utf-8",
        )
        out_files.append((out_path, end - start))
        print(f"  → {out_path.name}  ({end - start} bayi, [{start}:{end}])")

    print()
    print(f"PowerShell paralel başlatma örneği ({len(out_files)} job):")
    print("```")
    print(f"cd c:\\Users\\stjot2\\Desktop\\scraper-repo")
    for p, _ in out_files:
        print(f"Copy-Item {p} .")
    print()
    print("$jobs = @()")
    for i, (p, _) in enumerate(out_files, 1):
        print(f"$jobs += Start-Job -ScriptBlock {{")
        print(f"  $env:PYTHONIOENCODING = 'utf-8'")
        print(f"  cd c:\\Users\\stjot2\\Desktop\\scraper-repo")
        print(f"  c:\\Users\\stjot2\\Desktop\\denemer\\.venv\\Scripts\\python.exe "
              f"start.py scrape --config {p.name}")
        print(f"}}")
    print()
    print("while ($jobs | Where-Object State -eq 'Running') {")
    print("    Start-Sleep -Seconds 120")
    print(f"    Write-Host \"--- $((Get-Date).ToString('HH:mm:ss')) ---\"")
    print("    $jobs | Format-Table Id, State")
    print("}")
    print("Write-Host 'Tum scrape bitti.'")
    print("```")


if __name__ == "__main__":
    main()
