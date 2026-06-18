"""Kayak.de scraper."""

import re
import sys
from datetime import date

from bs4 import BeautifulSoup

sys.path.insert(0, "..")
from models import FlightOffer
from .base import BaseScraper, parse_price


class KayakScraper(BaseScraper):
    SOURCE_NAME = "Kayak"
    RESULTS_SELECTOR = "div.nrc6-wrapper, div[class*='resultInner'], div.Iqt3"

    def _build_url(self, origin: str, outbound: date, return_d: date) -> str:
        out = outbound.strftime("%Y-%m-%d")
        ret = return_d.strftime("%Y-%m-%d")
        return (
            f"https://www.kayak.de/flights/{origin}-PMI/{out}/{ret}"
            f"?adults=1&sort=price_a&fs=cfc=1"
        )

    def _parse_results(self, soup: BeautifulSoup, origin: str,
                       outbound: date, return_d: date) -> list[FlightOffer]:
        offers: list[FlightOffer] = []
        base_url = "https://www.kayak.de"

        result_cards = (
            soup.select("div.nrc6-wrapper")
            or soup.select("div[class*='resultInner']")
            or soup.select("div.Iqt3")
        )

        for card in result_cards[:20]:
            # Price
            price_el = (
                card.select_one("div.f8F1-price-text")
                or card.select_one("span[class*='price']")
                or card.select_one("div.Iqt3-price")
                or card.select_one("[class*='price-text']")
            )
            if not price_el:
                continue
            price = parse_price(price_el.get_text(strip=True))
            if not price or price <= 0:
                continue

            # Airline
            airline_el = (
                card.select_one("div.c_cgF-carrier-text")
                or card.select_one("div[class*='carrier']")
                or card.select_one("span[class*='airline']")
            )
            airline = airline_el.get_text(strip=True) if airline_el else "Unbekannt"

            # Stops
            stop_el = (
                card.select_one("span[class*='stops-text']")
                or card.select_one("div[class*='stops']")
            )
            stop_text = stop_el.get_text(strip=True).lower() if stop_el else ""
            if "nonstop" in stop_text or "direct" in stop_text or "direkt" in stop_text:
                stops = 0
            else:
                m = re.search(r"(\d+)", stop_text)
                stops = int(m.group(1)) if m else 1

            # Departure time
            time_el = card.select_one("span[class*='depart-time'], div[class*='departure'] span")
            dep_time = time_el.get_text(strip=True)[:5] if time_el else ""

            # Booking link
            link_el = card.select_one("a[href*='/flights/']")
            href = link_el["href"] if link_el and link_el.get("href") else ""
            booking_url = base_url + href if href.startswith("/") else href or self.driver.current_url

            offers.append(FlightOffer(
                abflughafen=origin,
                abflugdatum=outbound.isoformat(),
                abflugzeit=dep_time,
                rueckflugdatum=return_d.isoformat(),
                rueckflugzeit="",
                airline=airline,
                direktflug="ja" if stops == 0 else "nein",
                zwischenstopps=stops,
                preis_eur=price,
                quelle=self.SOURCE_NAME,
                buchungs_url=booking_url,
            ))

        return offers
