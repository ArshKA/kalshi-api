# Changelog

## 2.0.0 — 2026-07-26

Major release: migration to Kalshi's V2 order endpoints and canonical
direction fields. **Upgrading is required for order placement** — Kalshi
removed the v1 write path (`POST /portfolio/orders` now returns `410 Gone`),
so 1.x versions can no longer place, amend, or cancel orders.

### Breaking changes

- **Order writes use the V2 endpoints** (`/portfolio/events/orders`,
  `.../amend`, `.../decrease`, `.../batched`). Read paths are unchanged.
  V2 write acks are thin (id + counts); returned `Order` objects are
  reconstructed from the ack plus request context instead of a full server
  echo.
- **Default hosts moved** to Kalshi's recommended roots:
  `external-api.kalshi.com` / `external-api-ws.kalshi.com` (demo:
  `external-api.demo.kalshi.co` / `external-api-ws.demo.kalshi.co`).
  The legacy hosts remain supported when passed explicitly.
- **Removed `Announcement` and `exchange.get_announcements()`** — Kalshi
  removed the endpoint (404).
- **Subaccount API rewritten to match the live API.**
  `SubaccountModel`, `SubaccountBalanceModel`, and `SubaccountTransferModel`
  now use integer `subaccount_number` (0 = primary, 1–63) instead of the
  string ids that never matched the wire. `transfer_between_subaccounts` is
  now `(from_subaccount: int, to_subaccount: int, amount_cents: int, *,
  client_transfer_id=None, exchange_index=None) -> str` and returns the
  idempotency key (the API's success body is empty).
- **`SettlementModel` costs are now fixed-point dollar strings**
  (`yes_total_cost_dollars` / `no_total_cost_dollars`). The old cents-int
  fields never matched the wire and silently zeroed cost out of every pnl.
  New `pnl_dollars` / `total_cost_dollars` properties; `pnl` (cents) retained.
- **`FillModel.action` / `.side` are now optional** (Kalshi deprecated them);
  previously required, which would break `get_fills()` the day Kalshi stops
  sending them. `no_price_dollars` is also optional.
- **WebSocket models realigned to the actual wire format.** Fields that never
  matched (and so were always `None`, or failed validation entirely) now use
  the wire names: `FillMessage.market_ticker` (`.ticker` kept as a property),
  `PositionMessage.market_ticker` (frames previously failed validation and
  degraded to raw dicts), `OrderbookSnapshotMessage.yes_dollars_fp` /
  `no_dollars_fp` (old names kept as properties),
  `MarketLifecycleMessage.event_type` (was `status`),
  `OrderGroupUpdateMessage.event_type`, `TickerMessage.dollar_volume` /
  `dollar_open_interest` (wire sends ints). The `order_group_updates` frame
  type (plural) is now recognized.
- `place_order` now always sends `time_in_force` (default GTC) and
  `self_trade_prevention_type` (default cancel-resting) — required by the V2
  request.

### Added

- **Canonical direction vocabulary**, matching Kalshi's current API:
  `BookSide` / `OutcomeSide` enums; `book_side` / `outcome_side` on Order,
  Fill, and Trade models and WebSocket messages (back-filled from legacy
  fields when absent, using the correct per-surface mapping — note the fill
  convention differs from the order convention); `is_bid` / `is_ask` /
  `yes_delta_fp` helpers.
- **Canonical order entry**: `place_order(ticker, book_side="bid"|"ask",
  price_dollars=..., count_fp=...)` — YES-denominated, no 1−p mental math.
  Same form on `amend` and batch items. The legacy `action`/`side` form
  still works and maps onto the same wire body.
- **`UserOrderMessage`** (`user_orders` channel) and **`ErrorMessage`**
  WebSocket models; error frames are now logged instead of swallowed.
- **Subaccount netting**: `get_subaccount_netting()`,
  `update_subaccount_netting()`, `SubaccountNettingModel`.
- `MarketLifecycleMessage` now models the `metadata_updated` payload
  (strikes, custom strike, subtitle, additional metadata).

### Fixed

- **Unfilled IOC/FOK orders are no longer reported as `executed`.** A V2 ack
  with zero fills and zero remaining is classified `canceled` (verified
  against the live exchange); previously it read as a complete fill.
- **Batch items given both `count_fp` and `count` now raise** instead of
  silently sending whichever key survived dict merging.
- `amend` preserves the filled portion of a partially filled order — `count`
  is the API's *total* (filled + remaining), so amending no longer cancels
  what has already filled.
- `Order.amend()` / `cancel()` / `decrease()` no longer blank known fields
  (ticker, price, direction) when overlaying the thin V2 ack.

### Deprecated

- `Order.action` / `Order.side`, `Fill.action` / `Fill.side`,
  `Trade.taker_side` — deprecated by Kalshi (removal floor of
  2026-05-28 has passed). Read `book_side` / `outcome_side` instead.

---

Versions 1.0.6 and earlier predate this changelog; see the git history.
