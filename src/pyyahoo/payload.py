"""Payload helpers shared by the endpoint parsers.

The parsers all read Yahoo JSON, and three things recur across them: turning the
text into a tree, unwrapping the ``{envelope: {result, error}}`` shape most
endpoints answer with, and reading a ``{"raw": .., "fmt": ..}`` number box. Kept
here so each parser is the shape of *its* endpoint, not a re-implementation of the
same three steps.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from typing import Any, TypeGuard

from .errors import YahooParseError, YahooRequestError, _format_error


def load_json(payload: str, what: str) -> Any:
    """Parse ``payload`` into a JSON tree, or raise a parse error naming ``what``."""
    try:
        return json.loads(payload)
    except (ValueError, TypeError) as err:
        raise YahooParseError(f"{what} payload is not JSON: {err}") from err


def unwrap_result(payload: str, envelope: str, what: str, label: str) -> Any:
    """Unwrap the recurring ``{envelope: {result, error}}`` shape.

    Most endpoints (quote, options, recommendations, insights, screener) wrap their
    answer in one named envelope with a sibling ``error`` node. Returns the
    ``result`` as-is -- a list for most, a bare object for insights -- for the
    caller to walk.

    Raises:
        YahooRequestError: the payload carries an ``error`` -- an unknown symbol,
            or a crumb the caller must re-mint -- carrying Yahoo's own words.
        YahooParseError: the payload is not JSON, or not the ``{envelope: {result,
            error}}`` shape, or a result that is empty without being an error.
    """
    root = load_json(payload, what)
    try:
        node = root[envelope]
        error, result = node["error"], node["result"]
    except (KeyError, TypeError) as err:
        raise YahooParseError(f"{what} payload has no {envelope}/result: {err}") from err
    if error is not None:
        raise YahooRequestError(f"Yahoo served no {what} for {label}: {_format_error(error)}")
    if not result:
        raise YahooParseError(f"{what} result for {label} is empty but not an error")
    return result


def _is_number(value: object) -> TypeGuard[int | float]:
    """A real numeric reading -- int or float, but not bool.

    ``bool`` is a subclass of ``int``, so a JSON ``true`` would otherwise pass as
    ``1`` and reach a price/timestamp field as a fake reading; exclude it.
    """
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def unwrap_raw(node: object) -> float | None:
    """The number inside a ``{"raw": ..}`` box, or None.

    A present field is a box; an absent one is None (Yahoo omits it) or an empty
    box ``{}`` (present but unset). Both become None -- there is no reading. A bare
    number (some endpoints do not box) is taken as is.
    """
    if isinstance(node, dict):
        value = node.get("raw")
        return value if _is_number(value) else None
    return node if _is_number(node) else None


def unwrap_raw_int(node: object) -> int | None:
    """``unwrap_raw`` as an int, for counts (shares, market cap)."""
    value = unwrap_raw(node)
    return int(value) if value is not None else None


def epoch_to_datetime(value: object) -> datetime | None:
    """A Yahoo epoch-seconds timestamp as a UTC datetime, or None if absent."""
    return datetime.fromtimestamp(value, tz=UTC) if _is_number(value) else None


def epoch_to_date(value: object) -> date | None:
    """A Yahoo epoch-seconds timestamp as a UTC date, or None if absent."""
    moment = epoch_to_datetime(value)
    return moment.date() if moment is not None else None


def iso_to_date(value: object) -> date | None:
    """An ISO ``YYYY-MM-DD`` string (Yahoo's ``asOfDate``) as a date, or None."""
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None
