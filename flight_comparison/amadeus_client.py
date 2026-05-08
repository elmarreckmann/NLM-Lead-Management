"""Amadeus for Developers API – flight offers search."""

import time
from datetime import date

import requests

from config import (
    AMADEUS_API_KEY,
    AMADEUS_API_SECRET,
    DESTINATION_AIRPORT,
    PASSENGERS_ADULTS,
    REQUEST_TIMEOUT,
    get_return_dates,
)
from models import FlightOffer
from utils import get_logger, random_delay

logger = get_logger("amadeus")

_AUTH_URL = "https://test.api.amadeus.com/v1/security/oauth2/token"
_SEARCH_URL = "https://test.api.amadeus.com/v2/shopping/flight-offers"
# Switch to production base URL when you have a production key:
# _AUTH_URL  = "https://api.amadeus.com/v1/security/oauth2/token"
# _SEARCH_URL = "https://api.amadeus.com/v2/shopping/flight-offers"


class AmadeusClient:
    def __init__(self) -> None:
        self._token: str = ""
        self._token_expires_at: float = 0.0

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def _authenticate(self) -> None:
        if not AMADEUS_API_KEY or not AMADEUS_API_SECRET:
            raise ValueError("AMADEUS_API_KEY / AMADEUS_API_SECRET not set in .env")

        logger.info("Requesting Amadeus OAuth2 token …")
        resp = requests.post(
            _AUTH_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": AMADEUS_API_KEY,
                "client_secret": AMADEUS_API_SECRET,
            },
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        payload = resp.json()
        self._token = payload["access_token"]
        # Subtract 60 s buffer so we refresh before actual expiry
        self._token_expires_at = time.time() + int(payload.get("expires_in", 1799)) - 60
        logger.info("Amadeus token acquired (valid ~%ds)", payload.get("expires_in", 1799))

    def _get_headers(self) -> dict:
        if time.time() >= self._token_expires_at:
            self._authenticate()
        return {"Authorization": f"Bearer {self._token}"}

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search_flights(
        self,
        origin: str,
        outbound_date: date,
    ) -> list[FlightOffer]:
        """Search for all valid round-trips from *origin* on *outbound_date*."""
        offers: list[FlightOffer] = []

        return_dates = get_return_dates(outbound_date)
        if not return_dates:
            return offers

        for return_date in return_dates:
            batch = self._fetch_offers(origin, outbound_date, return_date)
            offers.extend(batch)
            random_delay(1.0, 2.0)  # stay within rate limit between return-date calls

        return offers

    def _fetch_offers(
        self,
        origin: str,
        outbound_date: date,
        return_date: date,
    ) -> list[FlightOffer]:
        params = {
            "originLocationCode": origin,
            "destinationLocationCode": DESTINATION_AIRPORT,
            "departureDate": outbound_date.isoformat(),
            "returnDate": return_date.isoformat(),
            "adults": PASSENGERS_ADULTS,
            "currencyCode": "EUR",
            "max": 50,  # max results per call (API limit: 250)
        }

        try:
            resp = requests.get(
                _SEARCH_URL,
                headers=self._get_headers(),
                params=params,
                timeout=REQUEST_TIMEOUT,
            )
            if resp.status_code == 429:
                logger.warning("Amadeus rate limit hit – sleeping 10 s")
                time.sleep(10)
                resp = requests.get(
                    _SEARCH_URL,
                    headers=self._get_headers(),
                    params=params,
                    timeout=REQUEST_TIMEOUT,
                )
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.error("Amadeus request failed (%s %s): %s", origin, outbound_date, exc)
            return []

        try:
            data = resp.json()
        except ValueError:
            logger.error("Amadeus returned non-JSON response")
            return []

        return self._parse_offers(data, origin)

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def _parse_offers(self, data: dict, origin: str) -> list[FlightOffer]:
        offers: list[FlightOffer] = []
        raw_offers = data.get("data", [])

        for item in raw_offers:
            try:
                offer = self._parse_single_offer(item, origin)
                if offer:
                    offers.append(offer)
            except Exception as exc:
                logger.debug("Could not parse offer: %s", exc)

        return offers

    def _parse_single_offer(self, item: dict, origin: str) -> FlightOffer | None:
        itineraries = item.get("itineraries", [])
        if len(itineraries) < 2:
            return None  # need both outbound and return leg

        # --- Outbound leg ---
        out_segments = itineraries[0].get("segments", [])
        if not out_segments:
            return None
        out_first = out_segments[0]
        out_last = out_segments[-1]

        abflugdatum, abflugzeit = _split_datetime(out_first["departure"]["at"])
        out_stops = len(out_segments) - 1

        # --- Return leg ---
        ret_segments = itineraries[1].get("segments", [])
        if not ret_segments:
            return None
        ret_first = ret_segments[0]

        rueckflugdatum, rueckflugzeit = _split_datetime(ret_first["departure"]["at"])

        # --- Airline (first operating/marketing carrier) ---
        airline = (
            out_first.get("operating", {}).get("carrierCode")
            or out_first.get("carrierCode", "")
        )

        # --- Price ---
        price_str = item.get("price", {}).get("grandTotal", "0")
        try:
            preis = float(price_str)
        except ValueError:
            preis = 0.0

        direktflug = "ja" if out_stops == 0 else "nein"

        return FlightOffer(
            abflughafen=origin,
            abflugdatum=abflugdatum,
            abflugzeit=abflugzeit,
            rueckflugdatum=rueckflugdatum,
            rueckflugzeit=rueckflugzeit,
            airline=airline,
            direktflug=direktflug,
            zwischenstopps=out_stops,
            preis_eur=preis,
            quelle="Amadeus API",
            buchungs_url="https://www.amadeus.com",
        )


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _split_datetime(iso: str) -> tuple[str, str]:
    """Split '2026-05-18T06:45:00' into ('2026-05-18', '06:45')."""
    parts = iso.split("T")
    date_part = parts[0] if parts else ""
    time_part = parts[1][:5] if len(parts) > 1 else ""
    return date_part, time_part
