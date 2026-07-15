package com.javifalces.kalshi;

import com.fasterxml.jackson.databind.JsonNode;
import com.javifalces.kalshi.exception.AuthenticationException;
import com.javifalces.kalshi.exception.InsufficientFundsException;
import com.javifalces.kalshi.exception.KalshiApiException;
import com.javifalces.kalshi.exception.OrderRejectedException;
import com.javifalces.kalshi.exception.RateLimitException;
import com.javifalces.kalshi.exception.ResourceNotFoundException;
import com.javifalces.kalshi.rate.NoOpRateLimiter;
import com.javifalces.kalshi.rate.RateLimiter;
import com.javifalces.kalshi.service.ApiKeysService;
import com.javifalces.kalshi.service.ExchangeService;
import com.javifalces.kalshi.service.HistoryService;
import com.javifalces.kalshi.service.MarketsService;
import com.javifalces.kalshi.service.PortfolioService;
import com.javifalces.kalshi.transport.HttpRequestData;
import com.javifalces.kalshi.transport.HttpResponseData;
import com.javifalces.kalshi.transport.HttpTransport;
import com.javifalces.kalshi.transport.JavaHttpTransport;
import com.javifalces.kalshi.util.AuthSigner;
import com.javifalces.kalshi.util.JsonSupport;
import com.javifalces.kalshi.util.PemUtils;
import com.javifalces.kalshi.util.QueryStringBuilder;

