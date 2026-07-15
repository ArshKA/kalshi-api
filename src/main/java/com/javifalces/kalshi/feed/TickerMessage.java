package com.javifalces.kalshi.feed;

public record TickerMessage(String marketTicker, String yesBidDollars, String yesAskDollars, String volumeFp) implements FeedMessage {}
