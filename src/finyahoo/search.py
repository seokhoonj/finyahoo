"""Parsing Yahoo's search response into symbol matches and related news.

Pure function of the payload -- no network. ``/v1/finance/search`` is symbol
lookup: a free-text query in ("apple", "Samsung", "005930"), a ranked list of
matching securities out, plus the news headlines Yahoo attaches to the query. The
top level is a bare object -- no ``{result, error}`` envelope -- so this walks it
directly.

Matches carry enough to identify and route a symbol (its exchange, type, sector);
the news is a convenience Yahoo bundles in, carried but not the point.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .errors import YahooParseError
from .payload import as_number, as_str, each_dict, epoch_to_datetime, load_json


@dataclass(frozen=True, slots=True)
class SearchMatch:
    """One security matching the query.

    ``score`` is Yahoo's relevance ranking (higher is a better match); the list is
    returned in Yahoo's order, which is that ranking.
    """

    symbol: str
    name: str | None
    exchange: str | None
    quote_type: str | None
    type_display: str | None
    sector: str | None
    industry: str | None
    score: float | None


@dataclass(frozen=True, slots=True)
class SearchNews:
    """One news headline Yahoo attached to the query."""

    uuid: str
    title: str | None
    publisher: str | None
    link: str | None
    published_at: datetime | None
    related_tickers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Search:
    """A query's matching securities and the news beside them."""

    query: str
    matches: tuple[SearchMatch, ...]
    news: tuple[SearchNews, ...]


def parse_search(payload: str, query: str) -> Search:
    """Parse a search response into ``query``'s matches and news.

    Raises:
        YahooParseError: the payload is not JSON, or not the search shape.
    """
    root = load_json(payload, "search")
    if not isinstance(root, dict) or "quotes" not in root:
        raise YahooParseError("search payload has no quotes array")
    matches = tuple(
        SearchMatch(
            symbol       = match.get("symbol", ""),
            name         = as_str(match.get("shortname")) or as_str(match.get("longname")),
            exchange     = as_str(match.get("exchDisp")) or as_str(match.get("exchange")),
            quote_type   = as_str(match.get("quoteType")),
            type_display = as_str(match.get("typeDisp")),
            sector       = as_str(match.get("sector")),
            industry     = as_str(match.get("industry")),
            score        = as_number(match.get("score")),
        )
        for match in each_dict(root.get("quotes", []), "search quotes")
    )
    news = tuple(
        SearchNews(
            uuid            = item.get("uuid", ""),
            title           = as_str(item.get("title")),
            publisher       = as_str(item.get("publisher")),
            link            = as_str(item.get("link")),
            published_at    = epoch_to_datetime(item.get("providerPublishTime")),
            related_tickers = tuple(t for t in item.get("relatedTickers", []) if isinstance(t, str)),
        )
        for item in each_dict(root.get("news", []), "search news")
    )
    return Search(query=query, matches=matches, news=news)
