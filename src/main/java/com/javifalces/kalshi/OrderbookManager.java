package com.javifalces.kalshi;

import java.math.BigDecimal;
import java.util.Comparator;
import java.util.HashMap;
import java.util.Map;

public final class OrderbookManager {
    private final String ticker;
    private final Map<String, String> yes = new HashMap<>();
    private final Map<String, String> no = new HashMap<>();

    public OrderbookManager(String ticker) {
        this.ticker = ticker;
    }

    public void applySnapshot(java.util.List<java.util.List<String>> yesLevels, java.util.List<java.util.List<String>> noLevels) {
        yes.clear();
        no.clear();
        if (yesLevels != null) yesLevels.forEach(level -> yes.put(level.get(0), level.get(1)));
        if (noLevels != null) noLevels.forEach(level -> no.put(level.get(0), level.get(1)));
    }

    public void applyDelta(String side, String priceDollars, String deltaFp) {
        Map<String, String> book = "yes".equals(side) ? yes : no;
        BigDecimal next = new BigDecimal(book.getOrDefault(priceDollars, "0")).add(new BigDecimal(deltaFp));
        if (next.compareTo(BigDecimal.ZERO) <= 0) {
            book.remove(priceDollars);
        } else {
            book.put(priceDollars, next.stripTrailingZeros().toPlainString());
        }
    }

    public String bestBid() {
        return yes.keySet().stream().map(BigDecimal::new).max(Comparator.naturalOrder()).map(BigDecimal::stripTrailingZeros).map(BigDecimal::toPlainString).orElse(null);
    }

    public String bestAsk() {
        return no.keySet().stream().map(BigDecimal::new).max(Comparator.naturalOrder()).map(price -> BigDecimal.ONE.subtract(price)).map(BigDecimal::stripTrailingZeros).map(BigDecimal::toPlainString).orElse(null);
    }

    public String spread() {
        if (bestBid() == null || bestAsk() == null) return null;
        return new BigDecimal(bestAsk()).subtract(new BigDecimal(bestBid())).stripTrailingZeros().toPlainString();
    }

    public String mid() {
        if (bestBid() == null || bestAsk() == null) return null;
        return new BigDecimal(bestAsk()).add(new BigDecimal(bestBid())).divide(new BigDecimal("2")).stripTrailingZeros().toPlainString();
    }

    public String ticker() { return ticker; }
}
