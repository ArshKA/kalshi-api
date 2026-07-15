package com.javifalces.kalshi.feed;

public record PositionMessage(String marketTicker, String positionFp) implements FeedMessage {}
