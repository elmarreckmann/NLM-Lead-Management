"""Ryanair – cheapestPerDay Methode für vollständige Preisgitter.

Strategie:
  1. GET cheapestPerDay  ORIGIN → PMI  (Hinflug-Preise pro Tag)
  2. GET cheapestPerDay  PMI → ORIGIN  (Rückflug-Preise pro Tag)
  3. Alle gültigen 7–10-Nacht-Kombinationen kreuzen → Gesamtpreis = Hin + Rück
  4. Direkter Buchungslink je Kombination
"""

import sys
from datetime import date, timedelta

sys.path.insert(0, "..")
from config import (ORIGIN_AIRPORTS, SEARCH_START_DATE, SEARCH_END_DATE,
                    RETURN_LATEST_DATE, MIN_NIGHTS, MAX_NIGHTS)
from models import FlightOffer
from utils import get_logger, random_delay
from .base import make_session, get_json

logger = get_logger("airlines.ryanair")

_CHEAPEST_PER_DAY = "https://www.ryanair.com/api/farfnd/v4/oneWayFares/{origin}/{dest}/cheapestPerDay"
_BOOKING_BASE     = "https://www.ryanair.com/de/de/booking/new-booking"

# Ryanair bedient DUS nicht direkt (nutzt NRN/Weeze)
_RYANAIR_AIRPORTS = {"PAD", "HAJ"}


class RyanairClient:
    SOURCE_NAME = "Ryanair"

    def __init__(self) -> None:
        self._session = make_session()
        self._session.headers.update({
            "Origin":  "https://www.ryanair.com",
            "Referer": "https://www.ryanair.com/de/de/",
            "Accept":  "application/json, text/plain, */*",
        })

    def search_all(self) -> list[FlightOffer]:
        offers: list[FlightOffer] = []
        for origin in ORIGIN_AIRPORTS:
            if origin not in _RYANAIR_AIRPORTS:
                logger.info("Ryanair: %s wird nicht bedient – überspringe", origin)
                continue
            batch = self._search_origin(origin)
            offers.extend(batch)
            random_delay(2, 3)
        return offers

    # ------------------------------------------------------------------
    # Kernlogik: Preisgitter aufbauen
    # ------------------------------------------------------------------

    def _search_origin(self, origin: str) -> list[FlightOffer]:
        # Hinflug-Preise pro Tag: ORIGIN → PMI
        out_prices = self._fetch_cheapest_per_day(origin, "PMI")
        if not out_prices:
            logger.warning("Ryanair: keine Hinflug-Preise für %s", origin)
            return []

        # Rückflug-Preise pro Tag: PMI → ORIGIN
        ret_prices = self._fetch_cheapest_per_day("PMI", origin)
        if not ret_prices:
            logger.warning("Ryanair: keine Rückflug-Preise für %s", origin)
            return []

        logger.info("Ryanair %s: %d Hintage, %d Rücktage – kombiniere …",
                    origin, len(out_prices), len(ret_prices))
        return self._combine(origin, out_prices, ret_prices)

    def _fetch_cheapest_per_day(self, origin: str, dest: str) -> dict[date, tuple[float, str]]:
        """Gibt {Datum: (Preis, Abflugzeit)} zurück."""
        prices: dict[date, tuple[float, str]] = {}

        # API ist monatsweise – Mai und Juni separat abfragen
        for year, month in [(2026, 5), (2026, 6)]:
            month_date = date(year, month, 1)
            url = _CHEAPEST_PER_DAY.format(origin=origin, dest=dest)
            data = get_json(self._session, url,
                            {"outboundMonthOfDate": month_date.isoformat(),
                             "currency": "EUR"})
            if not data:
                continue

            fares = data.get("outbound", {}).get("fares", [])
            for fare in fares:
                if fare.get("soldOut") or fare.get("unavailable"):
                    continue
                day_str = fare.get("day", "")
                price   = fare.get("price", {}).get("value")
                if not day_str or not price or float(price) <= 0:
                    continue
                try:
                    d = date.fromisoformat(day_str[:10])
                except ValueError:
                    continue
                dep_time = fare.get("departureTime", "")[:5]
                prices[d] = (round(float(price), 2), dep_time)

            random_delay(1, 2)

        return prices

    # ------------------------------------------------------------------
    # Kombination Hin × Rück → FlightOffer
    # ------------------------------------------------------------------

    def _combine(self, origin: str,
                 out_prices: dict[date, tuple[float, str]],
                 ret_prices: dict[date, tuple[float, str]]) -> list[FlightOffer]:
        offers: list[FlightOffer] = []

        for out_date, (out_price, out_time) in sorted(out_prices.items()):
            if not (SEARCH_START_DATE <= out_date <= SEARCH_END_DATE):
                continue

            for nights in range(MIN_NIGHTS, MAX_NIGHTS + 1):
                ret_date = out_date + timedelta(days=nights)
                if ret_date > RETURN_LATEST_DATE:
                    break
                if ret_date not in ret_prices:
                    continue

                ret_price, ret_time = ret_prices[ret_date]
                total = round(out_price + ret_price, 2)

                offers.append(FlightOffer(
                    abflughafen=origin,
                    abflugdatum=out_date.isoformat(),
                    abflugzeit=out_time,
                    rueckflugdatum=ret_date.isoformat(),
                    rueckflugzeit=ret_time,
                    airline="Ryanair",
                    direktflug="ja",
                    zwischenstopps=0,
                    preis_eur=total,
                    quelle=self.SOURCE_NAME,
                    buchungs_url=(
                        f"{_BOOKING_BASE}/{origin}/PMI"
                        f"/{out_date.isoformat()}/{ret_date.isoformat()}/1/0/0/0"
                    ),
                ))

        offers.sort(key=lambda o: o.preis_eur)
        logger.info("Ryanair %s: %d Kombinationen gefunden", origin, len(offers))
        return offers
