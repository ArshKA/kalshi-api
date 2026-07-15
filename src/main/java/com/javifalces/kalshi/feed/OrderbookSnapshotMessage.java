package com.javifalces.kalshi.feed;

import java.util.List;

public record OrderbookSnapshotMessage(String marketTicker, List<List<String>> yesDollars, List<List<String>> noDollars) implements FeedMessage {}
