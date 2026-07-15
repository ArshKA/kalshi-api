package com.javifalces.kalshi.feed;

import com.fasterxml.jackson.databind.JsonNode;
import com.javifalces.kalshi.KalshiClient;
import com.javifalces.kalshi.util.JsonSupport;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.WebSocket;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletionStage;
import java.util.function.Consumer;

public final class Feed implements WebSocket.Listener {
    public static final String DEFAULT_WS_BASE = "wss://api.elections.kalshi.com/trade-api/ws/v2";
    public static final String DEMO_WS_BASE = "wss://demo-api.kalshi.co/trade-api/ws/v2";

    private final KalshiClient client;
    private final String wsUrl;
    private final Map<String, List<Consumer<FeedMessage>>> handlers = new LinkedHashMap<>();
    private final List<Map<String, Object>> activeSubscriptions = new ArrayList<>();
    private final StringBuilder messageBuffer = new StringBuilder();
    private volatile boolean connected;
    private volatile WebSocket webSocket;

    public Feed(KalshiClient client) {
        this.client = client;
        this.wsUrl = KalshiClient.DEMO_API_BASE.equals(client.apiBase()) ? DEMO_WS_BASE : DEFAULT_WS_BASE;
    }

    public Feed on(String channel, Consumer<FeedMessage> handler) {
        handlers.computeIfAbsent(channel, ignored -> new ArrayList<>()).add(handler);
        return this;
    }

    public void subscribe(String channel, String marketTicker, List<String> marketTickers) {
        Map<String, Object> subscription = new LinkedHashMap<>();
        subscription.put("channels", List.of(channel));
        if (marketTicker != null) subscription.put("market_ticker", marketTicker);
        if (marketTickers != null) subscription.put("market_tickers", marketTickers);
        activeSubscriptions.add(subscription);
        sendIfConnected("subscribe", subscription);
    }

    public void unsubscribe(String channel, String marketTicker) {
        activeSubscriptions.removeIf(entry -> entry.get("channels").equals(List.of(channel))
                && java.util.Objects.equals(entry.get("market_ticker"), marketTicker));
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("channels", List.of(channel));
        if (marketTicker != null) payload.put("market_ticker", marketTicker);
        sendIfConnected("unsubscribe", payload);
    }

    public boolean isConnected() { return connected; }
    public String wsUrl() { return wsUrl; }
    public List<Map<String, Object>> activeSubscriptions() { return activeSubscriptions; }

    public CompletionStage<WebSocket> connect() {
        return HttpClient.newHttpClient().newWebSocketBuilder().buildAsync(URI.create(wsUrl), this)
                .thenApply(ws -> {
                    this.webSocket = ws;
                    this.connected = true;
                    for (Map<String, Object> sub : activeSubscriptions) send("subscribe", sub);
                    return ws;
                });
    }

    public void disconnect() {
        if (webSocket != null) {
            webSocket.sendClose(WebSocket.NORMAL_CLOSURE, "bye");
        }
        connected = false;
    }

    public void dispatch(String rawJson) {
        try {
            JsonNode root = JsonSupport.MAPPER.readTree(rawJson);
            String type = root.path("type").asText();
            JsonNode msg = root.path("msg");
            FeedMessage message = switch (type) {
                case "ticker" -> new TickerMessage(msg.path("market_ticker").asText(), msg.path("yes_bid_dollars").asText(null), msg.path("yes_ask_dollars").asText(null), msg.path("volume_fp").asText(null));
                case "orderbook_snapshot" -> new OrderbookSnapshotMessage(msg.path("market_ticker").asText(), levelMatrix(msg.path("yes_dollars")), levelMatrix(msg.path("no_dollars")));
                case "orderbook_delta" -> new OrderbookDeltaMessage(msg.path("market_ticker").asText(), msg.path("price_dollars").asText(), msg.path("delta_fp").asText(), msg.path("side").asText());
                case "trade" -> new TradeMessage(msg.path("market_ticker").asText(), msg.path("trade_id").asText(), msg.path("count_fp").asText(), msg.path("yes_price_dollars").asText(null), msg.path("taker_side").asText(null), parseTs(msg.path("ts")));
                case "fill" -> new FillMessage(msg.path("market_ticker").asText(), msg.path("order_id").asText(), msg.path("trade_id").asText(), msg.path("count_fp").asText(), msg.path("side").asText());
                case "position" -> new PositionMessage(msg.path("market_ticker").asText(), msg.path("position_fp").asText());
                case "market_lifecycle" -> new MarketLifecycleMessage(msg.path("market_ticker").asText(), msg.path("status").asText());
                case "order_group_update" -> new OrderGroupUpdateMessage(msg.path("order_group_id").asText(), msg.path("status").asText());
                default -> null;
            };
            if (message == null) return;
            String dispatchChannel = "orderbook_snapshot".equals(type) ? "orderbook_delta" : type;
            handlers.getOrDefault(dispatchChannel, List.of()).forEach(handler -> handler.accept(message));
        } catch (Exception ignored) {
        }
    }

    private List<List<String>> levelMatrix(JsonNode node) {
        return JsonSupport.MAPPER.convertValue(
                node,
                JsonSupport.MAPPER.getTypeFactory().constructCollectionType(
                        List.class,
                        JsonSupport.MAPPER.getTypeFactory().constructCollectionType(List.class, String.class)
                )
        );
    }

    public static Long parseTs(JsonNode ts) {
        if (ts == null || ts.isMissingNode() || ts.isNull()) return null;
        if (ts.isIntegralNumber()) return ts.asLong();
        try {
            return OffsetDateTime.parse(ts.asText()).toInstant().toEpochMilli();
        } catch (Exception e) {
            return null;
        }
    }

    private void sendIfConnected(String command, Map<String, Object> payload) {
        if (connected) send(command, payload);
    }

    private void send(String command, Map<String, Object> payload) {
        if (webSocket != null) {
            Map<String, Object> envelope = new LinkedHashMap<>();
            envelope.put("type", command);
            envelope.putAll(payload);
            webSocket.sendText(JsonSupport.write(envelope), true);
        }
    }

    @Override
    public void onOpen(WebSocket webSocket) {
        connected = true;
        WebSocket.Listener.super.onOpen(webSocket);
    }

    @Override
    public CompletionStage<?> onText(WebSocket webSocket, CharSequence data, boolean last) {
        messageBuffer.append(data);
        if (last) {
            dispatch(messageBuffer.toString());
            messageBuffer.setLength(0);
        }
        return WebSocket.Listener.super.onText(webSocket, data, last);
    }

    @Override
    public CompletionStage<?> onClose(WebSocket webSocket, int statusCode, String reason) {
        connected = false;
        return WebSocket.Listener.super.onClose(webSocket, statusCode, reason);
    }

    @Override
    public void onError(WebSocket webSocket, Throwable error) {
        connected = false;
        WebSocket.Listener.super.onError(webSocket, error);
    }
}
