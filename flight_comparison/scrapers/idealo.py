"""Idealo Flüge scraper."""

import re
import sys
from datetime import date

from bs4 import BeautifulSoup

sys.path.insert(0, "..")
from models import FlightOffer
from .base import BaseScraper, parse_price


class IdealoScraper(BaseScraper):
    SOURCE_NAME = "Idealo"
    RESULTS_SELECTOR = "div[class*='OfferList'], div[class*='offer-item'], section[class*='results']"

    COOKIE_SELECTORS = [
        "button[class*='CookieBanner-acceptAll']",
        "button[data-testid='uc-accept-all-button']",
        *BaseScraper.COOKIE_SELECTORS,
    ]

    def _build_url(self, origin: str, outbound: date, return_d: date) -> str:
        out = outbound.strftime("%Y-%m-%d")
        ret = return_d.strftime("%Y-%m-%d")
        return (
            f"https://www.idealo.de/flug/suche/Roundtrip/{origin}/PMI/{out}/{ret}.html"
            f"?adults=1&cabin=ECONOMY&sort=CHEAPEST"
        )

    def _parse_results(self, soup: BeautifulSoup, origin: str,
                       outbound: date, return_d: date) -> list[FlightOffer]:
        offers: list[FlightOffer] = []

        result_cards = (
            soup.select("div[class*='offer-item']")
            or soup.select("article[class*='OfferItem']")
            or soup.select("li[class*='result']")
            or soup.select("div[class*='FlightOffer']")
        )

        for card in result_cards[:20]:
            # Price
            price_el = (
                card.select_one("span[class*='price']")
                or card.select_one("div[class*='Price']")
                or card.select_one("strong[class*='offerPrice']")
                or card.select_one("[data-testid='price']")
            )
            if not price_el:
                continue
            price = parse_price(price_el.get_text(strip=True))
            if not price or price <= 0:
                continue

            # Airline
            airline_el = (
                card.select_one("img[class*='airline']")
                or card.select_one("span[class*='carrier']")
                or card.select_one("div[class*='AirlineName']")
            )
            if airline_el:
                airline = airline_el.get("alt") or airline_el.get_text(strip=True)
            else:
                airline = "Unbekannt"

            # Stops
            stop_el = (
                card.select_one("span[class*='stop']")
                or card.select_one("div[class*='Stop']")
            )
            stop_text = stop_el.get_text(strip=True).lower() if stop_el else ""
            if "direkt" in stop_text or "nonstop" in stop_text:
                stops = 0
            else:
                m = re.search(r"(\d+)", stop_text)
                stops = int(m.group(1)) if m else 1

            # Departure time
            time_el = (
                card.select_one("time")
                or card.select_one("span[class*='departureTime']")
                or card.select_one("div[class*='time'] span")
            )
            dep_time = time_el.get_text(strip=True)[:5] if time_el else ""

            # Booking link
            link_el = card.select_one("a[href]")
            href = link_el["href"] if link_el and link_el.get("href") else ""
            if href.startswith("/"):
                booking_url = "https://www.idealo.de" + href
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
