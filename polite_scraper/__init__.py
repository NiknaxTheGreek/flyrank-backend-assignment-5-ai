"""FlyRank Backend Assignment 5: a small, polite Books to Scrape pipeline."""

from .models import BookRecord, RunReport
from .pipeline import PoliteScraper

__all__ = ["BookRecord", "PoliteScraper", "RunReport"]