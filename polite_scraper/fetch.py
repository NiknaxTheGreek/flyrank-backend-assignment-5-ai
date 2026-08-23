from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser


class FetchError(RuntimeError):
    """A page could not be fetched or was not permitted by robots.txt."""


class RobotsDeniedError(FetchError):
    """The target URL is disallowed by robots.txt."""


class OpenUrl(Protocol):
    def __call__(self, request: Request, timeout: float): ...


@dataclass(frozen=True)
class FetchResponse:
    url: str
    body: str
    cache_hit: bool
    network_fetch: bool
    robots_allowed: bool = True


class FileCache:
    """A filesystem cache that writes only successful response bodies."""

    def __init__(self, directory: Path):
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)

    def _path(self, url: str) -> Path:
        key = hashlib.sha256(url.encode("utf-8")).hexdigest()
        return self.directory / f"{key}.json"

    def read(self, url: str) -> str | None:
        path = self._path(url)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            body = payload.get("body")
            return body if isinstance(body, str) else None
        except (OSError, json.JSONDecodeError):
            return None

    def write(self, url: str, body: str) -> None:
        path = self._path(url)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps({"url": url, "body": body}, ensure_ascii=False),
            encoding="utf-8",
        )
        temporary.replace(path)


class PoliteFetcher:
    """Fetches pages with robots.txt checks, a User-Agent, timeout, cache, and throttle."""

    def __init__(
        self,
        *,
        user_agent: str,
        timeout_seconds: float,
        min_delay_seconds: float,
        cache_dir: Path,
        opener: OpenUrl = urlopen,
        sleep_fn: Callable[[float], None] = time.sleep,
        clock_fn: Callable[[], float] = time.monotonic,
        robots_checker: Callable[[str], bool] | None = None,
    ):
        if min_delay_seconds < 0.5:
            raise ValueError("min_delay_seconds must be at least 0.5 seconds")
        self.user_agent = user_agent
        self.timeout_seconds = timeout_seconds
        self.min_delay_seconds = min_delay_seconds
        self.opener = opener
        self.sleep_fn = sleep_fn
        self.clock_fn = clock_fn
        self.cache = FileCache(cache_dir)
        self.robots_checker = robots_checker
        self._robots_cache: dict[str, RobotFileParser] = {}
        self._last_network_started_at: float | None = None
        self.robots_fetches = 0
        self.robots_cache_hits = 0
        self.robots_decisions: dict[str, bool] = {}
        self.robots_decision_details: dict[str, dict[str, str | bool | None]] = {}
        self._robots_policy_metadata: dict[str, dict[str, str | None]] = {}
        self.network_fetch_attempts = 0
        self.network_intervals_seconds: list[float] = []

    def _wait_for_throttle(self) -> None:
        if self._last_network_started_at is None:
            return
        elapsed = self.clock_fn() - self._last_network_started_at
        remaining = self.min_delay_seconds - elapsed
        if remaining > 0:
            self.sleep_fn(remaining)

    def _open(self, url: str) -> str:
        self._wait_for_throttle()
        network_started_at = self.clock_fn()
        if self._last_network_started_at is not None:
            self.network_intervals_seconds.append(
                network_started_at - self._last_network_started_at
            )
        self._last_network_started_at = network_started_at
        self.network_fetch_attempts += 1
        request = Request(url, headers={"User-Agent": self.user_agent}, method="GET")
        try:
            response = self.opener(request, timeout=self.timeout_seconds)
            raw = response.read()
            body = raw.decode("utf-8", errors="replace")
        except HTTPError as exc:
            raise FetchError(f"HTTP {exc.code} for {url}") from exc
        except (TimeoutError, URLError, OSError) as exc:
            reason = "timed out" if isinstance(exc, TimeoutError) else str(exc)
            raise FetchError(f"fetch failed for {url}: {reason}") from exc
        return body

    def _allowed(self, url: str) -> bool:
        if self.robots_checker is not None:
            allowed = self.robots_checker(url)
            self.robots_decisions[url] = allowed
            self.robots_decision_details[url] = {
                "robots_url": None,
                "policy_source": "injected_checker",
                "robots_fetch_error": None,
                "allowed": allowed,
            }
            return allowed
        robots_url = urljoin(url, "/robots.txt")
        parser = self._robots_cache.get(robots_url)
        if parser is None:
            robots_body = self.cache.read(robots_url)
            if robots_body is not None:
                self.robots_cache_hits += 1
                metadata = {
                    "robots_url": robots_url,
                    "policy_source": "successful_response_cache",
                    "robots_fetch_error": None,
                }
            else:
                try:
                    robots_body = self._open(robots_url)
                except FetchError as exc:
                    # A robots endpoint that is unavailable is not a denial. The
                    # target site remains fetched with the identifying User-Agent.
                    robots_body = ""
                    metadata = {
                        "robots_url": robots_url,
                        "policy_source": "unavailable_default_allow",
                        "robots_fetch_error": str(exc),
                    }
                else:
                    self.cache.write(robots_url, robots_body)
                    metadata = {
                        "robots_url": robots_url,
                        "policy_source": "successful_response_network",
                        "robots_fetch_error": None,
                    }
                self.robots_fetches += 1
            parser = RobotFileParser()
            parser.set_url(robots_url)
            parser.parse(robots_body.splitlines())
            self._robots_cache[robots_url] = parser
            self._robots_policy_metadata[robots_url] = metadata
        allowed = parser.can_fetch(self.user_agent, url)
        self.robots_decisions[url] = allowed
        self.robots_decision_details[url] = {
            **self._robots_policy_metadata[robots_url],
            "allowed": allowed,
        }
        return allowed

    def fetch(self, url: str) -> FetchResponse:
        allowed = self._allowed(url)
        if not allowed:
            raise RobotsDeniedError(f"robots.txt disallows {url}")
        cached = self.cache.read(url)
        if cached is not None:
            return FetchResponse(
                url, cached, cache_hit=True, network_fetch=False, robots_allowed=allowed
            )
        body = self._open(url)
        self.cache.write(url, body)
        return FetchResponse(
            url, body, cache_hit=False, network_fetch=True, robots_allowed=allowed
        )