package com.javifalces.kalshi;

import com.javifalces.kalshi.model.EventData;
import java.util.List;

public final class Event {
    private final KalshiClient client;
    private final EventData data;

    public Event(KalshiClient client, EventData data) {
        this.client = client;
        this.data = data;
    }

    public String eventTicker() { return data.eventTicker(); }
    public String seriesTicker() { return data.seriesTicker(); }
    public String title() { return data.title(); }

    public List<Market> getMarkets(Integer limit) {
        return client.getMarkets(null, eventTicker(), null, limit, false);
    }
}
