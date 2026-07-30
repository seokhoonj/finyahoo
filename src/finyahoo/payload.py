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


def unwrap_result(payload: str, envelope: str, what: str, label: str,
                  *, allow_empty: bool = False) -> object:
    """Unwrap the recurring ``{envelope: {result, error}}`` shape.

    Most endpoints (quote, options, recommendations, insights, screener) wrap their
    answer in one named envelope with a sibling ``error`` node. Returns the
    ``result`` as-is -- a list for most, a bare object for insights -- for the
    caller to walk.

    ``allow_empty`` distinguishes two situations an empty ``result`` can mean. By
    default an empty result is shape drift (a single-item endpoint like chart or
    quoteSummary should always carry its one object). A multi-item endpoint,
    though, answers a request that matched nothing with an empty list and a null
    ``error`` -- a legitimate "no matches", not drift -- so those callers pass
    ``allow_empty=True`` and receive the empty list.

    Raises:
        YahooRequestError: the payload carries an ``error`` -- an unknown symbol,
            or a crumb the caller must re-mint -- carrying Yahoo's own words.
        YahooParseError: the payload is not JSON, or not the ``{envelope: {result,
            error}}`` shape, or (unless ``allow_empty``) a result that is empty
            without being an error.
    """
    root = load_json(payload, what)
    try:
        node = root[envelope]
        error, result = node["error"], node["result"]
    except (KeyError, TypeError) as err:
        raise YahooParseError(f"{what} payload has no {envelope}/result: {err}") from err
    if error is not None:
        raise YahooRequestError(f"Yahoo served no {what} for {label}: {_format_error(error)}")
    if not result and not allow_empty:
        raise YahooParseError(f"{what} result for {label} is empty but not an error")
    return result


def first_dict(result: object, what: str) -> dict[str, Any]:
    """The first element of an unwrapped list result, guaranteed an object.

    ``unwrap_result`` guarantees the result is present, not that it is a list whose
    first element is an object. A drift to a bare value, or a non-object first
    element, is shape drift -- raised here as ``YahooParseError`` rather than let
    escape as a bare ``IndexError``/``AttributeError`` past the documented contract.
    """
    if not isinstance(result, list) or not result:
        raise YahooParseError(f"{what} result is not a non-empty list: {type(result).__name__}")
    first = result[0]
    if not isinstance(first, dict):
        raise YahooParseError(f"{what} result[0] is not an object: {type(first).__name__}")
    return first


def each_dict(items: object, what: str) -> list[dict[str, Any]]:
    """Every element of a result list, each guaranteed an object.

    A non-list, or a non-object element (a JSON ``null`` record), is shape drift
    raised as ``YahooParseError`` rather than left to escape as an ``AttributeError``
    from a later ``.get()``.
    """
    if not isinstance(items, list):
        raise YahooParseError(f"{what} result is not a list: {type(items).__name__}")
    for item in items:
        if not isinstance(item, dict):
            raise YahooParseError(f"{what} result has a non-object entry: {type(item).__name__}")
    return items


def is_number(value: object) -> TypeGuard[int | float]:
    """A real numeric reading -- int or float, but not bool.

    ``bool`` is a subclass of ``int``, so a JSON ``true`` would otherwise pass as
    ``1`` and reach a price/timestamp field as a fake reading; exclude it.
    """
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def as_number(value: object) -> float | None:
    """A bare numeric field as a float, or None when it is absent or not a number.

    The counterpart to ``unwrap_raw`` for endpoints that answer with bare numbers
    rather than ``{"raw": ..}`` boxes (quote, options, search, ...). Routing every
    bare numeric field through this keeps a JSON ``true`` or an unexpected ``{..}``
    box out of a field typed ``float | None``, so the hint stays honest.
    """
    return value if is_number(value) else None


def as_bool(value: object) -> bool | None:
    """A bare boolean field, or None when it is absent or not a real bool.

    The boolean counterpart to ``as_number``: a JSON string or number drifting into a
    field typed ``bool | None`` is rejected rather than silently stored.
    """
    return value if isinstance(value, bool) else None


def as_str(value: object) -> str | None:
    """A bare string field, or None when it is absent or not a real string.

    The string counterpart to ``as_number``: a JSON number, bool, or ``{..}`` box
    drifting into a field typed ``str | None`` is rejected rather than silently
    stored, so the hint stays honest.
    """
    return value if isinstance(value, str) else None


def dict_or_empty(node: object) -> dict[str, Any]:
    """``node`` if it is a dict, else an empty one.

    A missing branch (``None``) *or* one that drifted to a non-dict reads as absent
    fields, so an optional nested node cannot raise ``AttributeError`` from a later
    ``.get()`` past the documented ``YahooParseError`` contract.
    """
    return node if isinstance(node, dict) else {}


def unwrap_raw(node: object) -> float | None:
    """The number inside a ``{"raw": ..}`` box, or None.

    A present field is a box; an absent one is None (Yahoo omits it) or an empty
    box ``{}`` (present but unset). Both become None -- there is no reading. A bare
    number (some endpoints do not box) is taken as is.
    """
    if isinstance(node, dict):
        value = node.get("raw")
        return value if is_number(value) else None
    return node if is_number(node) else None


def unwrap_raw_int(node: object) -> int | None:
    """``unwrap_raw`` as an int, for counts (shares, market cap)."""
    value = unwrap_raw(node)
    return int(value) if value is not None else None


def epoch_to_datetime(value: object) -> datetime | None:
    """A Yahoo epoch-seconds timestamp as a UTC datetime, or None if absent."""
    return datetime.fromtimestamp(value, tz=UTC) if is_number(value) else None


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
