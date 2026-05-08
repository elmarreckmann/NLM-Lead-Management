"""Fluege.de scraper."""

import re
import sys
from datetime import date

from bs4 import BeautifulSoup

sys.path.insert(0, "..")
from models import FlightOffer
from .base import BaseScraper, parse_price


class FluegeDeScaper(BaseScraper):
    SOURCE_NAME = "Fluege.de"
    RESULTS_SELECTOR = "div.flight-item, div[class*='ResultItem'], li.result"

    def _build_url(self, origin: str, outbound: date, return_d: date) -> str:
        out = outbound.strftime("%d%m%Y")   # fluege.de uses DDMMYYYY
        ret = return_d.strftime("%d%m%Y")
        return (
            f"https://www.fluege.de/flug/result/"
            f"?dep={origin}&arr=PMI"
            f"&depdate={out}&retdate={ret}"
            f"&adults=1&children=0&infants=0"
            f"&cabin=Y&sort=price"
        )

    def _parse_results(self, soup: BeautifulSoup, origin: str,
                       outbound: date, return_d: date) -> list[FlightOffer]:
        offers: list[FlightOffer] = []

        result_cards = (
            soup.select("div[class*='flight-item']")
            or soup.select("li[class*='result']")
            or soup.select("div[class*='ResultItem']")
            or soup.select("div[class*='offer-row']")
        )

        for card in result_cards[:20]:
            # Price
            price_el = (
                card.select_one("span[class*='price']")
                or card.select_one("div[class*='price']")
                or card.select_one("strong[class*='amount']")
            )
            if not price_el:
                continue
            price = parse_price(price_el.get_text(strip=True))
            if not price or price <= 0:
                continue

            # Airline
            airline_el = (
                card.select_one("img[class*='airline']")
                or card.select_one("span[class*='airline']")
                or card.select_one("div[class*='carrier']")
            )
            if airline_el:
                airline = airline_el.get("alt") or airline_el.get("title") or airline_el.get_text(strip=True)
            else:
                airline = "Unbekannt"

            # Stops
            stop_el = (
                card.select_one("span[class*='stop']")
                or card.select_one("div[class*='connection']")
            )
            stop_text = stop_el.get_text(strip=True).lower() if stop_el else ""
            if "direkt" in stop_text or "nonstop" in stop_text or "0" == stop_text:
                stops = 0
            else:
                m = re.search(r"(\d+)", stop_text)
                stops = int(m.group(1)) if m else 1

            # Departure time
            time_el = (
                card.select_one("span[class*='depart']")
                or card.select_one("td[class*='time']:first-child")
                or card.select_one("div[class*='departure'] span")
            )
            dep_time = time_el.get_text(strip=True)[:5] if time_el else ""

            # Booking link
            link_el = card.select_one("a[href]")
            href = link_el["href"] if link_el and link_el.get("href") else ""
            if href.startswith("/"):
                booking_url = "https://www.fluege.de" + href
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
