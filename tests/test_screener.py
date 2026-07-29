"""Yahoo screener-parsing tests that need no network.

A predefined screen's members come back in the same record shape ``/v7/finance/
quote`` returns, so a member is a ``Quote``; the fixtures cover that reuse, the
match total, and the error envelope.
"""

import pytest

from finyahoo import Quote, Screen, YahooParseError, YahooRequestError
from finyahoo.screener import parse_screener

_SCREEN = """
{"finance": {"error": null, "result": [{
  "id": "abc", "canonicalName": "MOST_ACTIVES", "title": "Most Actives",
  "total": 211, "count": 2,
  "quotes": [
    {"symbol": "NVDA", "longName": "NVIDIA", "regularMarketPrice": 900.0, "currency": "USD"},
    {"symbol": "INTC", "shortName": "Intel", "regularMarketPrice": 30.0}
  ]
}]}}
"""

_ERROR = '{"finance": {"result": null, "error": {"code": "Bad Request", "description": "no"}}}'


def test_parses_the_screen_id_title_and_total():
    screen = parse_screener(_SCREEN)
    assert isinstance(screen, Screen)
    assert screen.screen_id == "MOST_ACTIVES"
    assert screen.title == "Most Actives"
    assert screen.total == 211


def test_members_are_quotes():
    screen = parse_screener(_SCREEN)
    assert isinstance(screen.members[0], Quote)
    assert [m.symbol for m in screen.members] == ["NVDA", "INTC"]
    assert screen.members[0].price == pytest.approx(900.0)
    assert screen.members[0].name == "NVIDIA"


def test_error_envelope_raises_request_error():
    with pytest.raises(YahooRequestError):
        parse_screener(_ERROR)


def test_non_screener_shape_raises_parse_error():
    with pytest.raises(YahooParseError):
        parse_screener('{"unexpected": "shape"}')
