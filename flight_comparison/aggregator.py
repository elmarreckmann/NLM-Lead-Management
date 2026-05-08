"""Orchestrates all data sources and deduplicates results."""

import sys
from datetime import date
from typing import Callable

import pandas as pd

from config import ORIGIN_AIRPORTS, get_outbound_dates, get_return_dates
from models import FlightOffer
from utils import get_logger, random_delay

logger = get_logger("aggregator")


# ------------------------------------------------------------------
# Main entry point
# ------------------------------------------------------------------

def collect_all_offers(
    use_amadeus: bool = True,
    use_duffel: bool = True,
    use_scrapers: bool = True,
    progress_cb: Callable[[str], None] | None = None,
) -> pd.DataFrame:
    """Run all enabled sources and return a deduplicated DataFrame."""
    all_offers: list[FlightOffer] = []

    if use_amadeus:
        all_offers.extend(_run_amadeus(progress_cb))

    if use_duffel:
        all_offers.extend(_run_duffel(progress_cb))

    if use_scrapers:
        all_offers.extend(_run_scrapers(progress_cb))

    if not all_offers:
        logger.warning("No offers collected from any source.")
        return pd.DataFrame()

    df = _to_dataframe(all_offers)
    df = _deduplicate(df)
    logger.info("Total unique offers after deduplication: %d", len(df))
    return df


# ------------------------------------------------------------------
# Per-source runners
# ------------------------------------------------------------------

def _run_amadeus(progress_cb: Callable | None) -> list[FlightOffer]:
    from config import AMADEUS_API_KEY
    if not AMADEUS_API_KEY:
        logger.warning("Amadeus API key missing – skipping.")
        return []

    try:
        from amadeus_client import AmadeusClient
        client = AmadeusClient()
    except Exception as exc:
        logger.error("Amadeus client init failed: %s", exc)
        return []

    offers: list[FlightOffer] = []
    outbound_dates = get_outbound_dates()
    total = len(ORIGIN_AIRPORTS) * len(outbound_dates)
    done = 0

    for origin in ORIGIN_AIRPORTS:
        for out_date in outbound_dates:
            _notify(progress_cb, f"Amadeus  {origin}  {out_date.isoformat()}"
                    f"  ({done+1}/{total})")
            try:
                batch = client.search_flights(origin, out_date)
                offers.extend(batch)
                logger.debug("Amadeus %s %s → %d offers", origin, out_date, len(batch))
            except Exception as exc:
                logger.error("Amadeus search error (%s %s): %s", origin, out_date, exc)
            done += 1
            random_delay(1.0, 2.0)

    logger.info("Amadeus total: %d raw offers", len(offers))
    return offers


def _run_duffel(progress_cb: Callable | None) -> list[FlightOffer]:
    from config import DUFFEL_API_KEY
    if not DUFFEL_API_KEY:
        logger.warning("Duffel API key missing – skipping.")
        return []

    try:
        from duffel_client import DuffelClient
        client = DuffelClient()
    except Exception as exc:
        logger.error("Duffel client init failed: %s", exc)
        return []

    offers: list[FlightOffer] = []
    outbound_dates = get_outbound_dates()
    total = len(ORIGIN_AIRPORTS) * len(outbound_dates)
    done = 0

    for origin in ORIGIN_AIRPORTS:
        for out_date in outbound_dates:
            _notify(progress_cb, f"Duffel   {origin}  {out_date.isoformat()}"
                    f"  ({done+1}/{total})")
            try:
                batch = client.search_flights(origin, out_date)
                offers.extend(batch)
            except Exception as exc:
                logger.error("Duffel search error (%s %s): %s", origin, out_date, exc)
            done += 1
            random_delay(1.5, 3.0)

    logger.info("Duffel total: %d raw offers", len(offers))
    return offers


def _run_scrapers(progress_cb: Callable | None) -> list[FlightOffer]:
    from scrapers import ALL_SCRAPERS

    offers: list[FlightOffer] = []
    outbound_dates = get_outbound_dates()

    for ScraperClass in ALL_SCRAPERS:
        scraper_name = ScraperClass.SOURCE_NAME
        logger.info("Starting scraper: %s", scraper_name)

        try:
            with ScraperClass() as scraper:
                for origin in ORIGIN_AIRPORTS:
                    for out_date in outbound_dates:
                        for ret_date in get_return_dates(out_date):
                            _notify(progress_cb,
                                    f"{scraper_name}  {origin}  "
                                    f"{out_date.isoformat()} → {ret_date.isoformat()}")
                            try:
                                batch = scraper.search(origin, out_date, ret_date)
                                offers.extend(batch)
                            except Exception as exc:
                                logger.error("[%s] search error (%s %s → %s): %s",
                                             scraper_name, origin, out_date, ret_date, exc)
                            random_delay(2.0, 4.0)

        except Exception as exc:
            logger.error("Scraper %s crashed: %s", scraper_name, exc)

    logger.info("Scrapers total: %d raw offers", len(offers))
    return offers


# ------------------------------------------------------------------
# DataFrame helpers
# ------------------------------------------------------------------

def _to_dataframe(offers: list[FlightOffer]) -> pd.DataFrame:
    rows = [
        {
            "abflughafen":   o.abflughafen,
            "abflugdatum":   o.abflugdatum,
            "abflugzeit":    o.abflugzeit,
            "rueckflugdatum": o.rueckflugdatum,
            "rueckflugzeit": o.rueckflugzeit,
            "airline":       o.airline,
            "direktflug":    o.direktflug,
            "zwischenstopps": o.zwischenstopps,
            "preis_eur":     o.preis_eur,
            "quelle":        o.quelle,
            "buchungs_url":  o.buchungs_url,
            "abgerufen_am":  o.abgerufen_am,
        }
        for o in offers
    ]
    return pd.DataFrame(rows)


def _deduplicate(df: pd.DataFrame) -> pd.DataFrame:
    """For identical flights (same route/times/airline/stops from multiple sources),
    keep the row with the lowest price and cheapest booking URL."""
    if df.empty:
        return df

    key_cols = [
        "abflughafen", "abflugdatum", "abflugzeit",
        "rueckflugdatum", "rueckflugzeit",
        "airline", "zwischenstopps",
    ]

    # Where time info is missing, different sources may fill it in differently.
    # Group only on columns that are reliably set; keep lowest price per group.
    df_sorted = df.sort_values("preis_eur", ascending=True)

    # Fill empty strings so groupby works correctly
    for col in key_cols:
        df_sorted[col] = df_sorted[col].fillna("").str.strip()

    df_dedup = df_sorted.drop_duplicates(subset=key_cols, keep="first")
    dropped = len(df) - len(df_dedup)
    if dropped:
        logger.info("Deduplicated %d duplicate rows (kept cheapest price)", dropped)

    return df_dedup.reset_index(drop=True)
