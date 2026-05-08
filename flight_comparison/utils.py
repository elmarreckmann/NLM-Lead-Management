"""Shared helpers: logging, rate limiting, user-agent rotation."""

import logging
import random
import time

from fake_useragent import UserAgent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)

_ua = None


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def random_delay(min_s: float = 2.0, max_s: float = 5.0) -> None:
    time.sleep(random.uniform(min_s, max_s))


def random_user_agent() -> str:
    global _ua
    try:
        if _ua is None:
            _ua = UserAgent()
        return _ua.random
    except Exception:
        # Fallback if fake-useragent cache fails
        return (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
