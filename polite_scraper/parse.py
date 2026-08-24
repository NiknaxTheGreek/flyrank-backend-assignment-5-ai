from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urldefrag, urljoin

from .models import BookLink, BookRecord


_WHITESPACE = re.compile(r"\s+")
_RATING_WORDS = {"One", "Two", "Three", "Four", "Five"}


def normalize_text(value: str) -> str:
    return _WHITESPACE.sub(" ", value).strip()


def parse_price_gbp(value: str) -> float:
    cleaned = normalize_text(value).replace("£", "").replace(",", "")
    return float(cleaned)


@dataclass(frozen=True)
class CatalogueResult:
    links: list[BookLink]
    next_url: str | None


class CatalogueParser(HTMLParser):
    """Discover canonical product URLs and the site's actual next-page link."""

    def __init__(self, *, source_page: int, page_url: str):
        super().__init__(convert_charrefs=True)
        self.source_page = source_page
        self.page_url = page_url
        self.links: list[BookLink] = []
        self.next_url: str | None = None
        self._in_product = False
        self._in_product_h3 = False
        self._in_next_li = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        classes = set((attributes.get("class") or "").split())

        if tag == "article" and "product_pod" in classes:
            self._in_product = True
            return
        if self._in_product and tag == "h3":
            self._in_product_h3 = True
            return
        if self._in_product_h3 and tag == "a":
            href = attributes.get("href")
            if href:
                absolute = urldefrag(urljoin(self.page_url, href))[0]
                self.links.append(BookLink(absolute, self.source_page))
            return

        if tag == "li" and "next" in classes:
            self._in_next_li = True
            return
        if self._in_next_li and tag == "a":
            href = attributes.get("href")
            if href:
                self.next_url = urldefrag(urljoin(self.page_url, href))[0]

    def handle_endtag(self, tag: str) -> None:
        if tag == "h3":
            self._in_product_h3 = False
        elif tag == "article":
            self._in_product = False
            self._in_product_h3 = False
        elif tag == "li" and self._in_next_li:
            self._in_next_li = False


class DetailParser(HTMLParser):
    """Extract the exact raw/provenance fields required from one detail page."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.price_text = ""
        self.availability_text = ""
        self.rating_text = ""
        self.description: str | None = None

        self._capture: str | None = None
        self._text: list[str] = []
        self._description_marker_seen = False
        self._description_capture_pending = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        classes = set((attributes.get("class") or "").split())

        if tag == "h1":
            self._capture = "title"
            self._text = []
        elif tag == "p" and "price_color" in classes and not self.price_text:
            self._capture = "price_text"
            self._text = []
        elif tag == "p" and "availability" in classes and not self.availability_text:
            self._capture = "availability_text"
            self._text = []
        elif tag == "p" and "star-rating" in classes and not self.rating_text:
            self.rating_text = next((word for word in classes if word in _RATING_WORDS), "")
        elif tag == "div" and attributes.get("id") == "product_description":
            self._description_marker_seen = True
        elif tag == "p" and self._description_capture_pending and self.description is None:
            self._capture = "description"
            self._text = []
            self._description_capture_pending = False

    def handle_data(self, data: str) -> None:
        if self._capture is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._capture == "title" and tag == "h1":
            self.title = normalize_text("".join(self._text))
            self._capture = None
            self._text = []
        elif self._capture in {"price_text", "availability_text", "description"} and tag == "p":
            value = normalize_text("".join(self._text))
            if self._capture == "description":
                self.description = value or None
            else:
                setattr(self, self._capture, value)
            self._capture = None
            self._text = []
        elif tag == "div" and self._description_marker_seen and self.description is None:
            self._description_marker_seen = False
            self._description_capture_pending = True


def parse_catalogue(html: str, *, source_page: int, page_url: str) -> CatalogueResult:
    parser = CatalogueParser(source_page=source_page, page_url=page_url)
    parser.feed(html)
    parser.close()
    return CatalogueResult(parser.links, parser.next_url)


def parse_detail(
    html: str,
    *,
    product_url: str,
    source_page: int,
    fetched_at: str,
) -> BookRecord:
    parser = DetailParser()
    parser.feed(html)
    parser.close()
    return BookRecord(
        title=parser.title,
        product_url=product_url,
        price_text=parser.price_text,
        price_gbp=parse_price_gbp(parser.price_text),
        availability_text=parser.availability_text,
        rating_text=parser.rating_text,
        description=parser.description,
        source_page=source_page,
        fetched_at=fetched_at,
    )
