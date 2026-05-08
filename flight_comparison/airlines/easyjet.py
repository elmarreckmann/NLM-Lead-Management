"""easyJet – low-fare calendar + direkte Buchungs-URLs."""

import sys
from datetime import date, timedelta

sys.path.insert(0, "..")
from config import ORIGIN_AIRPORTS, SEARCH_START_DATE, SEARCH_END_DATE, get_return_dates
from models import FlightOffer
from utils import get_logger, random_delay
from .base import make_session, get_json

logger = get_logger("airlines.easyjet")

# easyJet flies from HAJ and DUS to PMI; not from PAD
_EZY_AIRPORTS = {"HAJ", "DUS"}

# Endpoint variants to try in order
_ENDPOINTS = [
    "https://www.easyjet.com/api/routepricing/v3/search/roundtrip",
    "https://www.easyjet.com/api/routepricing/v2/search/roundtrip",
    "https://api.easyjet.com/yield/api/2/routeavailability",
]
_CALENDAR_URL = "https://www.easyjet.com/api/routepricing/v2/calendar"
_BOOKING_BASE = "https://www.easyjet.com/de/fliegen"


class EasyJetClient:
    SOURCE_NAME = "easyJet"

    def __init__(self) -> None:
        self._session = make_session()
        self._session.headers.update({
            "Origin":  "https://www.easyjet.com",
            "Referer": "https://www.easyjet.com/de",
            "X-Requested-With": "XMLHttpRequest",
        })
        self._working_endpoint: str | None = None

    def search_all(self) -> list[FlightOffer]:
        offers: list[FlightOffer] = []
        for origin in ORIGIN_AIRPORTS:
            if origin not in _EZY_AIRPORTS:
                logger.info("easyJet: %s nicht bedient – überspringe", origin)
                continue
            batch = self._search_origin(origin)
            offers.extend(batch)
            random_delay(2, 4)
        return offers

    def _search_origin(self, origin: str) -> list[FlightOffer]:
        offers: list[FlightOffer] = []
        out_date = SEARCH_START_DATE

        while out_date <= SEARCH_END_DATE:
            ret_dates = get_return_dates(out_date)
            if ret_dates:
                ret_date = ret_dates[0]
                batch = self._fetch_one(origin, out_date, ret_date)
                offers.extend(batch)
                random_delay(1.5, 3)
            out_date += timedelta(days=3)   # sample every 3 days

        return offers

    def _fetch_one(self, origin: str, out_date: date, ret_date: date) -> list[FlightOffer]:
        params = {
            "origin":         origin,
            "destination":    "PMI",
            "departureDate":  out_date.isoformat(),
            "returnDate":     ret_date.isoformat(),
            "adult":          1,
            "child":          0,
            "infant":         0,
            "currency":       "EUR",
        }

        # Try each endpoint until one returns data
        endpoints = ([self._working_endpoint] if self._working_endpoint
                     else _ENDPOINTS)
        for url in endpoints:
            if not url:
                continue
            logger.info("easyJet fares  %s → PMI  %s  via %s", origin, out_date, url.split("/")[-1])
            data = get_json(self._session, url, params)
            if data:
                self._working_endpoint = url
                return self._parse(data, origin, out_date, ret_date)

        # All JSON endpoints failed – build booking URL with price=unknown
        logger.info("easyJet: alle Endpoints fehlgeschlagen für %s %s – nur Buchungs-URL", origin, out_date)
        return []

    def _parse(self, data: dict | list, origin: str,
               out_date: date, ret_date: date) -> list[FlightOffer]:
        offers = []
        if isinstance(data, dict):
            items = (data.get("outboundFlights")
                     or data.get("fares")
                     or data.get("flights")
                     or [data])
        else:
            items = data

        for item in items:
            try:
                dep_str  = item.get("departureDateTime") or item.get("departureDate") or out_date.isoformat()
                ret_str  = item.get("returnDepartureDateTime") or item.get("returnDate") or ret_date.isoformat()
                dep_date = dep_str[:10]
                dep_time = dep_str[11:16] if "T" in dep_str else ""
                r_date   = ret_str[:10]
                r_time   = ret_str[11:16] if "T" in ret_str else ""
                price    = (item.get("price", {}).get("amount")
                            or item.get("totalPrice")
                            or item.get("amount"))
                if not price or float(price) <= 0:
                    continue
                booking_url = (
                    f"{_BOOKING_BASE}/{origin.lower()}-pmi"
                    f"?departureDate={dep_date}&returnDate={r_date}&adultsCount=1"
                )
                offers.append(FlightOffer(
                    abflughafen=origin,
                    abflugdatum=dep_date,
                    abflugzeit=dep_time,
                    rueckflugdatum=r_date,
                    rueckflugzeit=r_time,
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
