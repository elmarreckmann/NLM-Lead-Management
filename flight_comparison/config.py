"""Central configuration for the flight comparison tool."""

import os
from datetime import date, timedelta
from dotenv import load_dotenv

load_dotenv()

# --- API Credentials ---
AMADEUS_API_KEY = os.getenv("AMADEUS_API_KEY", "")
AMADEUS_API_SECRET = os.getenv("AMADEUS_API_SECRET", "")
DUFFEL_API_KEY = os.getenv("DUFFEL_API_KEY", "")

# --- Search Parameters ---
ORIGIN_AIRPORTS = ["PAD", "HAJ", "DUS"]
DESTINATION_AIRPORT = "PMI"

SEARCH_START_DATE = date(2026, 5, 18)
SEARCH_END_DATE = date(2026, 6, 23)   # latest outbound so return ≤ 30 Jun
RETURN_LATEST_DATE = date(2026, 6, 30)

MIN_NIGHTS = 7
MAX_NIGHTS = 10

PASSENGERS_ADULTS = 1

# --- Scraping ---
SCRAPING_MIN_DELAY = float(os.getenv("SCRAPING_MIN_DELAY", 2))
SCRAPING_MAX_DELAY = float(os.getenv("SCRAPING_MAX_DELAY", 5))
HEADLESS_BROWSER = os.getenv("HEADLESS_BROWSER", "true").lower() == "true"
CHROME_BINARY_PATH = os.getenv("CHROME_BINARY_PATH", "")
REQUEST_TIMEOUT = 30  # seconds

# --- Output ---
OUTPUT_CSV = "flights_mallorca.csv"
TOP_N_RESULTS = 10

# --- Derived: all outbound dates ---
def get_outbound_dates() -> list[date]:
    dates = []
    current = SEARCH_START_DATE
    while current <= SEARCH_END_DATE:
        dates.append(current)
        current += timedelta(days=1)
    return dates


def get_return_dates(outbound: date) -> list[date]:
    """Return all valid return dates for a given outbound date."""
    dates = []
    for nights in range(MIN_NIGHTS, MAX_NIGHTS + 1):
        ret = outbound + timedelta(days=nights)
        if ret <= RETURN_LATEST_DATE:
            dates.append(ret)
    return dates
