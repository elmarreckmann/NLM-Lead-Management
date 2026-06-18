"""Google Flights scraper."""

import re
import sys
from datetime import date

from bs4 import BeautifulSoup

sys.path.insert(0, "..")
from models import FlightOffer
from .base import BaseScraper, parse_price


class GoogleFlightsScraper(BaseScraper):
    SOURCE_NAME = "Google Flights"
    # Google Flights loads results into li elements inside a UL
    RESULTS_SELECTOR = "ul.Rk10dc, div[jsname='IWWDBc'], div.yR1LGd"

    COOKIE_SELECTORS = [
        "button[aria-label='Alle akzeptieren']",
        "button[aria-label='Accept all']",
        "#L2AGLb",   # classic Google consent button id
        ".sy4vM",
        *BaseScraper.COOKIE_SELECTORS,
    ]

    def _build_url(self, origin: str, outbound: date, return_d: date) -> str:
        # Google Flights deep-link with encoded trip data
        # Format: origin.dest.date*dest.origin.returnDate
        out = outbound.strftime("%Y-%m-%d")
        ret = return_d.strftime("%Y-%m-%d")
        dest = "PMI"
        fragment = f"{origin}.{dest}.{out}*{dest}.{origin}.{ret};c:EUR;e:1;sd:1;t:f"
        return f"https://www.google.com/travel/flights?hl=de&curr=EUR#flt={fragment}"

    def _parse_results(self, soup: BeautifulSoup, origin: str,
                       outbound: date, return_d: date) -> list[FlightOffer]:
        offers: list[FlightOffer] = []
        booking_url = self.driver.current_url

        # Google Flights renders prices in spans with class YMlIz or similar
        # Try multiple known selector patterns
        price_containers = (
            soup.select("li.pIav2d")           # list items with price
            or soup.select("div.yR1LGd")       # result card
            or soup.select("[data-travelimpact]")
        )

        for container in price_containers[:20]:  # cap at 20 results per page
            price_el = (
                container.select_one("div.YMlIz span")
                or container.select_one("span.YMlIz")
                or container.select_one("[aria-label*='EUR']")
                or container.select_one("span[data-gs]")
            )
            if not price_el:
                continue

            raw_price = price_el.get_text(strip=True)
            price = parse_price(raw_price)
            if not price or price <= 0:
                continue

            airline_el = container.select_one("div.Ir0Voe .sSHqwe, span.h1fkLb, div.sSHqwe")
            airline = airline_el.get_text(strip=True) if airline_el else "Unbekannt"

            # Detect stops
            stop_el = container.select_one("div.EfT7Ae span, span.ogfYpf")
            stop_text = stop_el.get_text(strip=True).lower() if stop_el else ""
            if "nonstop" in stop_text or "direktflug" in stop_text or stop_text == "0":
                stops = 0
            else:
                m = re.search(r"(\d+)", stop_text)
                stops = int(m.group(1)) if m else 1

            # Departure time
            time_el = container.select_one("span.wtdjmc, div.Ak5kof span")
            dep_time = time_el.get_text(strip=True)[:5] if time_el else ""

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
