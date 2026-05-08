"""Eurowings – session-cookie basierter Zugriff auf den Bestpreis-Kalender."""

import sys
from datetime import date

sys.path.insert(0, "..")
from config import ORIGIN_AIRPORTS, SEARCH_START_DATE, SEARCH_END_DATE, get_return_dates
from models import FlightOffer
from utils import get_logger, random_delay
from .base import make_session, get_json

logger = get_logger("airlines.eurowings")

_HOME       = "https://www.eurowings.com/de/"
_CALENDAR   = "https://www.eurowings.com/api/priceCalendar/v2/prices"
_BOOKING    = "https://www.eurowings.com/de/buchen/flights/results.html"


class EurowingsClient:
    SOURCE_NAME = "Eurowings"

    def __init__(self) -> None:
        self._session = make_session()
        self._session.headers.update({
            "Origin":  "https://www.eurowings.com",
            "Referer": "https://www.eurowings.com/de/",
        })
        self._warm_up()

    def _warm_up(self) -> None:
        """Visit homepage once to pick up session cookies."""
        try:
            r = self._session.get(_HOME, timeout=15)
            logger.debug("Eurowings warm-up: %s", r.status_code)
        except Exception as exc:
            logger.debug("Eurowings warm-up failed (continuing): %s", exc)

    def search_all(self) -> list[FlightOffer]:
        offers: list[FlightOffer] = []
        for origin in ORIGIN_AIRPORTS:
            batch = self._search_origin(origin)
            offers.extend(batch)
            random_delay(2, 4)
        return offers

    def _search_origin(self, origin: str) -> list[FlightOffer]:
        offers: list[FlightOffer] = []
        for year, month in [(2026, 5), (2026, 6)]:
            logger.info("Eurowings calendar  %s → PMI  %d-%02d", origin, year, month)

            # Try v2 calendar endpoint (with session cookies)
            params = {
                "origin":       origin,
                "destination":  "PMI",
                "month":        f"{year}-{month:02d}",
                "tripType":     "RETURN",
                "adults":       1,
                "currency":     "EUR",
            }
            data = get_json(self._session, _CALENDAR, params)

            # Fallback: v1 variant
            if not data:
                params_v1 = {
                    "origin":          origin,
                    "destination":     "PMI",
                    "outboundMonth":   f"{year}-{month:02d}",
                    "adults":          1,
                    "currency":        "EUR",
                    "cabinClass":      "ECONOMY",
                }
                data = get_json(
                    self._session,
                    "https://www.eurowings.com/api/priceCalendar/v1/calendar",
                    params_v1,
                )

            if not data:
                logger.info("Eurowings: keine Daten für %s %d-%02d", origin, year, month)
                continue

            day_fares = (
                data.get("outboundDays")
                or data.get("days")
                or data.get("prices")
                or (data if isinstance(data, list) else [])
            )
            for entry in day_fares:
                offers.extend(self._parse_day(entry, origin))
            random_delay(1.5, 3)

        return offers

    def _parse_day(self, entry: dict, origin: str) -> list[FlightOffer]:
        dep_str = entry.get("date") or entry.get("departureDate") or entry.get("day", "")
        if not dep_str:
            return []
        try:
            dep_date = date.fromisoformat(dep_str[:10])
        except ValueError:
            return []
        if not (SEARCH_START_DATE <= dep_date <= SEARCH_END_DATE):
            return []

        price_val = (
            entry.get("lowestPrice", {}).get("amount")
            or entry.get("price", {}).get("amount")
            or entry.get("price")
            or entry.get("amount")
            or entry.get("total")
        )
        if not price_val:
            return []
        try:
            price = round(float(price_val), 2)
        except (ValueError, TypeError):
            return []
        if price <= 0:
            return []

        dep_time = (entry.get("departureTime") or "")[:5]
        ret_dates = get_return_dates(dep_date)
        if not ret_dates:
            return []
        ret_date = ret_dates[0]

        booking_url = (
            f"{_BOOKING}?origin={origin}&destination=PMI"
            f"&outboundDate={dep_date.isoformat()}&inboundDate={ret_date.isoformat()}"
            f"&adults=1&currency=EUR&cabinClass=ECONOMY"
        )
        return [FlightOffer(
            abflughafen=origin,
            abflugdatum=dep_date.isoformat(),
            abflugzeit=dep_time,
            rueckflugdatum=ret_date.isoformat(),
            rueckflugzeit="",
            airline="Eurowings",
            direktflug="ja",
            zwischenstopps=0,
            preis_eur=price,
            quelle=self.SOURCE_NAME,
            buchungs_url=booking_url,
        )]