import java.io.IOException;
import java.net.URI;
import java.nio.file.Path;
import java.security.PrivateKey;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public class KalshiClient {
    public static final String DEFAULT_API_BASE = "https://api.elections.kalshi.com/trade-api/v2";
    public static final String DEMO_API_BASE = "https://demo-api.kalshi.co/trade-api/v2";
    private static final java.util.Set<String> ORDER_REJECTION_CODES = java.util.Set.of(
            "order_rejected", "market_closed", "market_settled", "invalid_price", "self_trade", "post_only_rejected"
    );

    private final String apiKeyId;
    private final String apiBase;
    private final String apiPath;
    private final int timeoutSeconds;
    private final int maxRetries;
    private final RateLimiter rateLimiter;
    private final HttpTransport transport;
    private final AuthSigner signer;

    private MarketsService markets;
    private PortfolioService portfolio;
    private ExchangeService exchange;
    private ApiKeysService apiKeys;
    private HistoryService history;

    public KalshiClient(String apiKeyId, Path privateKeyPath, boolean demo) {
        this(apiKeyId, privateKeyPath, demo ? DEMO_API_BASE : DEFAULT_API_BASE, 10, 3, new NoOpRateLimiter(), new JavaHttpTransport());
    }

    public KalshiClient(String apiKeyId, Path privateKeyPath, String apiBase, int timeoutSeconds, int maxRetries,
                        RateLimiter rateLimiter, HttpTransport transport) {
        if (apiKeyId == null || apiKeyId.isBlank()) {
            throw new IllegalArgumentException("API key ID required");
        }
        this.apiKeyId = apiKeyId;
        this.apiBase = apiBase;
        this.apiPath = URI.create(apiBase).getPath();
        this.timeoutSeconds = timeoutSeconds;
        this.maxRetries = maxRetries;
        this.rateLimiter = rateLimiter == null ? new NoOpRateLimiter() : rateLimiter;
        this.transport = transport == null ? new JavaHttpTransport() : transport;
        PrivateKey privateKey = PemUtils.readPrivateKey(privateKeyPath);
        this.signer = new AuthSigner(privateKey);
    }

    public JsonNode get(String endpoint) { return request("GET", endpoint, null, null); }
    public JsonNode post(String endpoint, Object body) { return request("POST", endpoint, null, body); }
    public JsonNode delete(String endpoint) { return request("DELETE", endpoint, null, null); }

    public JsonNode request(String method, String endpoint, Map<String, ?> query, Object body) {
        String queryString = QueryStringBuilder.build(query);
        URI uri = URI.create(apiBase + endpoint + queryString);
        String requestBody = body == null ? null : JsonSupport.write(body);
        String fullPath = apiPath + endpoint;
        KalshiApiException failure = null;

        for (int attempt = 0; attempt <= maxRetries; attempt++) {
            rateLimiter.acquire();
            long timestamp = System.currentTimeMillis();
            AuthSigner.SignedRequest signed = signer.sign(method, fullPath, timestamp);
            Map<String, String> headers = new LinkedHashMap<>();
            headers.put("Content-Type", "application/json");
            headers.put("KALSHI-ACCESS-KEY", apiKeyId);
            headers.put("KALSHI-ACCESS-SIGNATURE", signed.signature());
            headers.put("KALSHI-ACCESS-TIMESTAMP", signed.timestamp());
            HttpResponseData response;
            try {
                response = transport.execute(new HttpRequestData(method, uri, headers, requestBody, timeoutSeconds));
            } catch (IOException e) {
                throw new IllegalStateException("HTTP request failed", e);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                throw new IllegalStateException("HTTP request interrupted", e);
            }
            updateRateLimiter(response);
            if (response.statusCode() < 400) {
                try {
                    return response.body() == null || response.body().isBlank()
                            ? JsonSupport.MAPPER.createObjectNode()
                            : JsonSupport.MAPPER.readTree(response.body());
                } catch (IOException e) {
                    throw new IllegalStateException("Invalid JSON response", e);
                }
            }
            if (!isRetryable(response.statusCode()) || attempt == maxRetries) {
                failure = mapException(response, method, endpoint, requestBody);
                break;
            }
            sleep(computeBackoff(attempt, response.firstHeader("Retry-After")));
        }
        throw failure == null ? new IllegalStateException("Request failed without a mapped exception") : failure;
    }

    public Market getMarket(String ticker) { return markets().getMarket(ticker); }
    public List<Market> getMarkets(String seriesTicker, String eventTicker, MarketStatus status, Integer limit, boolean fetchAll) {
        return markets().getMarkets(seriesTicker, eventTicker, status, limit, fetchAll);
    }
    public Event getEvent(String ticker) { return markets().getEvent(ticker); }
    public List<Event> getEvents(String seriesTicker, Integer limit, boolean fetchAll) { return markets().getEvents(seriesTicker, limit, fetchAll); }

    public MarketsService markets() { return markets == null ? (markets = new MarketsService(this)) : markets; }
    public PortfolioService portfolio() { return portfolio == null ? (portfolio = new PortfolioService(this)) : portfolio; }
    public ExchangeService exchange() { return exchange == null ? (exchange = new ExchangeService(this)) : exchange; }
    public ApiKeysService apiKeys() { return apiKeys == null ? (apiKeys = new ApiKeysService(this)) : apiKeys; }
    public HistoryService history() { return history == null ? (history = new HistoryService(this)) : history; }

    public String apiBase() { return apiBase; }

    private void updateRateLimiter(HttpResponseData response) {
        try {
            String remaining = response.firstHeader("X-RateLimit-Remaining");
            String resetAt = response.firstHeader("X-RateLimit-Reset");
            rateLimiter.updateFromHeaders(remaining == null ? null : Integer.parseInt(remaining),
                    resetAt == null ? null : Integer.parseInt(resetAt));
        } catch (NumberFormatException ignored) {
        }
    }

    private boolean isRetryable(int statusCode) {
        return statusCode == 429 || statusCode == 500 || statusCode == 502 || statusCode == 503 || statusCode == 504;
    }

    private double computeBackoff(int attempt, String retryAfter) {
        double fallback = Math.min(Math.pow(2, attempt) * 0.5, 30.0);
        try {
            return retryAfter != null ? Double.parseDouble(retryAfter) : fallback;
        } catch (NumberFormatException e) {
            return fallback;
        }
    }

    private void sleep(double seconds) {
        try {
            Thread.sleep(Math.max(0L, Math.round(seconds * 1000)));
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("Retry sleep interrupted", e);
        }
    }

    private KalshiApiException mapException(HttpResponseData response, String method, String endpoint, String requestBody) {
        String message = response.body();
        String code = null;
        try {
            JsonNode error = JsonSupport.MAPPER.readTree(response.body());
            JsonNode inner = error.path("error");
            if (inner.isObject()) {
                message = inner.path("message").asText(error.path("message").asText(message));
                code = inner.path("code").asText(error.path("code").asText(null));
            } else {
                message = error.path("message").asText(error.path("error_message").asText(message));
                code = error.path("code").asText(error.path("error_code").asText(null));
            }
        } catch (IOException ignored) {
        }

        int status = response.statusCode();
        if (status == 401 || status == 403) {
            return new AuthenticationException(status, message, code, method, endpoint, requestBody, response.body());
        }
        if (status == 404) {
            return new ResourceNotFoundException(status, message, code, method, endpoint, requestBody, response.body());
        }
        if (status == 429) {
            return new RateLimitException(status, message, code, method, endpoint, requestBody, response.body());
        }
        if ("insufficient_funds".equals(code) || "insufficient_balance".equals(code)) {
            return new InsufficientFundsException(status, message, code, method, endpoint, requestBody, response.body());
        }
        if (code != null && ORDER_REJECTION_CODES.contains(code)) {
            return new OrderRejectedException(status, message, code, method, endpoint, requestBody, response.body());
        }
        return new KalshiApiException(status, message, code, method, endpoint, requestBody, response.body());
    }
}
