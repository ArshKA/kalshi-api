package com.javifalces.kalshi.feed;

public record FillMessage(String marketTicker, String orderId, String tradeId, String countFp, String side) implements FeedMessage {}
