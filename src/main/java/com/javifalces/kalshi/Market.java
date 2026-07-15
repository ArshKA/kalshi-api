package com.javifalces.kalshi;

import com.javifalces.kalshi.model.CandlestickResponse;
import com.javifalces.kalshi.model.MarketData;
import com.javifalces.kalshi.model.Orderbook;
import com.javifalces.kalshi.model.Trade;
import java.util.List;
import java.util.Objects;

public final class Market {
    private final KalshiClient client;
    private MarketData data;

    public Market(KalshiClient client, MarketData data) {
        this.client = client;
        this.data = data;
    }

    public String ticker() { return data.ticker(); }
    public String eventTicker() { return data.eventTicker(); }
    public String seriesTicker() { return data.seriesTicker(); }
    public String title() { return data.title(); }
    public MarketStatus status() { return data.status(); }
    public String yesBidDollars() { return data.yesBidDollars(); }
    public String yesAskDollars() { return data.yesAskDollars(); }
    public String volumeFp() { return data.volumeFp(); }

    public String resolveSeriesTicker() {
        if (data.seriesTicker() != null && !data.seriesTicker().isBlank()) {
            return data.seriesTicker();
        }
        if (data.eventTicker() == null || data.eventTicker().isBlank()) {
            throw new IllegalArgumentException("series_ticker is required for candlesticks");
        }
        Event event = client.getEvent(data.eventTicker());
        return event.seriesTicker();
    }

    public CandlestickResponse getCandlesticks(long startTs, long endTs, CandlestickPeriod period) {
        return client.markets().getCandlesticks(ticker(), resolveSeriesTicker(), startTs, endTs, period);
    }

    public CandlestickResponse getCandlesticks(long startTs, long endTs) {
        return getCandlesticks(startTs, endTs, CandlestickPeriod.ONE_HOUR);
    }

    public List<Trade> getTrades(Integer limit) {
        return client.markets().getTrades(ticker(), limit);
    }

    public Orderbook getOrderbook() {
        return client.markets().getOrderbook(ticker());
    }

    public Event getEvent() {
        return client.getEvent(eventTicker());
    }

    @Override
    public boolean equals(Object other) {
        return other instanceof Market market && Objects.equals(ticker(), market.ticker());
    }

    @Override
    public int hashCode() {
        return Objects.hash(ticker());
    }
}
