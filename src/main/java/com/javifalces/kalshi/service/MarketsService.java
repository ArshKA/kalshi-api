package com.javifalces.kalshi.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonNode;
import com.javifalces.kalshi.CandlestickPeriod;
import com.javifalces.kalshi.Event;
import com.javifalces.kalshi.KalshiClient;
import com.javifalces.kalshi.Market;
import com.javifalces.kalshi.MarketStatus;
import com.javifalces.kalshi.model.CandlestickResponse;
import com.javifalces.kalshi.model.EventData;
import com.javifalces.kalshi.model.MarketData;
import com.javifalces.kalshi.model.Orderbook;
import com.javifalces.kalshi.model.OrderbookLevel;
import com.javifalces.kalshi.model.Trade;
import com.javifalces.kalshi.util.JsonSupport;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class MarketsService extends AbstractService {
    public MarketsService(KalshiClient client) { super(client); }

    public Market getMarket(String ticker) {
        JsonNode root = get("/markets/" + ticker);
        return new Market(client, JsonSupport.MAPPER.convertValue(root.path("market"), MarketData.class));
    }

    public List<Market> getMarkets(String seriesTicker, String eventTicker, MarketStatus status, Integer limit, boolean fetchAll) {
        List<Market> markets = new ArrayList<>();
        String cursor = null;
        do {
            Map<String, Object> query = new LinkedHashMap<>();
            query.put("series_ticker", seriesTicker);
            query.put("event_ticker", eventTicker);
            query.put("status", status == null ? null : status.value());
            query.put("limit", limit == null ? 100 : limit);
            query.put("cursor", cursor);
            JsonNode root = client.request("GET", "/markets", query, null);
            for (JsonNode node : root.path("markets")) {
                markets.add(new Market(client, JsonSupport.MAPPER.convertValue(node, MarketData.class)));
            }
            cursor = root.path("cursor").asText("");
        } while (fetchAll && cursor != null && !cursor.isBlank());
        return markets;
    }

    public Event getEvent(String eventTicker) {
        JsonNode root = get("/events/" + eventTicker);
        return new Event(client, JsonSupport.MAPPER.convertValue(root.path("event"), EventData.class));
    }

    public List<Event> getEvents(String seriesTicker, Integer limit, boolean fetchAll) {
        List<Event> events = new ArrayList<>();
        String cursor = null;
        do {
            Map<String, Object> query = new LinkedHashMap<>();
            query.put("series_ticker", seriesTicker);
            query.put("limit", limit == null ? 100 : limit);
            query.put("cursor", cursor);
            JsonNode root = client.request("GET", "/events", query, null);
            for (JsonNode node : root.path("events")) {
                events.add(new Event(client, JsonSupport.MAPPER.convertValue(node, EventData.class)));
            }
            cursor = root.path("cursor").asText("");
        } while (fetchAll && cursor != null && !cursor.isBlank());
        return events;
    }

    public CandlestickResponse getCandlesticks(String ticker, String seriesTicker, long startTs, long endTs, CandlestickPeriod period) {
        Map<String, Object> query = new LinkedHashMap<>();
        query.put("start_ts", startTs);
        query.put("end_ts", endTs);
        query.put("period_interval", period == null ? null : period.value());
        JsonNode root = client.request("GET", "/series/" + seriesTicker + "/markets/" + ticker + "/candlesticks", query, null);
        return JsonSupport.MAPPER.convertValue(root, CandlestickResponse.class);
    }

    public List<Trade> getTrades(String ticker, Integer limit) {
        Map<String, Object> query = new LinkedHashMap<>();
        query.put("limit", limit == null ? 100 : limit);
        JsonNode root = client.request("GET", "/markets/" + ticker + "/trades", query, null);
        return JsonSupport.MAPPER.convertValue(root.path("trades"), new TypeReference<List<Trade>>() {});
    }

    public Orderbook getOrderbook(String ticker) {
        JsonNode node = client.request("GET", "/markets/" + ticker + "/orderbook", null, null);
        JsonNode orderbookNode = node.has("orderbook") ? node.path("orderbook") : node.path("orderbook_fp");
        return new Orderbook(levels(orderbookNode.path("yes_dollars")), levels(orderbookNode.path("no_dollars")));
    }

    private List<OrderbookLevel> levels(JsonNode node) {
        List<OrderbookLevel> result = new ArrayList<>();
        for (JsonNode level : node) {
            result.add(new OrderbookLevel(level.get(0).asText(), level.get(1).asText()));
        }
        return result;
    }
}
