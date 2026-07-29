# Changelog

## Unreleased

### Breaking changes

- **Removed `place_order(buy_max_cost_dollars=...)`.** The V2 create-order
  request (`CreateOrderV2Request`) has no such field, so the advertised
  slippage protection was a **silent no-op**: the server ignored the field
  and the order went out uncapped. Passing it now raises `TypeError`. To cap
  cost, use a limit price (`price_dollars`) — total cost is then bounded by
  `price × count`.
- **Batch order items now reject unknown keys.** `batch_place_orders` used
  to forward any leftover item keys to the API verbatim, where unknown
  fields are silently ignored — the same failure mode as above, plus typos
  (e.g. `expiry_ts`) going undetected. Unknown keys now raise `ValueError`
  naming the offending key(s).
- **`communications.get_quotes` realigned to the live API.** It previously
  sent `creator_user_id` (a parameter name the API never documented — the
  deprecated spelling is `quote_creator_user_id`) and `market_ticker`
  (filter removed by Kalshi on 2026-06-20), so those filters could return
  unfiltered results. Policy for old kwargs: names with a still-supported
  server-side mapping become `DeprecationWarning` aliases; names whose
  filter no longer exists raise `TypeError` rather than silently returning
  unfiltered data.
  - Added first-class filters from the spec: `user_filter="self"`,
    `rfq_user_filter="self"`, `min_ts`, `max_ts`, `rfq_creator_subtrader_id`
    (plus existing `rfq_id`, `status`, `cursor`).
  - `creator_user_id=` is kept as a deprecated alias mapping to
    `quote_creator_user_id`; `quote_creator_user_id` / `rfq_creator_user_id`
    are deprecated by the API itself and now emit `DeprecationWarning`.
  - `market_ticker=` / `event_ticker=` raise `TypeError`; filter the
    returned quotes by their `market_ticker` field instead.
  - Default `limit` corrected from 100 to 500 (the API default and max).
- **`communications.get_rfqs` filter surface aligned to the spec.** Added
  `event_ticker`, `user_filter="self"`, `subaccount`, and the API-deprecated
  `creator_user_id` (emits `DeprecationWarning`). The undocumented
  `mve_collection_ticker` kwarg now raises `TypeError`; filter the returned
  RFQs by their `mve_collection_ticker` field instead. Both methods accept
  `**extra_params` for forward compatibility.
### Fixed

- **Integration tests no longer race each other on the shared demo account.**
  The suite mutates real orders on one demo account with no per-run
  namespace, and the workflow had nothing serialising concurrent runs. When
  several commits land close together the suites overlap and interfere — a
  `trigger_order_group` in one run cancels resting orders another run just
  placed, so its next cancel 404s and its order-group membership never
  reaches the asserted size. On 2026-07-29 five merges landed in 3.5 minutes
  and 3 of the 5 overlapping runs failed, in three different tests, while
  both isolated runs passed; re-running the same SHA alone passed. The
  integration job now queues on run id (strictly FIFO — unlike a
  `concurrency:` group, which cancels superseded pending runs and would drop
  per-commit signal during a merge train). Teardown cancels also became
  best-effort against `ResourceNotFoundError`, since an order already gone is
  not a regression in a test whose assertions have all passed; the tests that
  exercise cancellation as their subject stay strict.

- **`APILimits` realigned to the live `/account/limits` response.** Kalshi
  restructured the endpoint (Apr 30, 2026) to nested per-bucket objects and
  added automated usage-tier `grants` (Jun 5, 2026); the old flat
  `read_limit` / `write_limit` fields no longer existed on the wire, so
  `get_limits()` returned an empty shell with every field `None`. The model
  now carries `usage_tier`, `read` / `write` (new `RateBucket` with
  `refill_rate` tokens/second and `bucket_capacity` burst headroom), and
  `grants` (new `Grant` with `exchange_instance`, `level`, `source`, and
  optional `expires_ts` — absent means permanent). `read_limit` /
  `write_limit` remain as deprecated properties returning the corresponding
  `refill_rate` and emitting a `DeprecationWarning`.
### Added

- **`MarketModel.price_ranges`** (new exported `PriceRange` model:
  `{start, end, step}` fixed-point dollar strings, plus `*_decimal`
  accessors) — Kalshi's canonical tick definition for a market. The field is
  required on the `Market` schema and was previously dropped by
  `extra="ignore"`.
- **Tick validation now consumes `price_ranges`.** When a `Market` object
  passed to `place_order` carries `price_ranges`, the order price is
  validated against them: it must fall inside a band
  (`start <= price <= end`, inclusive) and sit on that band's grid
  (`(price - start) % step == 0`), all in `Decimal` arithmetic — never
  float. This covers the seven new `price_level_structure` values rolling
  out from the week of 2026-07-27 (`center_{whole|half|quint}_edge_{half|
  quint|deci}_cent`), where the old label-based switch silently validated
  nothing. When ranges are absent, the legacy label logic (`linear_cent`,
  `deci_cent`, `tapered_deci_cent`) applies unchanged; unknown labels
  without ranges remain unvalidated, as before.

### Changed

- **`MarketLifecycleMessage.price_ranges` now parses into `PriceRange`
  models** instead of raw `dict`s, so the WebSocket and REST views of a
  market's tick grid are the same type. Handlers that subscripted the dicts
  (`band["step"]`) must use attribute access (`band.step`).
### Added

- `get_orderbooks(tickers)` on `KalshiClient` / `AsyncKalshiClient` wraps the
  batch `GET /markets/orderbooks` endpoint and returns
  `dict[str, OrderbookResponse]` keyed by ticker. Tickers are uppercased,
  de-duplicated, and sent as repeated `tickers=` query parameters (the
  comma-joined form is silently misread by the API, so tickers containing
  commas raise `ValueError`). Lists longer than the API's 100-ticker limit
  are chunked into sequential requests and merged, so any number of tickers
  may be passed.
### Added

- **`GET /portfolio/balance` matches the current API.** `BalanceModel` now
  carries `balance_dollars` (fixed-point dollar string, up to 6 decimal
  places — sub-cent precision the cents field cannot represent) and
  `balance_breakdown` (per-exchange-index dollar balances, new
  `IndexedBalanceModel`). `get_balance()` accepts `subaccount` (0 for
  primary, 1–63 for subaccounts) and `exchange_index` keyword-only query
  parameters. The docstring previously claimed dollar strings for what are
  cents integers; it now describes the actual fields.
### Added

- **`history.get_positions()`** — wraps the new `GET /historical/positions`
  endpoint (Kalshi changelog 2026-07-23) for settled market positions that
  have been archived to the historical database. Supports `ticker`,
  `event_ticker`, `limit`, `cursor`, and `fetch_all`, returning the same
  `PositionModel` objects as `portfolio.get_positions()`. Available on both
  sync and async clients.
- **`HistoricalCutoffResponse.market_positions_last_updated_ts`** (optional) —
  the new cutoff timestamp: positions archived before it are served by
  `GET /historical/positions` instead of `GET /portfolio/positions`.

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
