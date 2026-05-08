"""Shared HTTP session for all direct airline clients."""

import time
import requests
from utils import get_logger, random_delay, random_user_agent

logger = get_logger("airlines.base")


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": random_user_agent(),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Cache-Control": "no-cache",
    })
    return s


def get_json(session: requests.Session, url: str, params: dict,
             extra_headers: dict | None = None, timeout: int = 20) -> dict | list | None:
    """GET with retry-on-429 and structured error logging."""
    headers = extra_headers or {}
    for attempt in range(3):
        try:
            resp = session.get(url, params=params, headers=headers, timeout=timeout)
            if resp.status_code == 429:
                wait = 10 * (attempt + 1)
                logger.warning("Rate limited by %s – waiting %ds", url, wait)
                time.sleep(wait)
                continue
            if resp.status_code == 403:
                logger.warning("403 Forbidden from %s (blocked)", url)
                return None
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.JSONDecodeError:
            logger.error("Non-JSON response from %s", url)
            return None
        except requests.RequestException as exc:
            logger.error("Request error %s: %s", url, exc)
            if attempt < 2:
                random_delay(2, 4)
    return None
