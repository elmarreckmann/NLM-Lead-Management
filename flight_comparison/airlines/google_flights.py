"""Google Flights via SerpApi – echte Preise inkl. direkter Buchungs-URL.

Kostenloser Account: https://serpapi.com/users/sign_up  (100 Searches/Monat)
API-Key in .env:  SERPAPI_KEY=your_key_here
"""

import sys
from datetime import date, timedelta

sys.path.insert(0, "..")
from config import ORIGIN_AIRPORTS, SERPAPI_KEY, SEARCH_START_DATE, SEARCH_END_DATE, get_return_dates
from models import FlightOffer
from utils import get_logger, random_delay
from .base import make_session, get_json

logger = get_logger("airlines.google_flights")

_SERPAPI_URL = "https://serpapi.com/search"

# SerpApi kostet pro Call – wir samplen alle 3 Tage statt täglich,
# um im Free-Tier zu bleiben (37 Tage × 3 Airports / 3 = ~37 Calls).
_SAMPLE_DAYS = 3


class GoogleFlightsClient:
    SOURCE_NAME = "Google Flights"

    def __init__(self) -> None:
        if not SERPAPI_KEY:
            raise ValueError(
                "SERPAPI_KEY fehlt in .env\n"
                "Kostenlos registrieren: https://serpapi.com/users/sign_up"
            )
        self._session = make_session()

    def search_all(self) -> list[FlightOffer]:
        offers: list[FlightOffer] = []
        for origin in ORIGIN_AIRPORTS:
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
                # SerpApi: einen mittleren Rückflug wählen (8 Nächte)
                ret_date = ret_dates[min(1, len(ret_dates) - 1)]
                batch = self._fetch(origin, out_date, ret_date)
                offers.extend(batch)
                if batch:
                    logger.info("Google Flights  %s  %s → %s  %d Angebote",
                                origin, out_date, ret_date, len(batch))
                random_delay(1.5, 3)
            out_date += timedelta(days=_SAMPLE_DAYS)

        return offers

    def _fetch(self, origin: str, out_date: date, ret_date: date) -> list[FlightOffer]:
        params = {
            "engine":         "google_flights",
            "departure_id":   origin,
            "arrival_id":     "PMI",
            "outbound_date":  out_date.isoformat(),
            "return_date":    ret_date.isoformat(),
            "currency":       "EUR",
            "hl":             "de",
            "gl":             "de",
            "adults":         1,
            "type":           1,          # 1 = Hin- und Rückflug
            "api_key":        SERPAPI_KEY,
        }
        data = get_json(self._session, _SERPAPI_URL, params)
        if not data or "error" in data:
            err = data.get("error") if data else "Keine Antwort"
            logger.warning("Google Flights API Fehler (%s %s): %s", origin, out_date, err)
            return []

        return self._parse(data, origin, out_date, ret_date)

    def _parse(self, data: dict, origin: str,
               out_date: date, ret_date: date) -> list[FlightOffer]:
        offers: list[FlightOffer] = []

        # SerpApi liefert "best_flights" (günstigste) + "other_flights"
        all_results = data.get("best_flights", []) + data.get("other_flights", [])

        for item in all_results:
            try:
                flights = item.get("flights", [])
                if not flights:
                    continue

                first_leg = flights[0]
                last_leg  = flights[-1]

                # Abflugzeit aus "YYYY-MM-DD HH:MM"-String
                dep_raw  = first_leg.get("departure_airport", {}).get("time", "")
                arr_raw  = last_leg.get("arrival_airport", {}).get("time", "")
                dep_time = dep_raw[11:16] if len(dep_raw) > 10 else ""

                # Rückflug-Segment
                return_flights = item.get("return_flights", [])
                if return_flights:
                    ret_dep_raw  = return_flights[0].get("departure_airport", {}).get("time", "")
                    ret_dep_date = ret_dep_raw[:10] if len(ret_dep_raw) >= 10 else ret_date.isoformat()
                    ret_dep_time = ret_dep_raw[11:16] if len(ret_dep_raw) > 10 else ""
                else:
                    ret_dep_date = ret_date.isoformat()
                    ret_dep_time = ""

                price = item.get("price")
                if not price or float(price) <= 0:
                    continue

                airline = first_leg.get("airline", "Unbekannt")
                stops   = len(item.get("layovers", []))

                # Direkte Google-Buchungs-URL aus booking_token
                booking_token = item.get("booking_token", "")
                if booking_token:
                    booking_url = (
                        f"https://www.google.com/travel/flights/booking"
                        f"?tfs={booking_token}&curr=EUR&hl=de"
                    )
                else:
                    # Fallback: Google Flights Suchergebnisseite
                    booking_url = (
                        f"https://www.google.com/travel/flights?hl=de&curr=EUR"
                        f"#flt={origin}.PMI.{out_date.isoformat()}"
                        f"*PMI.{origin}.{ret_date.isoformat()};c:EUR;e:1;sd:1;t:f"
                    )

                offers.append(FlightOffer(
                    abflughafen=origin,
                    abflugdatum=out_date.isoformat(),
                    abflugzeit=dep_time,
                    rueckflugdatum=ret_dep_date,
                    rueckflugzeit=ret_dep_time,
                    airline=airline,
                    direktflug="ja" if stops == 0 else "nein",
                    zwischenstopps=stops,
                    preis_eur=round(float(price), 2),
                    quelle=self.SOURCE_NAME,
                    buchungs_url=booking_url,
                ))
            except (KeyError, TypeError, ValueError) as exc:
                logger.debug("Google Flights parse error: %s", exc)

        return offers
