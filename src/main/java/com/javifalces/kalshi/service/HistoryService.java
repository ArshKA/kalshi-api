package com.javifalces.kalshi.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonNode;
import com.javifalces.kalshi.CandlestickPeriod;
import com.javifalces.kalshi.KalshiClient;
import com.javifalces.kalshi.Market;
import com.javifalces.kalshi.model.CandlestickResponse;
import com.javifalces.kalshi.model.Fill;
import com.javifalces.kalshi.model.HistoricalCutoff;
import com.javifalces.kalshi.model.MarketData;
import com.javifalces.kalshi.model.OrderData;
import com.javifalces.kalshi.model.Trade;
import com.javifalces.kalshi.util.JsonSupport;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class HistoryService extends AbstractService {
    public HistoryService(KalshiClient client) { super(client); }

    public HistoricalCutoff getCutoff() {
        return JsonSupport.MAPPER.convertValue(get("/history/cutoff"), HistoricalCutoff.class);
    }

    public List<Market> getMarkets(String eventTicker, Integer limit, boolean fetchAll) {
        List<Market> markets = new ArrayList<>();
        String cursor = null;
        do {
            Map<String, Object> query = new LinkedHashMap<>();
            query.put("event_ticker", eventTicker);
            query.put("limit", limit == null ? 100 : limit);
            query.put("cursor", cursor);
            JsonNode root = client.request("GET", "/history/markets", query, null);
            for (JsonNode node : root.path("markets")) {
                markets.add(new Market(client, JsonSupport.MAPPER.convertValue(node, MarketData.class)));
            }
            cursor = root.path("cursor").asText("");
        } while (fetchAll && cursor != null && !cursor.isBlank());
        return markets;
    }

    public Market getMarket(String ticker) {
        JsonNode root = get("/history/markets/" + ticker);
        return new Market(client, JsonSupport.MAPPER.convertValue(root.path("market"), MarketData.class));
    }

    public CandlestickResponse getCandlesticks(String ticker, long startTs, long endTs, CandlestickPeriod period) {
        Map<String, Object> query = new LinkedHashMap<>();
        query.put("start_ts", startTs);
        query.put("end_ts", endTs);
        query.put("period_interval", period == null ? null : period.value());
        JsonNode root = client.request("GET", "/history/markets/" + ticker + "/candlesticks", query, null);
        return JsonSupport.MAPPER.convertValue(root, CandlestickResponse.class);
    }

    public List<Fill> getFills(Integer limit) {
        JsonNode root = client.request("GET", "/history/fills", Map.of("limit", limit == null ? 100 : limit), null);
        return JsonSupport.MAPPER.convertValue(root.path("fills"), new TypeReference<List<Fill>>() {});
    }

    public List<OrderData> getOrders(Integer limit) {
        JsonNode root = client.request("GET", "/history/orders", Map.of("limit", limit == null ? 100 : limit), null);
        return JsonSupport.MAPPER.convertValue(root.path("orders"), new TypeReference<List<OrderData>>() {});
    }

    public List<Trade> getTrades(Integer limit) {
        JsonNode root = client.request("GET", "/history/trades", Map.of("limit", limit == null ? 100 : limit), null);
        return JsonSupport.MAPPER.convertValue(root.path("trades"), new TypeReference<List<Trade>>() {});
    }
}
