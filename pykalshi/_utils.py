"""Internal utilities."""

from __future__ import annotations


# --- Direction -------------------------------------------------------------
#
# Kalshi expresses direction canonically as `book_side` (bid|ask) and
# `outcome_side` (yes|no), with bid == yes and ask == no. The legacy
# `action`/`side` pair is deprecated. See
# https://docs.kalshi.com/getting_started/order_direction
#
# The legacy pair does NOT mean the same thing on every surface, which is the
# trap these helpers exist to keep out of the models:
#
#   Orders  -- direction comes from the (action, side) PAIR, per the published
#              table. A sell/yes order is long no  -> ask.
#   Fills   -- `side` alone is the outcome acquired; `action` carries no sign.
#              A sell/yes fill is long yes -> bid. This is the OPPOSITE of the
#              order rule, and it contradicts the published table, which
#              documents only the order convention. Verified against 1,685
#              live fills: side == outcome_side in every one.
#   Trades  -- `taker_side` maps 1:1 onto `taker_outcome_side`.
#
# Applying the order rule to a fill silently inverts every `sell` row.
#
# This is not a quirk of one account. Kalshi's own changelog says so, in the
# 2025-09-22 entry that introduced `purchased_side`: it describes "the fills
# WebSocket and REST endpoints, which have different conventions for the
# interpretation 'side' and 'user_action'". `outcome_side` is consistent
# across surfaces precisely because the legacy `side` is not -- on a fill it
# already denotes the outcome, so outcome_side == side there, while on an
# order it denotes the leg being transacted and must be combined with
# `action`. The published equivalence table describes the ORDER reading.
#
# The decisive evidence, if this is ever questioned: join a fill to the order
# that produced it. An order's direction is unambiguous. Across every sell fill
# in the account, fill.book_side == parent_order.book_side (9/9):
#
#   fill sell/no  (book_side=ask) <- order sell/yes (book_side=ask, long no)
#   fill sell/yes (book_side=bid) <- order sell/no  (book_side=bid, long yes)
#
# Note the legacy pair is INVERTED between the two surfaces for the same
# resting order, while book_side is identical. So a fill reporting `sell/yes`
# came from a long-YES order and increased the yes position -- the opposite of
# what the order table would say if applied to the fill's own fields. That is
# the trap: it is not that book_side is ambiguous, it is that `side` means
# something different on each surface.
#
# Deprecation status (checked 2026-07-25): the changelog entry "Normalized
# outcome_side and book_side on Order, Fill, and Trade responses" marks
# `action`, `side`, `is_yes`, `purchased_side` and `taker_side` deprecated,
# with removal "not before May 28, 2026" -- a floor that has now passed. The
# legacy paths below are therefore transitional only; nothing in this library
# should require them.

_ORDER_LEGACY_TO_BOOK_SIDE = {
    ("buy", "yes"): "bid",
    ("sell", "no"): "bid",
    ("buy", "no"): "ask",
    ("sell", "yes"): "ask",
}


def book_side_from_order_legacy(action, side) -> str | None:
    """Map an ORDER's legacy (action, side) onto ``bid``/``ask``.

    Never apply this to a fill -- see the module comment. Returns None when
    either input is missing, rather than guessing.
    """
    a = getattr(action, "value", action)
    s = getattr(side, "value", side)
    if not a or not s:
        return None
    return _ORDER_LEGACY_TO_BOOK_SIDE.get((a, s))


def book_side_from_fill_legacy(side) -> str | None:
    """Map a FILL's legacy ``side`` onto ``bid``/``ask``.

    On fills ``side`` is the outcome acquired, so it maps straight through:
    yes -> bid, no -> ask. ``action`` is deliberately ignored; including it
    would invert the sell rows.
    """
    s = getattr(side, "value", side)
    if not s:
        return None
    return {"yes": "bid", "no": "ask"}.get(s)


def outcome_side_from_book_side(book_side) -> str | None:
    """``bid`` -> ``yes``, ``ask`` -> ``no``."""
    b = getattr(book_side, "value", book_side)
    if not b:
        return None
    return {"bid": "yes", "ask": "no"}.get(b)


def book_side_from_outcome_side(outcome_side) -> str | None:
    """``yes`` -> ``bid``, ``no`` -> ``ask``."""
    o = getattr(outcome_side, "value", outcome_side)
    if not o:
        return None
    return {"yes": "bid", "no": "ask"}.get(o)


def blank_to_none(v):
    """Coerce the empty string to None.

    Kalshi's Go services serialise absent optional strings as ``""`` rather
    than omitting them (observed live on ``client_order_id``). When the
    deprecated direction fields are retired they will most likely arrive the
    same way, and ``""`` is not a valid enum member -- so every legacy enum
    field runs through this to avoid a ValidationError on every row.
    """
    return None if v == "" else v


def normalize_ticker(ticker: str | None) -> str | None:
    """Uppercase a ticker string, passing through None."""
    return ticker.upper() if ticker else None


def normalize_tickers(tickers: list[str] | None) -> list[str] | None:
    """Uppercase a list of ticker strings, passing through None."""
    return [t.upper() for t in tickers] if tickers else None
