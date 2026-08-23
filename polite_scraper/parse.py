from __future__ import annotations

import re
from html.parser import HTMLParser
from urllib.parse import urljoin

from .models import BookRecord


_WHITESPACE = re.compile(r"\s+")
_RATING_WORDS = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}


def normalize_text(value: str) -> str:
    return _WHITESPACE.sub(" ", value).strip()


def _parse_price(value: str) -> float:
    cleaned = normalize_text(value).replace("£", "").replace(",", "")
    return float(cleaned)


class CatalogueParser(HTMLParser):
    """Extracts real article.product_pod records, not page-level metadata."""

    def __init__(self, *, page: int, base_url: str):
        super().__init__(convert_charrefs=True)
        self.page = page
        self.base_url = base_url
        self.records: list[BookRecord] = []
        self._book: dict[str, object] | None = None
        self._capture: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        classes = set((attributes.get("class") or "").split())
        if tag == "article" and "product_pod" in classes:
            self._book = {
                "title": "",
                "price": "",
                "availability": "",
                "rating": 0,
                "product_url": "",
            }
        if self._book is None:
            return
        if tag == "h3":
            self._capture = "title"
            self._text = []
        elif tag == "a" and self._capture == "title":
            href = attributes.get("href") or ""
            self._book["title"] = attributes.get("title") or ""
            self._book["product_url"] = urljoin(self.base_url, href)
        elif tag == "p" and "price_color" in classes:
            self._capture = "price"
            self._text = []
        elif tag == "p" and "availability" in classes:
            self._capture = "availability"
            self._text = []
        elif tag == "p" and "star-rating" in classes:
            rating = next(
                (_RATING_WORDS[word] for word in classes if word in _RATING_WORDS),
                0,
            )
            self._book["rating"] = rating

    def handle_data(self, data: str) -> None:
        if self._book is not None and self._capture is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._book is None:
            return
        if tag in {"h3", "p"} and self._capture is not None:
            if self._capture != "title":
                self._book[self._capture] = normalize_text("".join(self._text))
            self._capture = None
            self._text = []
        if tag == "article":
            self.records.append(
                BookRecord(
                    title=normalize_text(str(self._book["title"])),
                    price_gbp=_parse_price(str(self._book["price"])),
                    availability=normalize_text(str(self._book["availability"])),
                    rating=int(self._book["rating"]),
                    product_url=str(self._book["product_url"]),
                    source_page=self.page,
                )
            )
            self._book = None


def parse_catalogue(html: str, *, page: int, base_url: str) -> list[BookRecord]:
    parser = CatalogueParser(page=page, base_url=base_url)
    parser.feed(html)
    parser.close()
    return parser.records