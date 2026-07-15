package com.javifalces.kalshi.feed;

public record TradeMessage(String marketTicker, String tradeId, String countFp, String yesPriceDollars, String takerSide, Long ts) implements FeedMessage {}
