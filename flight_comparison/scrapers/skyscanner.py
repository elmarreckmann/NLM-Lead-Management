"""Skyscanner.de scraper."""

import re
import sys
from datetime import date

from bs4 import BeautifulSoup

sys.path.insert(0, "..")
from models import FlightOffer
from .base import BaseScraper, parse_price


class SkyscannerScraper(BaseScraper):
    SOURCE_NAME = "Skyscanner"
    RESULTS_SELECTOR = "div[class*='FlightsTicket'], div[class*='ItineraryContainer'], div[data-testid='itinerary-container']"

    COOKIE_SELECTORS = [
        "button[id*='acceptAllCookies']",
        "button[class*='BpkButton'][class*='primary']",
        *BaseScraper.COOKIE_SELECTORS,
    ]

    def _build_url(self, origin: str, outbound: date, return_d: date) -> str:
        # Skyscanner date format: YYMMDD
        out = outbound.strftime("%y%m%d")
        ret = return_d.strftime("%y%m%d")
        return (
            f"https://www.skyscanner.de/transport/flights/{origin.lower()}/pmi/{out}/{ret}/"
            f"?adults=1&cabinclass=economy&currency=EUR"
        )

    def _parse_results(self, soup: BeautifulSoup, origin: str,
                       outbound: date, return_d: date) -> list[FlightOffer]:
        offers: list[FlightOffer] = []

        result_cards = (
            soup.select("div[data-testid='itinerary-container']")
            or soup.select("div[class*='FlightsTicket_container']")
            or soup.select("div[class*='ItineraryContainer']")
        )

        for card in result_cards[:20]:
            # Price
            price_el = (
                card.select_one("span[class*='Price_mainPriceContainer']")
                or card.select_one("div[class*='price'] span")
                or card.select_one("[data-testid='price']")
                or card.select_one("span[class*='BpkText'][class*='price']")
            )
            if not price_el:
                continue
            price = parse_price(price_el.get_text(strip=True))
            if not price or price <= 0:
                continue

            # Airline
            airline_el = (
                card.select_one("span[class*='LogoImage']")
                or card.select_one("img[class*='logo']")
                or card.select_one("[data-testid='carrier-name']")
                or card.select_one("span[class*='airline']")
            )
            if airline_el:
                airline = airline_el.get("alt") or airline_el.get_text(strip=True)
            else:
                airline = "Unbekannt"

            # Stops
            stop_el = (
                card.select_one("span[class*='StopsIndicator']")
                or card.select_one("[data-testid='stops']")
                or card.select_one("span[class*='stops']")
            )
            stop_text = stop_el.get_text(strip=True).lower() if stop_el else ""
            if "direkt" in stop_text or "nonstop" in stop_text or "0 stopp" in stop_text:
                stops = 0
            else:
                m = re.search(r"(\d+)", stop_text)
                stops = int(m.group(1)) if m else 1

            # Departure time
            time_el = (
                card.select_one("span[class*='departure-time']")
                or card.select_one("span[class*='LegInfo_routeDepart']")
                or card.select_one("time")
            )
            dep_time = time_el.get_text(strip=True)[:5] if time_el else ""

            # Booking URL
            link_el = card.select_one("a[href*='/transport/flights/']")
            href = link_el["href"] if link_el and link_el.get("href") else ""
            if href.startswith("/"):
                booking_url = "https://www.skyscanner.de" + href
            else:
                booking_url = href or self.driver.current_url

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
