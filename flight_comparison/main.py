#!/usr/bin/env python3
"""
Flugpreisvergleich: PAD / HAJ / DUS  →  Palma de Mallorca (PMI)
Mai–Juni 2026  |  7–10 Nächte  |  1 Erwachsener

Verwendung:
    python main.py                         # alle Quellen
    python main.py --no-scraping           # nur APIs
    python main.py --no-amadeus --no-duffel  # nur Scraper
    python main.py --csv ergebnis.csv --html ergebnis.html
"""

import argparse
import sys
from pathlib import Path

from aggregator import collect_all_offers
from analysis import print_summary
from exporter import export_csv, export_html
from utils import get_logger

logger = get_logger("main")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Flugpreisvergleich PAD/HAJ/DUS → PMI (Mai–Jun 2026)"
    )
    p.add_argument("--no-amadeus",  action="store_true", help="Amadeus API überspringen")
    p.add_argument("--no-duffel",   action="store_true", help="Duffel API überspringen")
    p.add_argument("--no-scraping", action="store_true", help="Alle Web-Scraper überspringen")
    p.add_argument("--csv",  default="flights_mallorca.csv",  metavar="DATEI",
                   help="Ausgabedatei für CSV (Standard: flights_mallorca.csv)")
    p.add_argument("--html", default="flights_mallorca.html", metavar="DATEI",
                   help="Ausgabedatei für HTML (Standard: flights_mallorca.html)")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    use_amadeus  = not args.no_amadeus
    use_duffel   = not args.no_duffel
    use_scrapers = not args.no_scraping

    _print_banner(use_amadeus, use_duffel, use_scrapers)

    # --- Collect ---
    df = collect_all_offers(
        use_amadeus=use_amadeus,
        use_duffel=use_duffel,
        use_scrapers=use_scrapers,
        progress_cb=_progress,
    )

    if df.empty:
        print("\n[!] Keine Flugdaten gesammelt. Prüfe API-Keys und Netzwerk.")
        sys.exit(1)

    # --- Export ---
    csv_path  = args.csv
    html_path = args.html

    export_csv(df,  csv_path)
    export_html(df, html_path)

    # --- Console summary ---
    print_summary(df)

    print(f"\nDateien gespeichert:")
    print(f"  CSV : {Path(csv_path).resolve()}")
    print(f"  HTML: {Path(html_path).resolve()}")
    print("\nÖffne die HTML-Datei im Browser für die interaktive Ansicht.\n")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _progress(msg: str) -> None:
    print(f"  ⟳  {msg}", flush=True)


def _print_banner(amadeus: bool, duffel: bool, scrapers: bool) -> None:
    print()
    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║        FLUGPREISVERGLEICH  –  Mai / Juni 2026                   ║")
    print("║        PAD / HAJ / DUS  →  Palma de Mallorca (PMI)             ║")
    print("╚══════════════════════════════════════════════════════════════════╝")
    print()
    print("Aktive Quellen:")
    print(f"  {'✓' if amadeus  else '✗'}  Amadeus API")
    print(f"  {'✓' if duffel   else '✗'}  Duffel API")
    print(f"  {'✓' if scrapers else '✗'}  Web-Scraper (Google Flights, Kayak, Skyscanner,")
    print( "                           Check24, Fluege.de, Idealo)")
    print()
    print("Suche läuft … (das kann 10–30 Minuten dauern)")
    print()


if __name__ == "__main__":
    main()
