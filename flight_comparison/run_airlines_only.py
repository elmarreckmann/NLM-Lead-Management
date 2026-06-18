#!/usr/bin/env python3
"""
Schnell-Script: nur Ryanair, Eurowings & easyJet – kein API-Key, kein Chrome.

Verwendung:
    python run_airlines_only.py
    python run_airlines_only.py --csv meine_ergebnisse.csv
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

from airlines import ALL_AIRLINE_CLIENTS
from analysis import print_summary
from exporter import export_csv, export_html
from utils import get_logger

logger = get_logger("run_airlines")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--csv",  default="flights_mallorca.csv")
    p.add_argument("--html", default="flights_mallorca.html")
    args = p.parse_args()

    print()
    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║  AIRLINE-DIREKT-SUCHE  –  kein API-Key erforderlich            ║")
    print("║  Ryanair · Eurowings · easyJet  →  PMI  Mai/Jun 2026           ║")
    print("╚══════════════════════════════════════════════════════════════════╝")
    print()

    all_offers = []
    for ClientClass in ALL_AIRLINE_CLIENTS:
        name = ClientClass.SOURCE_NAME
        print(f"  ⟳  {name} …", flush=True)
        try:
            client = ClientClass()
            batch = client.search_all()
            all_offers.extend(batch)
            print(f"  ✓  {name}: {len(batch)} Angebote")
        except Exception as exc:
            print(f"  ✗  {name}: Fehler – {exc}")

    if not all_offers:
        print("\n[!] Keine Ergebnisse. Mögliche Ursachen:")
        print("    • Kein Internet / Firewall")
        print("    • Airline blockiert Requests")
        print("    → Versuche es von einem anderen Netzwerk / mit VPN")
        sys.exit(1)

    # Build DataFrame
    rows = [
        {
            "abflughafen":    o.abflughafen,
            "abflugdatum":    o.abflugdatum,
            "abflugzeit":     o.abflugzeit,
            "rueckflugdatum": o.rueckflugdatum,
            "rueckflugzeit":  o.rueckflugzeit,
            "airline":        o.airline,
            "direktflug":     o.direktflug,
            "zwischenstopps": o.zwischenstopps,
            "preis_eur":      o.preis_eur,
            "quelle":         o.quelle,
            "buchungs_url":   o.buchungs_url,
            "abgerufen_am":   o.abgerufen_am,
        }
        for o in all_offers
    ]
    df = pd.DataFrame(rows).sort_values("preis_eur").drop_duplicates(
        subset=["abflughafen","abflugdatum","rueckflugdatum","airline"],
        keep="first"
    ).reset_index(drop=True)

    export_csv(df, args.csv)
    export_html(df, args.html)
    print_summary(df)

    print(f"\nGespeichert:")
    print(f"  CSV : {Path(args.csv).resolve()}")
    print(f"  HTML: {Path(args.html).resolve()}")
    print()


if __name__ == "__main__":
    main()
