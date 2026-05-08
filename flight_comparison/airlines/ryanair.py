"""Ryanair public fare-finder API – no key required."""

import sys
from datetime import date, datetime

sys.path.insert(0, "..")
from config import ORIGIN_AIRPORTS, get_return_dates, SEARCH_START_DATE, SEARCH_END_DATE, RETURN_LATEST_DATE
from models import FlightOffer
from utils import get_logger, random_delay
from .base import make_session, get_json

logger = get_logger("airlines.ryanair")

_FARE_FINDER = "https://www.ryanair.com/api/farfnd/v4/roundTripFares"

# Ryanair doesn't serve DUS – they use NRN (Weeze). We map it so the user
# still gets Ryanair prices for the Rhine/Ruhr region.
_AIRPORT_MAP = {
    "DUS": "DUS",   # kept – will yield 0 results but won't error
    "HAJ": "HAJ",
    "PAD": "PAD",
}

_BOOKING_BASE = "https://www.ryanair.com/de/de/booking/new-booking"


class RyanairClient:
    SOURCE_NAME = "Ryanair"

    def __init__(self) -> None:
        self._session = make_session()
        self._session.headers.update({
            "Origin": "https://www.ryanair.com",
            "Referer": "https://www.ryanair.com/de/de/",
        })

    def search_all(self) -> list[FlightOffer]:
        offers: list[FlightOffer] = []
        for origin in ORIGIN_AIRPORTS:
            mapped = _AIRPORT_MAP.get(origin, origin)
            batch = self._search_origin(mapped, origin)
            offers.extend(batch)
            random_delay(2, 4)
        return offers

    def _search_origin(self, iata: str, display_origin: str) -> list[FlightOffer]:
        """Single API call covers the full date range for one origin."""
        params = {
            "departureAirportIataCode": iata,
            "arrivalAirportIataCode":   "PMI",
            "outboundDepartureDateFrom": SEARCH_START_DATE.isoformat(),
            "outboundDepartureDateTo":   SEARCH_END_DATE.isoformat(),
            "inboundDepartureDateFrom":  SEARCH_START_DATE.isoformat(),
            "inboundDepartureDateTo":    RETURN_LATEST_DATE.isoformat(),
            "durationFrom": 7,
            "durationTo":   10,
            "currency":     "EUR",
            "priceValueTo": 10000,
            "adult":        1,
        }
        logger.info("Ryanair fare-finder  %s → PMI  (%s–%s)",
                    iata, SEARCH_START_DATE, SEARCH_END_DATE)
        data = get_json(self._session, _FARE_FINDER, params,
                        extra_headers={"Accept": "application/json, text/plain, */*"})
        if not data:
            return []

        fares = data.get("fares") if isinstance(data, dict) else []
        if not fares:
            logger.info("Ryanair: no fares for %s", iata)
            return []

        return [o for raw in fares
                if (o := self._parse_fare(raw, display_origin)) is not None]

    def _parse_fare(self, raw: dict, origin: str) -> FlightOffer | None:
        try:
            outbound = raw["outbound"]
            inbound  = raw["inbound"]
            summary  = raw.get("summary", {})

            out_dep = outbound.get("departureDate", "")
            in_dep  = inbound.get("departureDate", "")
            out_date, out_time = _split_dt(out_dep)
            in_date,  in_time  = _split_dt(in_dep)

            # Total price from summary; fall back to sum of legs
            price = (
                summary.get("price", {}).get("value")
                or (outbound.get("price", {}).get("value", 0)
                    + inbound.get("price", {}).get("value", 0))
            )
            if not price or float(price) <= 0:
                return None

            # Validate return is 7–10 nights
            try:
                nights = (datetime.fromisoformat(in_date) - datetime.fromisoformat(out_date)).days
                if not (7 <= nights <= 10):
                    return None
            except Exception:
                pass

            booking_url = (
                f"{_BOOKING_BASE}/{origin}/PMI/{out_date}/{in_date}/1/0/0/0"
            )

            return FlightOffer(
                abflughafen=origin,
                abflugdatum=out_date,
                abflugzeit=out_time,
                rueckflugdatum=in_date,
                rueckflugzeit=in_time,
                airline="Ryanair",
                direktflug="ja",   # Ryanair operates point-to-point only
                zwischenstopps=0,
                preis_eur=round(float(price), 2),
                quelle=self.SOURCE_NAME,
                buchungs_url=booking_url,
            )
        except (KeyError, TypeError, ValueError) as exc:
            logger.debug("Ryanair parse error: %s  raw=%s", exc, str(raw)[:120])
            return None


def _split_dt(iso: str) -> tuple[str, str]:
    if "T" in iso:
        d, t = iso.split("T", 1)
        return d, t[:5]
    return iso, ""
