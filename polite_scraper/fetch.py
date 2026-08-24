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

from .models import utc_now


class FetchError(RuntimeError):
    """A page could not be fetched or was not permitted by robots.txt."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class RobotsDeniedError(FetchError):
    """The target URL is disallowed by robots.txt."""


class OpenUrl(Protocol):
    def __call__(self, request: Request, timeout: float): ...


@dataclass(frozen=True)
class CacheEntry:
    body: str
    fetched_at: str


@dataclass(frozen=True)
class FetchResponse:
    url: str
    body: str
    fetched_at: str
    cache_hit: bool
    network_fetch: bool
    robots_allowed: bool = True
    retries: int = 0


class FileCache:
    """Filesystem cache containing only successful HTTP response bodies."""

    def __init__(self, directory: Path):
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)

    def _path(self, url: str) -> Path:
        key = hashlib.sha256(url.encode("utf-8")).hexdigest()
        return self.directory / f"{key}.json"

    def read(self, url: str) -> CacheEntry | None:
        path = self._path(url)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            body = payload.get("body")
            if not isinstance(body, str):
                return None
            fetched_at = payload.get("fetched_at")
            if not isinstance(fetched_at, str) or not fetched_at:
                # Backward-compatible handling of cache entries from the older
                # catalogue-only implementation. The cache file timestamp is
                # used as provenance rather than inventing a network time.
                fetched_at = __import__("datetime").datetime.fromtimestamp(
                    path.stat().st_mtime,
                    tz=__import__("datetime").timezone.utc,
                ).isoformat()
            return CacheEntry(body=body, fetched_at=fetched_at)
        except (OSError, json.JSONDecodeError):
            return None

    def write(self, url: str, body: str, fetched_at: str) -> None:
        path = self._path(url)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(
                {"url": url, "body": body, "fetched_at": fetched_at},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        temporary.replace(path)


class PoliteFetcher:
    """Fetch with robots checks, identity, timeout, pacing, cache and one retry."""

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
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        if min_delay_seconds < 0.5:
            raise ValueError("min_delay_seconds must be at least 0.5 seconds")
        if not user_agent.strip():
            raise ValueError("user_agent must not be empty")
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
        self.network_fetch_attempts = 0
        self.network_intervals_seconds: list[float] = []
        self.retry_attempts = 0

    def _wait_for_throttle(self) -> None:
        if self._last_network_started_at is None:
            return
        elapsed = self.clock_fn() - self._last_network_started_at
        remaining = self.min_delay_seconds - elapsed
        if remaining > 0:
            self.sleep_fn(remaining)

    def _record_network_start(self) -> None:
        self._wait_for_throttle()
        started_at = self.clock_fn()
        if self._last_network_started_at is not None:
            self.network_intervals_seconds.append(started_at - self._last_network_started_at)
        self._last_network_started_at = started_at
        self.network_fetch_attempts += 1

    @staticmethod
    def _response_status(response: object) -> int:
        status = getattr(response, "status", None)
        if isinstance(status, int):
            return status
        getcode = getattr(response, "getcode", None)
        if callable(getcode):
            code = getcode()
            if isinstance(code, int):
                return code
        return 200

    @staticmethod
    def _retryable(exc: FetchError) -> bool:
        return exc.status_code is None and "timed out" in str(exc) or (
            exc.status_code is not None and 500 <= exc.status_code <= 599
        )

    def _network_once(self, url: str) -> tuple[str, str]:
        self._record_network_start()
        request = Request(url, headers={"User-Agent": self.user_agent}, method="GET")
        try:
            response = self.opener(request, timeout=self.timeout_seconds)
            status_code = self._response_status(response)
            if not 200 <= status_code <= 299:
                raise FetchError(
                    f"HTTP {status_code} for {url}", status_code=status_code
                )
            raw = response.read()
            body = raw.decode("utf-8", errors="replace")
            return body, utc_now()
        except HTTPError as exc:
            raise FetchError(
                f"HTTP {exc.code} for {url}", status_code=exc.code
            ) from exc
        except TimeoutError as exc:
            raise FetchError(f"fetch timed out for {url}") from exc
        except URLError as exc:
            if isinstance(getattr(exc, "reason", None), TimeoutError):
                raise FetchError(f"fetch timed out for {url}") from exc
            raise FetchError(f"fetch failed for {url}: {exc.reason}") from exc
        except OSError as exc:
            raise FetchError(f"fetch failed for {url}: {exc}") from exc

    def _open(self, url: str) -> tuple[str, str, int]:
        retries = 0
        for attempt in range(2):
            try:
                body, fetched_at = self._network_once(url)
                return body, fetched_at, retries
            except FetchError as exc:
                if attempt == 0 and self._retryable(exc):
                    retries += 1
                    self.retry_attempts += 1
                    continue
                raise
        raise AssertionError("unreachable")

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
        metadata: dict[str, str | None]
        if parser is None:
            cached = self.cache.read(robots_url)
            if cached is not None:
                self.robots_cache_hits += 1
                robots_body = cached.body
                metadata = {
                    "robots_url": robots_url,
                    "policy_source": "successful_response_cache",
                    "robots_fetch_error": None,
                }
            else:
                try:
                    robots_body, fetched_at, _ = self._open(robots_url)
                except FetchError as exc:
                    # An unavailable robots endpoint is not interpreted as an
                    # explicit denial. The failure is preserved in evidence.
                    robots_body = ""
                    metadata = {
                        "robots_url": robots_url,
                        "policy_source": "unavailable_default_allow",
                        "robots_fetch_error": str(exc),
                    }
                else:
                    self.cache.write(robots_url, robots_body, fetched_at)
                    self.robots_fetches += 1
                    metadata = {
                        "robots_url": robots_url,
                        "policy_source": "successful_response_network",
                        "robots_fetch_error": None,
                    }
            parser = RobotFileParser()
            parser.set_url(robots_url)
            parser.parse(robots_body.splitlines())
            self._robots_cache[robots_url] = parser
        else:
            metadata = {
                "robots_url": robots_url,
                "policy_source": "in_memory_policy",
                "robots_fetch_error": None,
            }

        allowed = parser.can_fetch(self.user_agent, url)
        self.robots_decisions[url] = allowed
        self.robots_decision_details[url] = {**metadata, "allowed": allowed}
        return allowed

    def fetch(self, url: str) -> FetchResponse:
        allowed = self._allowed(url)
        if not allowed:
            raise RobotsDeniedError(f"robots.txt disallows {url}")

        cached = self.cache.read(url)
        if cached is not None:
            return FetchResponse(
                url=url,
                body=cached.body,
                fetched_at=cached.fetched_at,
                cache_hit=True,
                network_fetch=False,
                robots_allowed=allowed,
                retries=0,
            )

        body, fetched_at, retries = self._open(url)
        self.cache.write(url, body, fetched_at)
        return FetchResponse(
            url=url,
            body=body,
            fetched_at=fetched_at,
            cache_hit=False,
            network_fetch=True,
            robots_allowed=allowed,
            retries=retries,
        )
