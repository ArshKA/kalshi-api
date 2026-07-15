package com.javifalces.kalshi.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonNode;
import com.javifalces.kalshi.Action;
import com.javifalces.kalshi.KalshiClient;
import com.javifalces.kalshi.Order;
import com.javifalces.kalshi.PositionCountFilter;
import com.javifalces.kalshi.Side;
import com.javifalces.kalshi.model.Balance;
import com.javifalces.kalshi.model.Fill;
import com.javifalces.kalshi.model.OrderData;
import com.javifalces.kalshi.model.Position;
import com.javifalces.kalshi.util.JsonSupport;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class PortfolioService extends AbstractService {
    public PortfolioService(KalshiClient client) { super(client); }

    public Balance getBalance() {
        JsonNode root = get("/portfolio/balance");
        return JsonSupport.MAPPER.convertValue(root, Balance.class);
    }

    public List<Position> getPositions(String ticker, String eventTicker, PositionCountFilter countFilter, Integer limit) {
        Map<String, Object> query = new LinkedHashMap<>();
        query.put("ticker", ticker);
        query.put("event_ticker", eventTicker);
        query.put("count_filter", countFilter == null ? null : countFilter.value());
        query.put("limit", limit == null ? 100 : limit);
        JsonNode root = client.request("GET", "/portfolio/positions", query, null);
        return JsonSupport.MAPPER.convertValue(root.path("market_positions"), new TypeReference<List<Position>>() {});
    }

    public List<Fill> getFills(String ticker, String orderId, Long minTs, Long maxTs, Integer limit) {
        Map<String, Object> query = new LinkedHashMap<>();
        query.put("ticker", ticker);
        query.put("order_id", orderId);
        query.put("min_ts", minTs);
        query.put("max_ts", maxTs);
        query.put("limit", limit == null ? 100 : limit);
        JsonNode root = client.request("GET", "/portfolio/fills", query, null);
        return JsonSupport.MAPPER.convertValue(root.path("fills"), new TypeReference<List<Fill>>() {});
    }

    public Order getOrder(String orderId) {
        JsonNode root = get("/portfolio/orders/" + orderId);
        return new Order(client, JsonSupport.MAPPER.convertValue(root.path("order"), OrderData.class));
    }

    public Order cancelOrder(String orderId) {
        JsonNode root = delete("/portfolio/orders/" + orderId);
        return new Order(client, JsonSupport.MAPPER.convertValue(root.path("order"), OrderData.class));
    }

    public Order placeOrder(String ticker, Action action, Side side, String countFp, String yesPriceDollars) {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("ticker", ticker);
        body.put("action", action == null ? null : action.value());
        body.put("side", side == null ? null : side.value());
        body.put("count_fp", countFp);
        body.put("yes_price_dollars", yesPriceDollars);
        JsonNode root = post("/portfolio/orders", body);
        return new Order(client, JsonSupport.MAPPER.convertValue(root.path("order"), OrderData.class));
    }
}
