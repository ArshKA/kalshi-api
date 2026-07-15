package com.javifalces.kalshi.feed;

public record OrderbookDeltaMessage(String marketTicker, String priceDollars, String deltaFp, String side) implements FeedMessage {}
