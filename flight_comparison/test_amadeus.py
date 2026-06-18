"""Quick smoke-test for the Amadeus client (run manually, not part of main flow)."""

from datetime import date

from amadeus_client import AmadeusClient
from utils import get_logger

logger = get_logger("test_amadeus")


def main() -> None:
    client = AmadeusClient()
    logger.info("Searching DUS → PMI on 2026-05-18 …")
    offers = client.search_flights(origin="DUS", outbound_date=date(2026, 5, 18))
    if offers:
        logger.info("Got %d offers. Cheapest: %.2f EUR", len(offers), min(o.preis_eur for o in offers))
        for o in sorted(offers, key=lambda x: x.preis_eur)[:3]:
            print(f"  {o.abflugdatum} → {o.rueckflugdatum}  {o.airline:4s}  "
                  f"{'direkt' if o.direktflug == 'ja' else o.zwischenstopps + ' stop'}  "
                  f"{o.preis_eur:.2f} EUR")
    else:
        logger.warning("No offers returned – check your API key or use production endpoint.")


if __name__ == "__main__":
    main()
