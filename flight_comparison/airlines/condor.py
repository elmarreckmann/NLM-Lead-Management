"""Condor (DE) – public fare search, no key required."""

import sys
from datetime import date

sys.path.insert(0, "..")
from config import ORIGIN_AIRPORTS, SEARCH_START_DATE, SEARCH_END_DATE, get_return_dates
from models import FlightOffer
from utils import get_logger, random_delay
from .base import make_session, get_json

logger = get_logger("airlines.condor")

_SEARCH  = "https://www.condor.com/de/api/flightSearch"
_BOOKING = "https://www.condor.com/de/fluege-buchen.html"

# Condor operates mainly from DUS and FRA; HAJ via partner
_CONDOR_AIRPORTS = {"DUS", "HAJ"}


class CondorClient:
    SOURCE_NAME = "Condor"

    def __init__(self) -> None:
        self._session = make_session()
        self._session.headers.update({
            "Origin":  "https://www.condor.com",
            "Referer": "https://www.condor.com/de/",
        })

    def search_all(self) -> list[FlightOffer]:
        offers: list[FlightOffer] = []
        for origin in ORIGIN_AIRPORTS:
            if origin not in _CONDOR_AIRPORTS:
                continue
            batch = self._search_origin(origin)
            offers.extend(batch)
            random_delay(2, 4)
        return offers

    def _search_origin(self, origin: str) -> list[FlightOffer]:
        offers: list[FlightOffer] = []
        out_date = SEARCH_START_DATE

        while out_date <= SEARCH_END_DATE:
            for ret_date in get_return_dates(out_date):
                params = {
                    "origin":      origin,
                    "destination": "PMI",
                    "departDate":  out_date.strftime("%Y-%m-%d"),
                    "returnDate":  ret_date.strftime("%Y-%m-%d"),
                    "adults":      1,
                    "currency":    "EUR",
                    "direct":      "false",
                }
                logger.info("Condor  %s → PMI  %s / %s", origin, out_date, ret_date)
                data = get_json(self._session, _SEARCH, params)
                if data:
                    offers.extend(self._parse(data, origin, out_date, ret_date))
                random_delay(1.5, 2.5)
                break   # one return date per outbound is enough for price signal

            from datetime import timedelta
            out_date += timedelta(days=1)

        return offers

    def _parse(self, data: dict | list, origin: str,
               out_date: date, ret_date: date) -> list[FlightOffer]:
        offers: list[FlightOffer] = []
        items = data if isinstance(data, list) else data.get("flights") or data.get("offers") or []
        for item in items:
            try:
                price = (
                    item.get("totalPrice")
                    or item.get("price", {}).get("total")
                    or item.get("amount")
                )
                if not price or float(price) <= 0:
                    continue
                dep_time = (item.get("departureTime") or "")[:5]
                ret_time = (item.get("returnDepartureTime") or "")[:5]
                stops = int(item.get("stops") or item.get("connections") or 0)
                booking_url = (
                    item.get("bookingUrl")
                    or (
                        f"{_BOOKING}?dep={origin}&arr=PMI"
                        f"&depDate={out_date.isoformat()}&retDate={ret_date.isoformat()}&adults=1"
                    )
                )
                offers.append(FlightOffer(
                    abflughafen=origin,
                    abflugdatum=out_date.isoformat(),
                    abflugzeit=dep_time,
                    rueckflugdatum=ret_date.isoformat(),
                    rueckflugzeit=ret_time,
                    airline="Condor",
                    direktflug="ja" if stops == 0 else "nein",
                    zwischenstopps=stops,
                    preis_eur=round(float(price), 2),
                    quelle=self.SOURCE_NAME,
                    buchungs_url=booking_url,
                ))
            except (KeyError, TypeError, ValueError) as exc:
                logger.debug("Condor parse error: %s", exc)
        return offers
