"""Yahoo Finance domain exceptions.

Named subclasses rather than an error-code slug: Yahoo answers a bad request with
an HTTP status and a JSON error that carries only a loose ``code`` string ("Not
Found"), not a stable vocabulary a caller could switch on -- so every failure class
here is one this package names itself, not one Yahoo defines.
"""

from __future__ import annotations


class YahooError(RuntimeError):
    """A Yahoo Finance fetch or parse failure."""


class YahooBlockedError(YahooError):
    """Yahoo is refusing this client (HTTP 429).

    Raised instead of retrying: a block is an answer to respect, so the caller
    backs off or stops rather than knocking again. The usual cause is a client
    whose TLS fingerprint Yahoo does not recognize as a browser -- this package
    reaches Yahoo through ``curl_cffi``'s Chrome impersonation for exactly that
    reason, so a block here is a real rate limit, not a missing disguise.
    """


class YahooRequestError(YahooError):
    """A request to Yahoo failed, returned a non-OK status, or named no data.

    Also raised for a symbol Yahoo does not serve -- a delisted or unknown ticker
    comes back as ``{"chart": {"result": null, "error": {"code": "Not Found"}}}``,
    which is a request that found nothing, not a payload this reader failed to
    understand.
    """


class YahooParseError(YahooError):
    """Yahoo's payload did not have the shape this reader expects.

    Raised where the response's structure -- not its content -- is unrecognized,
    so an API change surfaces as a failure rather than as silently empty data.
    """


def _format_error(error: object) -> str:
    """Yahoo's ``error`` node as a message: code and description together, since
    the code names the class ("Not Found") and the description says what to do
    about it ("symbol may be delisted", "Invalid Crumb"). Shared by the parsers,
    which raise on the same error shape from different endpoints."""
    if not isinstance(error, dict):
        return str(error)
    code, description = error.get("code"), error.get("description")
    return f"{code}: {description}" if description else str(code)
