from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


DEFAULT_BASE_URL = "https://books.toscrape.com/"
DEFAULT_USER_AGENT = "FlyRank-PoliteScraper/1.0 (+https://github.com/flyrank/backend-assignment-5)"


@dataclass(frozen=True)
class ScraperConfig:
    base_url: str = DEFAULT_BASE_URL
    user_agent: str = DEFAULT_USER_AGENT
    timeout_seconds: float = 10.0
    min_delay_seconds: float = 0.5
    cache_dir: Path = Path("cache")
    output_dir: Path = Path("output")

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        if self.min_delay_seconds < 0.5:
            raise ValueError("min_delay_seconds must be at least 0.5 seconds")
        if not self.user_agent.strip():
            raise ValueError("user_agent must not be empty")

    def page_url(self, page: int) -> str:
        if page < 1:
            raise ValueError("catalogue page must be at least 1")
        suffix = "" if page == 1 else f"catalogue/page-{page}.html"
        return self.base_url.rstrip("/") + ("/index.html" if page == 1 else f"/{suffix}")