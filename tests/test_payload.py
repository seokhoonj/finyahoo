"""Direct tests for the shared payload helpers.

The parsers exercise these transitively, but the leaf coercions have edges worth
pinning directly: a raw box that is empty or a bool, a malformed ISO date, an
absent epoch. A regression here would surface as many parsers going subtly wrong
at once.
"""

from datetime import UTC, date, datetime

from pyyahoo.payload import (
    epoch_to_date,
    epoch_to_datetime,
    iso_to_date,
    unwrap_raw,
    unwrap_raw_int,
)


def test_unwrap_raw_reads_the_boxed_number_and_the_bare_number():
    assert unwrap_raw({"raw": 3.5, "fmt": "3.50"}) == 3.5
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
