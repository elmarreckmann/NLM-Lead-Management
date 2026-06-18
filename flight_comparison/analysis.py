"""Analysis helpers: top-N, cheapest per airport, month comparison, direct flights."""

import pandas as pd

from config import TOP_N_RESULTS
from utils import get_logger

logger = get_logger("analysis")

_SEP = "-" * 72


def print_summary(df: pd.DataFrame) -> None:
    if df.empty:
        print("Keine Ergebnisse vorhanden.")
        return

    print(f"\n{'='*72}")
    print(f"  FLUGPREIS-AUSWERTUNG  –  {len(df)} einzigartige Angebote")
    print(f"{'='*72}\n")

    _print_top_n(df)
    _print_cheapest_per_airport(df)
    _print_cheapest_per_month(df)
    _print_cheapest_direct(df)


# ------------------------------------------------------------------
# Individual sections
# ------------------------------------------------------------------

def _print_top_n(df: pd.DataFrame) -> None:
    print(f"TOP {TOP_N_RESULTS} GÜNSTIGSTE ANGEBOTE")
    print(_SEP)
    top = df.nsmallest(TOP_N_RESULTS, "preis_eur")
    for rank, (_, row) in enumerate(top.iterrows(), start=1):
        direct_flag = "✓ Direkt" if row["direktflug"] == "ja" else f"{row['zwischenstopps']} Stopp(s)"
        print(
            f"{rank:>2}. {row['preis_eur']:>7.2f} €  |  "
            f"{row['abflughafen']} → PMI  {row['abflugdatum']}  {row['abflugzeit'] or '??:??'}  |  "
            f"Rück: {row['rueckflugdatum']}  |  "
            f"{row['airline']:<12}  {direct_flag:<14}  |  {row['quelle']}"
        )
    print()


def _print_cheapest_per_airport(df: pd.DataFrame) -> None:
    print("GÜNSTIGSTES ANGEBOT PRO ABFLUGHAFEN")
    print(_SEP)
    for airport, group in df.groupby("abflughafen"):
        row = group.loc[group["preis_eur"].idxmin()]
        direct_flag = "✓ Direkt" if row["direktflug"] == "ja" else f"{row['zwischenstopps']} Stopp(s)"
        print(
            f"  {airport}:  {row['preis_eur']:>7.2f} €  |  "
            f"{row['abflugdatum']}  {row['abflugzeit'] or '??:??'}  →  {row['rueckflugdatum']}  |  "
            f"{row['airline']:<12}  {direct_flag}  |  {row['quelle']}"
        )
    print()


def _print_cheapest_per_month(df: pd.DataFrame) -> None:
    print("GÜNSTIGSTER MONAT (Mai vs. Juni)")
    print(_SEP)

    df2 = df.copy()
    df2["monat"] = pd.to_datetime(df2["abflugdatum"], errors="coerce").dt.month
    monat_map = {5: "Mai 2026", 6: "Juni 2026"}

    for month_num, label in monat_map.items():
        subset = df2[df2["monat"] == month_num]
        if subset.empty:
            print(f"  {label}:  keine Daten")
            continue
        row = subset.loc[subset["preis_eur"].idxmin()]
        print(
            f"  {label}:  günstigstes = {row['preis_eur']:.2f} €  "
            f"({row['abflughafen']} {row['abflugdatum']} → {row['rueckflugdatum']}, "
            f"{row['airline']})"
        )

    # Overall average per month
    avg = df2.groupby("monat")["preis_eur"].mean()
    for month_num, label in monat_map.items():
        if month_num in avg.index:
            print(f"  {label} Ø:  {avg[month_num]:.2f} €")
    print()


def _print_cheapest_direct(df: pd.DataFrame) -> None:
    print("GÜNSTIGSTES DIREKTFLUG-ANGEBOT")
    print(_SEP)
    direct = df[df["direktflug"] == "ja"]
    if direct.empty:
        print("  Keine Direktflüge gefunden.")
    else:
        row = direct.loc[direct["preis_eur"].idxmin()]
        print(
            f"  {row['preis_eur']:>7.2f} €  |  "
            f"{row['abflughafen']} → PMI  {row['abflugdatum']}  {row['abflugzeit'] or '??:??'}  |  "
            f"Rück: {row['rueckflugdatum']}  |  "
            f"{row['airline']}  |  {row['quelle']}"
        )
        print(f"  URL: {row['buchungs_url']}")
    print()
