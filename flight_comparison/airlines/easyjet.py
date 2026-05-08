"""easyJet fare API – no key required."""

import sys
from datetime import date

sys.path.insert(0, "..")
from config import ORIGIN_AIRPORTS, SEARCH_START_DATE, SEARCH_END_DATE, get_return_dates
from models import FlightOffer
from utils import get_logger, random_delay
from .base import make_session, get_json

logger = get_logger("airlines.easyjet")

_FARE_URL   = "https://www.easyjet.com/api/routepricing/v2/search/roundtrip"
_BOOKING_BASE = "https://www.easyjet.com/de/fliegen"


class EasyJetClient:
    SOURCE_NAME = "easyJet"

    def __init__(self) -> None:
        self._session = make_session()
        self._session.headers.update({
            "Origin":  "https://www.easyjet.com",
            "Referer": "https://www.easyjet.com/de",
        })

    def search_all(self) -> list[FlightOffer]:
        offers: list[FlightOffer] = []
        for origin in ORIGIN_AIRPORTS:
            batch = self._search_origin(origin)
            offers.extend(batch)
            random_delay(2, 4)
        return offers

    def _search_origin(self, origin: str) -> list[FlightOffer]:
        params = {
            "origin":            origin,
            "destination":       "PMI",
            "departureDate":     SEARCH_START_DATE.isoformat(),
            "returnDate":        (SEARCH_START_DATE.replace(day=SEARCH_START_DATE.day + 7)).isoformat(),
            "adult":             1,
            "child":             0,
            "infant":            0,
            "currency":          "EUR",
            "flexibility":       0,
        }
        logger.info("easyJet fares  %s → PMI", origin)
        data = get_json(self._session, _FARE_URL, params,
                        extra_headers={"X-Requested-With": "XMLHttpRequest"})
        if not data:
            return []

        return self._parse_response(data, origin)

    def _parse_response(self, data: dict | list, origin: str) -> list[FlightOffer]:
        offers: list[FlightOffer] = []

        # easyJet response can vary; handle dict with fares list or direct list
        if isinstance(data, dict):
            fares = data.get("outboundFlights") or data.get("fares") or []
        else:
            fares = data

        for item in fares:
            try:
                dep_str = item.get("departureDateTime") or item.get("departureDate", "")
                ret_str = item.get("returnDepartureDateTime") or item.get("returnDate", "")
                if not dep_str:
                    continue

                dep_date = dep_str[:10]
                dep_time = dep_str[11:16] if "T" in dep_str else ""
                ret_date = ret_str[:10] if ret_str else ""
                ret_time = ret_str[11:16] if ret_str and "T" in ret_str else ""

                price = (
                    item.get("price", {}).get("amount")
                    or item.get("totalPrice")
                    or item.get("amount")
                )
                if not price or float(price) <= 0:
                    continue

                booking_url = (
                    f"{_BOOKING_BASE}/{origin.lower()}-pmi"
                    f"?departureDate={dep_date}&returnDate={ret_date}&adultsCount=1"
                )

                offers.append(FlightOffer(
                    abflughafen=origin,
                    abflugdatum=dep_date,
                    abflugzeit=dep_time,
                    rueckflugdatum=ret_date,
                    rueckflugzeit=ret_time,
                    airline="easyJet",
                    direktflug="ja",
                    zwischenstopps=0,
                    preis_eur=round(float(price), 2),
                    quelle=self.SOURCE_NAME,
                    buchungs_url=booking_url,
                ))
            except (KeyError, TypeError, ValueError) as exc:
                logger.debug("easyJet parse error: %s", exc)

        return offers
