"""Direct tests for the shared payload helpers.

The parsers exercise these transitively, but the leaf coercions have edges worth
pinning directly: a raw box that is empty or a bool, a malformed ISO date, an
absent epoch. A regression here would surface as many parsers going subtly wrong
at once.
"""

from datetime import UTC, date, datetime

import pytest

from finyahoo import YahooParseError
from finyahoo.payload import (
    as_number,
    each_dict,
    epoch_to_date,
    epoch_to_datetime,
    first_dict,
    iso_to_date,
    unwrap_raw,
    unwrap_raw_int,
    unwrap_result,
)


def test_unwrap_raw_reads_the_boxed_number_and_the_bare_number():
    assert unwrap_raw({"raw": 3.5, "fmt": "3.50"}) == pytest.approx(3.5)
    assert unwrap_raw(42) == 42                 # some endpoints do not box


def test_unwrap_raw_is_none_for_an_empty_box_or_absent_value():
    assert unwrap_raw({}) is None
    assert unwrap_raw(None) is None
    assert unwrap_raw({"raw": None}) is None


def test_unwrap_raw_rejects_bool_because_bool_is_an_int_subclass():
    """A JSON true must not read as 1.0 in a price/count field."""
    assert unwrap_raw(True) is None
    assert unwrap_raw({"raw": False}) is None


def test_unwrap_raw_int_truncates_a_float_to_int():
    assert unwrap_raw_int({"raw": 1.23e9}) == 1230000000
    assert isinstance(unwrap_raw_int(1000), int)
    assert unwrap_raw_int(None) is None


def test_epoch_to_datetime_and_date_are_utc_and_none_safe():
    moment = epoch_to_datetime(1700000000)
    assert moment == datetime(2023, 11, 14, 22, 13, 20, tzinfo=UTC)
    assert epoch_to_date(1700000000) == date(2023, 11, 14)
    assert epoch_to_datetime(None) is None
    assert epoch_to_date(None) is None
    assert epoch_to_datetime(True) is None      # bool is not an epoch


def test_iso_to_date_parses_and_returns_none_on_garbage():
    assert iso_to_date("2022-09-30") == date(2022, 9, 30)
    assert iso_to_date("2022-13-40") is None    # out-of-range month/day
    assert iso_to_date("not-a-date") is None
    assert iso_to_date(123) is None


def test_as_number_reads_a_bare_number_and_rejects_non_numbers():
    """The bare-field counterpart to unwrap_raw: a JSON true or a stray box must not
    reach a field typed float | None."""
    assert as_number(339.25) == pytest.approx(339.25)
    assert as_number(0) == 0                     # a real zero, not absence
    assert as_number(None) is None
    assert as_number(True) is None               # bool is not a number
    assert as_number({"raw": 5}) is None         # an unexpected box, not a bare number
    assert as_number("339.25") is None           # a string is not a number


def test_first_dict_returns_the_object_or_raises_on_drift():
    assert first_dict([{"a": 1}], "x") == {"a": 1}
    with pytest.raises(YahooParseError):
        first_dict({"a": 1}, "x")                # a bare object, not a list
    with pytest.raises(YahooParseError):
        first_dict([], "x")                      # an empty list
    with pytest.raises(YahooParseError):
        first_dict([42], "x")                    # first element is not an object


def test_each_dict_returns_the_list_or_raises_on_a_non_object_entry():
    assert each_dict([{"a": 1}, {"b": 2}], "x") == [{"a": 1}, {"b": 2}]
    assert each_dict([], "x") == []              # empty is fine here
    with pytest.raises(YahooParseError):
        each_dict({"a": 1}, "x")                 # not a list
    with pytest.raises(YahooParseError):
        each_dict([{"a": 1}, None], "x")         # a null record is shape drift


def test_unwrap_result_allow_empty_distinguishes_no_matches_from_drift():
    empty = '{"quoteResponse": {"error": null, "result": []}}'
    assert unwrap_result(empty, "quoteResponse", "quote", "syms", allow_empty=True) == []
    with pytest.raises(YahooParseError):
        unwrap_result(empty, "quoteResponse", "quote", "syms")   # empty is drift by default
