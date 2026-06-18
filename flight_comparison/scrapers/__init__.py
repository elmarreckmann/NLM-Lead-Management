from .google_flights import GoogleFlightsScraper
from .kayak import KayakScraper
from .skyscanner import SkyscannerScraper
from .check24 import Check24Scraper
from .fluege import FluegeDeScaper
from .idealo import IdealoScraper

ALL_SCRAPERS = [
    GoogleFlightsScraper,
    KayakScraper,
    SkyscannerScraper,
    Check24Scraper,
    FluegeDeScaper,
    IdealoScraper,
]
