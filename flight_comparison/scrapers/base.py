"""Base scraper: Selenium + BeautifulSoup scaffolding shared by all portals."""

import sys
import time
from abc import ABC, abstractmethod
from datetime import date

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

try:
    from webdriver_manager.chrome import ChromeDriverManager
    _WDM_AVAILABLE = True
except ImportError:
    _WDM_AVAILABLE = False

sys.path.insert(0, "..")
from config import CHROME_BINARY_PATH, HEADLESS_BROWSER, SCRAPING_MAX_DELAY, SCRAPING_MIN_DELAY
from models import FlightOffer
from utils import get_logger, random_delay, random_user_agent


class BaseScraper(ABC):
    """Abstract base for all portal scrapers.

    Usage:
        with KayakScraper() as scraper:
            offers = scraper.search("DUS", date(2026, 5, 18), date(2026, 5, 25))
    """

    SOURCE_NAME: str = "Unknown"
    PAGE_LOAD_TIMEOUT: int = 30
    WAIT_FOR_RESULTS: int = 20   # seconds to wait for price elements

    # CSS selector that indicates results are loaded (override per portal)
    RESULTS_SELECTOR: str = "body"

    # Cookie-banner button selectors (tried in order)
    COOKIE_SELECTORS: list[str] = [
        "[data-testid='accept-button']",
        "#accept-all-cookies",
        ".accept-cookies",
        "button[aria-label*='Accept']",
        "button[aria-label*='Akzeptieren']",
        "#onetrust-accept-btn-handler",
        ".js-accept-cookies",
        "[id*='cookie'] button",
        "button[class*='cookie']",
    ]

    def __init__(self) -> None:
        self.driver: webdriver.Chrome | None = None
        self.logger = get_logger(self.__class__.__name__)

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "BaseScraper":
        self._setup_driver()
        return self

    def __exit__(self, *_) -> None:
        self.close()

    def close(self) -> None:
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None

    # ------------------------------------------------------------------
    # Driver setup
    # ------------------------------------------------------------------

    def _setup_driver(self) -> None:
        options = Options()
        if HEADLESS_BROWSER:
            options.add_argument("--headless=new")

        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        options.add_argument("--window-size=1440,900")
        options.add_argument("--lang=de-DE")
        options.add_argument(f"user-agent={random_user_agent()}")

        if CHROME_BINARY_PATH:
            options.binary_location = CHROME_BINARY_PATH

        if _WDM_AVAILABLE:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
        else:
            self.driver = webdriver.Chrome(options=options)

        # Mask webdriver property via JS
        self.driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
        )
        self.driver.set_page_load_timeout(self.PAGE_LOAD_TIMEOUT)

    # ------------------------------------------------------------------
    # Navigation helpers
    # ------------------------------------------------------------------

    def _load_page(self, url: str) -> bool:
        """Navigate to *url*. Returns False on hard failure."""
        try:
            self.driver.get(url)
            return True
        except TimeoutException:
            self.logger.warning("Page load timed out: %s", url)
            return False
        except WebDriverException as exc:
            self.logger.error("WebDriver error loading %s: %s", url, exc)
            return False

    def _wait_for(self, css_selector: str, timeout: int | None = None) -> bool:
        """Wait until *css_selector* is present. Returns False on timeout."""
        t = timeout or self.WAIT_FOR_RESULTS
        try:
            WebDriverWait(self.driver, t).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, css_selector))
            )
            return True
        except TimeoutException:
            return False

    def _dismiss_cookie_banner(self) -> None:
        for sel in self.COOKIE_SELECTORS:
            try:
                btn = WebDriverWait(self.driver, 3).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, sel))
                )
                btn.click()
                time.sleep(0.5)
                return
            except Exception:
                continue

    def _get_soup(self) -> BeautifulSoup:
        return BeautifulSoup(self.driver.page_source, "lxml")

    def _scroll_to_load(self, times: int = 3, pause: float = 1.5) -> None:
        for _ in range(times):
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(pause)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @abstractmethod
    def _build_url(self, origin: str, outbound: date, return_d: date) -> str:
        """Return the search URL for this portal."""

    @abstractmethod
    def _parse_results(self, soup: BeautifulSoup, origin: str,
                       outbound: date, return_d: date) -> list[FlightOffer]:
        """Parse the loaded page and return flight offers."""

    def search(self, origin: str, outbound: date, return_d: date) -> list[FlightOffer]:
        """High-level search: navigate → wait → parse → return offers."""
        url = self._build_url(origin, outbound, return_d)
        self.logger.info("[%s] %s  %s → %s", self.SOURCE_NAME, origin,
                         outbound.isoformat(), return_d.isoformat())

        if not self._load_page(url):
            return []

        self._dismiss_cookie_banner()
        random_delay(1.0, 2.0)

        results_found = self._wait_for(self.RESULTS_SELECTOR)
        if not results_found:
            self.logger.warning("[%s] Results selector not found – trying anyway", self.SOURCE_NAME)

        self._scroll_to_load()
        random_delay(SCRAPING_MIN_DELAY, SCRAPING_MAX_DELAY)

        try:
            soup = self._get_soup()
            offers = self._parse_results(soup, origin, outbound, return_d)
            self.logger.info("[%s] Found %d offers", self.SOURCE_NAME, len(offers))
            return offers
        except Exception as exc:
            self.logger.error("[%s] Parse error: %s", self.SOURCE_NAME, exc)
            return []


# ------------------------------------------------------------------
# Shared helpers
# ------------------------------------------------------------------

def parse_price(raw: str) -> float | None:
    """Convert '1.234,56 €' or '1234.56' to float. Returns None if unparseable."""
    if not raw:
        return None
    cleaned = (
        raw.replace("\xa0", "")
           .replace(" ", "")
           .replace("€", "")
           .replace("EUR", "")
           .replace("$", "")
    )
    # Handle German format: 1.234,56 → 1234.56
    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None
