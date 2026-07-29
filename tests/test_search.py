"""Yahoo search-parsing tests that need no network.

Search has no ``{result, error}`` envelope -- the top level is a bare object with a
``quotes`` array and an optional ``news`` array -- so the fixtures cover that flat
shape, an absent news array, and a payload missing ``quotes`` entirely.
"""

import pytest

from finyahoo import Search, YahooParseError
from finyahoo.search import parse_search

_FULL = """
{"count": 2, "quotes": [
  {"symbol": "AAPL", "shortname": "Apple Inc.", "exchDisp": "NASDAQ", "quoteType": "EQUITY",
   "typeDisp": "Equity", "sector": "Technology", "industry": "Consumer Electronics", "score": 30972.0},
  {"symbol": "APLE", "shortname": "Apple Hospitality REIT", "exchDisp": "NYSE", "score": 1200.0}
 ],
 "news": [
  {"uuid": "abc", "title": "Apple news", "publisher": "TheStreet",
   "link": "https://x", "providerPublishTime": 1785257545, "relatedTickers": ["AAPL"]}
 ]}
"""

_NO_NEWS = '{"count": 1, "quotes": [{"symbol": "AAPL", "shortname": "Apple Inc."}]}'


def test_parses_matches_in_yahoos_ranked_order():
    search = parse_search(_FULL, "apple")
    assert isinstance(search, Search)
    assert [m.symbol for m in search.matches] == ["AAPL", "APLE"]
    assert search.matches[0].sector == "Technology"


def test_query_is_carried_from_the_caller():
    assert parse_search(_FULL, "apple").query == "apple"


def test_news_is_parsed_with_related_tickers():
    news = parse_search(_FULL, "apple").news
    assert news[0].publisher == "TheStreet"
    assert news[0].related_tickers == ("AAPL",)


def test_absent_news_is_empty_not_an_error():
    search = parse_search(_NO_NEWS, "apple")
    assert search.news == ()
    assert search.matches[0].symbol == "AAPL"


def test_a_payload_without_quotes_raises_parse_error():
    with pytest.raises(YahooParseError):
        parse_search('{"count": 0}', "apple")


def test_type_display_carries_yahoos_type_disp():
    """The type_display field carries Yahoo's typeDisp."""
    match = parse_search(_FULL, "apple").matches[0]
    assert match.type_display == "Equity"


def test_related_tickers_keeps_only_strings():
    """A non-string entry in relatedTickers is filtered, so the tuple[str, ...] hint
    stays honest."""
    payload = ('{"quotes": [], "news": [{"uuid": "x", "relatedTickers": ["AAPL", null, 5]}]}')
    assert parse_search(payload, "q").news[0].related_tickers == ("AAPL",)


def test_a_non_numeric_score_becomes_none():
    payload = '{"quotes": [{"symbol": "AAPL", "score": true}], "news": []}'
    assert parse_search(payload, "q").matches[0].score is None
