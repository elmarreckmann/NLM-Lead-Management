"""Eurowings best-price calendar API – no key required."""

import sys
from datetime import date, timedelta

sys.path.insert(0, "..")
from config import ORIGIN_AIRPORTS, SEARCH_START_DATE, SEARCH_END_DATE, get_return_dates
from models import FlightOffer
from utils import get_logger, random_delay
from .base import make_session, get_json

logger = get_logger("airlines.eurowings")

# Best-price per departure day endpoint (one call per origin/month)
_BEST_PRICE = "https://api.eurowings.com/api/flights/v2/best-prices"
_BOOKING_BASE = "https://www.eurowings.com/de/buchen/flights/results.html"


class EurowingsClient:
    SOURCE_NAME = "Eurowings"

    def __init__(self) -> None:
        self._session = make_session()
        self._session.headers.update({
            "Origin":  "https://www.eurowings.com",
            "Referer": "https://www.eurowings.com/",
        })

    def search_all(self) -> list[FlightOffer]:
        offers: list[FlightOffer] = []
        for origin in ORIGIN_AIRPORTS:
            batch = self._search_origin(origin)
            offers.extend(batch)
            random_delay(2, 4)
        return offers

    def _search_origin(self, origin: str) -> list[FlightOffer]:
        offers: list[FlightOffer] = []
        # Query May and June separately (calendar endpoint is month-scoped)
        for year, month in [(2026, 5), (2026, 6)]:
            params = {
                "origin":          origin,
                "destination":     "PMI",
                "outboundMonth":   f"{year}-{month:02d}",
                "adults":          1,
                "currency":        "EUR",
                "cabinClass":      "ECONOMY",
                "tripType":        "RETURN",
            }
            logger.info("Eurowings best-price  %s → PMI  %d-%02d", origin, year, month)
            data = get_json(self._session, _BEST_PRICE, params)
            if not data:
                continue

            day_fares = data.get("outboundDays") or data.get("days") or []
            for day_entry in day_fares:
                batch = self._parse_day(day_entry, origin)
                offers.extend(batch)
            random_delay(1.5, 3)

        return offers

    def _parse_day(self, day_entry: dict, origin: str) -> list[FlightOffer]:
        offers: list[FlightOffer] = []
        dep_date_str = day_entry.get("date") or day_entry.get("departureDate", "")
        if not dep_date_str:
            return offers
        try:
            dep_date = date.fromisoformat(dep_date_str[:10])
        except ValueError:
            return offers

        if not (SEARCH_START_DATE <= dep_date <= SEARCH_END_DATE):
            return offers

        price_val = (
            day_entry.get("lowestPrice", {}).get("amount")
            or day_entry.get("price", {}).get("amount")
            or day_entry.get("total")
        )
        if not price_val or float(price_val) <= 0:
            return offers

        dep_time = day_entry.get("departureTime", "")[:5]

        for ret_date in get_return_dates(dep_date):
            booking_url = (
                f"{_BOOKING_BASE}"
                f"?origin={origin}&destination=PMI"
                f"&outboundDate={dep_date.isoformat()}"
                f"&inboundDate={ret_date.isoformat()}"
                f"&adults=1&currency=EUR&cabinClass=ECONOMY"
            )
            offers.append(FlightOffer(
                abflughafen=origin,
                abflugdatum=dep_date.isoformat(),
                abflugzeit=dep_time,
                rueckflugdatum=ret_date.isoformat(),
                rueckflugzeit="",
                airline="Eurowings",
                direktflug="ja",
                zwischenstopps=0,
                preis_eur=round(float(price_val), 2),
                quelle=self.SOURCE_NAME,
                buchungs_url=booking_url,
            ))
            # Only keep first valid return to avoid inflating duplicate rows
            break

        return offers
