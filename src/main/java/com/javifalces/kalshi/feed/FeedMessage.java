package com.javifalces.kalshi.feed;

public sealed interface FeedMessage permits TickerMessage, OrderbookSnapshotMessage, OrderbookDeltaMessage, TradeMessage, FillMessage, PositionMessage, MarketLifecycleMessage, OrderGroupUpdateMessage {}
