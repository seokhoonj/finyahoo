"""Yahoo quoteSummary-parsing tests that need no network.

The fixtures reproduce what makes a profile quietly wrong: a value boxed as
``{"raw": ..}`` vs a bare string, a field Yahoo omits (None, never 0), a module
absent entirely (an index has no financialData), and the error a bad crumb or
unknown ticker returns.
"""

import json

import pytest

from finyahoo import Profile, YahooParseError, YahooRequestError
from finyahoo.profile import parse_profile

_FULL = """
{"quoteSummary": {"error": null, "result": [{
  "quoteType": {"longName": "Samsung Electronics Co., Ltd.", "shortName": "SamsungElec"},
  "assetProfile": {"sector": "Technology", "industry": "Consumer Electronics"},
  "summaryDetail": {
    "marketCap": {"raw": 1674473665200128, "fmt": "1,674.47T"},
    "currency": "KRW",
    "trailingPE": {},
    "fiftyTwoWeekHigh": {"raw": 88800.0},
    "fiftyTwoWeekLow": {"raw": 49900.0},
    "beta": {"raw": 0.98}
  },
  "defaultKeyStatistics": {
    "sharesOutstanding": {"raw": 5764191903},
    "forwardPE": {"raw": 3.908},
    "priceToBook": {"raw": 1.42},
    "trailingEps": {"raw": 8.26}
  },
  "financialData": {
    "revenueGrowth": {"raw": 0.692, "fmt": "69.20%"},
    "earningsGrowth": {"raw": 0.218},
    "profitMargins": {"raw": 0.21459},
    "operatingMargins": {"raw": 0.42751},
    "returnOnEquity": {"raw": 0.18855}
  }
}]}}
"""

# An index (^GSPC-shaped): only summaryDetail, no assetProfile/financialData.
_INDEX = """
{"quoteSummary": {"error": null, "result": [{
  "quoteType": {"shortName": "S&P 500"},
  "summaryDetail": {"currency": "USD", "beta": {"raw": null}}
}]}}
"""

_BAD_CRUMB = """
{"quoteSummary": {"result": null, "error": {"code": "Unauthorized", "description": "Invalid Crumb"}}}
"""


def test_parses_name_sector_and_the_growth_and_margin_figures():
    profile = parse_profile(_FULL, "005930.KS")
    assert isinstance(profile, Profile)
    assert profile.name == "Samsung Electronics Co., Ltd."
    assert profile.sector == "Technology"
    assert profile.revenue_growth == pytest.approx(0.692)
    assert profile.operating_margin == pytest.approx(0.42751)


def test_a_boxed_value_is_unwrapped_to_its_raw_number():
    profile = parse_profile(_FULL, "005930.KS")
    assert profile.market_cap == 1674473665200128
    assert profile.shares_outstanding == 5764191903


def test_a_bare_string_field_is_taken_as_is():
    assert parse_profile(_FULL, "005930.KS").currency == "KRW"


def test_a_field_present_as_an_empty_box_is_none_not_zero():
    """An empty box {} means "present but unset" -- and 0 is a real reading (a stock
    no institution holds), so the absence must not collapse to it."""
    profile = parse_profile(_FULL, "005930.KS")
    assert profile.trailing_pe is None                         # present as an empty box
    assert profile.return_on_equity == pytest.approx(0.18855)  # a real 0.19, not None


def test_a_field_missing_from_a_present_module_is_none_not_zero():
    """The other way a field goes absent: the module is there but the key is not."""
    payload = json.loads(_FULL)
    del payload["quoteSummary"]["result"][0]["financialData"]["returnOnEquity"]
    assert parse_profile(json.dumps(payload), "005930.KS").return_on_equity is None


def test_a_module_absent_entirely_leaves_its_fields_none():
    """An index has no financialData or assetProfile module at all."""
    profile = parse_profile(_INDEX, "^GSPC")
    assert profile.sector is None
    assert profile.revenue_growth is None
    assert profile.currency == "USD"


def test_a_null_raw_is_none():
    assert parse_profile(_INDEX, "^GSPC").beta is None


def test_a_key_in_two_modules_resolves_by_profile_modules_order():
    """When a key appears in two modules with different values, precedence follows
    PROFILE_MODULES (financialData is listed after summaryDetail, so it wins) -- not
    the order Yahoo happened to serialize the modules in, which the merge must not
    depend on."""
    payload = {"quoteSummary": {"error": None, "result": [{
        "financialData": {"currency": "KRW"},   # serialized first, but listed later in PROFILE_MODULES
        "summaryDetail": {"currency": "USD"},
    }]}}
    assert parse_profile(json.dumps(payload), "MU").currency == "KRW"


def test_an_invalid_crumb_is_a_request_error():
    with pytest.raises(YahooRequestError) as excinfo:
        parse_profile(_BAD_CRUMB, "005930.KS")
    assert "Invalid Crumb" in str(excinfo.value)


def test_non_json_payload_raises_parse_error():
    with pytest.raises(YahooParseError):
        parse_profile("not json", "MU")


def test_payload_without_the_summary_shape_raises_parse_error():
    with pytest.raises(YahooParseError):
        parse_profile('{"unexpected": "shape"}', "MU")
