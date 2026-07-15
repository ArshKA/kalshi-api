package com.javifalces.kalshi.feed;

public record MarketLifecycleMessage(String marketTicker, String status) implements FeedMessage {}
