"""Duffel API – flight offer requests as secondary API source."""

from datetime import date

import requests

from config import (
    DESTINATION_AIRPORT,
    DUFFEL_API_KEY,
    PASSENGERS_ADULTS,
    REQUEST_TIMEOUT,
    get_return_dates,
)
from models import FlightOffer
from utils import get_logger, random_delay

logger = get_logger("duffel")

_BASE_URL = "https://api.duffel.com"
_OFFER_REQUEST_URL = f"{_BASE_URL}/air/offer_requests"
_OFFERS_URL = f"{_BASE_URL}/air/offers"
_API_VERSION = "v2"


class DuffelClient:
    def __init__(self) -> None:
        if not DUFFEL_API_KEY:
            raise ValueError("DUFFEL_API_KEY not set in .env")
        self._headers = {
            "Authorization": f"Bearer {DUFFEL_API_KEY}",
            "Duffel-Version": _API_VERSION,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def search_flights(self, origin: str, outbound_date: date) -> list[FlightOffer]:
        offers: list[FlightOffer] = []
        return_dates = get_return_dates(outbound_date)

        for return_date in return_dates:
            batch = self._fetch_offers(origin, outbound_date, return_date)
            offers.extend(batch)
            random_delay(1.5, 3.0)

        return offers

    # ------------------------------------------------------------------
    # API calls
    # ------------------------------------------------------------------

    def _fetch_offers(self, origin: str, outbound: date, return_d: date) -> list[FlightOffer]:
        # Step 1: create offer request
        offer_request_id = self._create_offer_request(origin, outbound, return_d)
        if not offer_request_id:
            return []

        # Step 2: list offers from that request
        return self._list_offers(offer_request_id, origin, outbound, return_d)

    def _create_offer_request(self, origin: str, outbound: date, return_d: date) -> str | None:
        payload = {
            "data": {
                "slices": [
                    {
                        "origin": origin,
                        "destination": DESTINATION_AIRPORT,
                        "departure_date": outbound.isoformat(),
                    },
                    {
                        "origin": DESTINATION_AIRPORT,
                        "destination": origin,
                        "departure_date": return_d.isoformat(),
                    },
                ],
                "passengers": [{"type": "adult"} for _ in range(PASSENGERS_ADULTS)],
                "cabin_class": "economy",
            }
        }

        try:
            resp = requests.post(
                _OFFER_REQUEST_URL,
                json=payload,
                headers=self._headers,
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            return resp.json()["data"]["id"]
        except requests.RequestException as exc:
            logger.error("Duffel offer_request failed (%s %s): %s", origin, outbound, exc)
            return None

    def _list_offers(self, offer_request_id: str, origin: str,
                     outbound: date, return_d: date) -> list[FlightOffer]:
        try:
            resp = requests.get(
                _OFFERS_URL,
                params={
                    "offer_request_id": offer_request_id,
                    "sort": "total_amount",
                    "limit": 50,
                },
                headers=self._headers,
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            raw_offers = resp.json().get("data", [])
        except requests.RequestException as exc:
            logger.error("Duffel list_offers failed (%s): %s", offer_request_id, exc)
            return []

        return [
            o for raw in raw_offers
            if (o := self._parse_offer(raw, origin, outbound, return_d)) is not None
        ]

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def _parse_offer(self, raw: dict, origin: str,
                     outbound: date, return_d: date) -> FlightOffer | None:
        try:
            slices = raw.get("slices", [])
            if len(slices) < 2:
                return None

            out_slice = slices[0]
            out_segments = out_slice.get("segments", [])
            if not out_segments:
                return None

            first_seg = out_segments[0]
            dep_at = first_seg.get("departing_at", "")
            abflugdatum, abflugzeit = _split_datetime(dep_at)

            ret_slice = slices[1]
            ret_segments = ret_slice.get("segments", [])
            ret_dep_at = ret_segments[0].get("departing_at", "") if ret_segments else ""
            rueckflugdatum, rueckflugzeit = _split_datetime(ret_dep_at)

            stops = len(out_segments) - 1
            airline = (
                first_seg.get("operating_carrier", {}).get("iata_code")
                or first_seg.get("marketing_carrier", {}).get("iata_code", "")
            )

            price_str = raw.get("total_amount", "0")
            currency = raw.get("total_currency", "EUR")
            if currency != "EUR":
                logger.debug("Duffel offer in %s – skipping non-EUR", currency)
                return None

            return FlightOffer(
                abflughafen=origin,
                abflugdatum=abflugdatum,
                abflugzeit=abflugzeit,
                rueckflugdatum=rueckflugdatum,
                rueckflugzeit=rueckflugzeit,
                airline=airline,
                direktflug="ja" if stops == 0 else "nein",
                zwischenstopps=stops,
                preis_eur=float(price_str),
                quelle="Duffel API",
                buchungs_url=raw.get("booking_url") or "https://app.duffel.com",
            )
        except Exception as exc:
            logger.debug("Duffel parse error: %s", exc)
            return None


def _split_datetime(iso: str) -> tuple[str, str]:
    parts = iso.split("T")
    date_part = parts[0] if parts else ""
    time_part = parts[1][:5] if len(parts) > 1 else ""
    return date_part, time_part
