package com.javifalces.kalshi.model;

import java.util.List;

public record Orderbook(List<OrderbookLevel> yesDollars, List<OrderbookLevel> noDollars) {}
