"""Check24 Flug scraper."""

import re
import sys
from datetime import date

from bs4 import BeautifulSoup

sys.path.insert(0, "..")
from models import FlightOffer
from .base import BaseScraper, parse_price


class Check24Scraper(BaseScraper):
    SOURCE_NAME = "Check24"
    RESULTS_SELECTOR = "div.flight-offer, div[class*='FlightOffer'], li[class*='result-item']"

    COOKIE_SELECTORS = [
        "button#onetrust-accept-btn-handler",
        "button.btn-primary[data-testid*='accept']",
        "button[class*='CookieBanner'][class*='accept']",
        *BaseScraper.COOKIE_SELECTORS,
    ]

    def _build_url(self, origin: str, outbound: date, return_d: date) -> str:
        out = outbound.strftime("%d.%m.%Y")
        ret = return_d.strftime("%d.%m.%Y")
        return (
            f"https://flug.check24.de/flug/suche"
            f"?origin={origin}&destination=PMI"
            f"&departure={out}&return={ret}"
            f"&adults=1&children=0&infants=0&cabinClass=ECONOMY"
            f"&sort=PRICE_ASC"
        )

    def _parse_results(self, soup: BeautifulSoup, origin: str,
                       outbound: date, return_d: date) -> list[FlightOffer]:
        offers: list[FlightOffer] = []

        result_cards = (
            soup.select("div[class*='flight-offer']")
            or soup.select("li[class*='result-item']")
            or soup.select("div[class*='FlightResultItem']")
            or soup.select("article[class*='flight']")
        )

        for card in result_cards[:20]:
            # Price
            price_el = (
                card.select_one("span[class*='price']")
                or card.select_one("div[class*='total-price']")
                or card.select_one("[data-testid='price']")
                or card.select_one("strong[class*='price']")
            )
            if not price_el:
                continue
            price = parse_price(price_el.get_text(strip=True))
            if not price or price <= 0:
                continue

            # Airline
            airline_el = (
                card.select_one("span[class*='airline-name']")
                or card.select_one("div[class*='carrier']")
                or card.select_one("img[class*='airline']")
            )
            if airline_el:
                airline = airline_el.get("alt") or airline_el.get_text(strip=True)
            else:
                airline = "Unbekannt"

            # Stops
            stop_el = (
                card.select_one("span[class*='stops']")
                or card.select_one("div[class*='stop']")
                or card.select_one("[data-testid*='stop']")
            )
            stop_text = stop_el.get_text(strip=True).lower() if stop_el else ""
            if "direkt" in stop_text or "nonstop" in stop_text:
                stops = 0
            else:
                m = re.search(r"(\d+)", stop_text)
                stops = int(m.group(1)) if m else 1

            # Departure time
            time_el = (
                card.select_one("span[class*='departure-time']")
                or card.select_one("time[class*='depart']")
                or card.select_one("div[class*='time'] span:first-child")
            )
            dep_time = time_el.get_text(strip=True)[:5] if time_el else ""

            # Booking link
            link_el = card.select_one("a[href*='flug']")
            href = link_el["href"] if link_el and link_el.get("href") else ""
            if href.startswith("/"):
                booking_url = "https://flug.check24.de" + href
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
