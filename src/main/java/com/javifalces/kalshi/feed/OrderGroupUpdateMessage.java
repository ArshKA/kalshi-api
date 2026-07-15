package com.javifalces.kalshi.feed;

public record OrderGroupUpdateMessage(String orderGroupId, String status) implements FeedMessage {}
