package com.javifalces.kalshi;

import com.javifalces.kalshi.model.Balance;
import java.time.Duration;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Executor;
import java.util.concurrent.ForkJoinPool;

public final class AsyncKalshiClient {
    private final KalshiClient delegate;
    private final Executor executor;

    public AsyncKalshiClient(KalshiClient delegate) {
        this(delegate, ForkJoinPool.commonPool());
    }

    public AsyncKalshiClient(KalshiClient delegate, Executor executor) {
        this.delegate = delegate;
        this.executor = executor;
    }

    public CompletableFuture<Market> getMarket(String ticker) {
        return CompletableFuture.supplyAsync(() -> delegate.getMarket(ticker), executor);
    }

    public CompletableFuture<List<Market>> getMarkets(String seriesTicker, String eventTicker, MarketStatus status, Integer limit, boolean fetchAll) {
        return CompletableFuture.supplyAsync(() -> delegate.getMarkets(seriesTicker, eventTicker, status, limit, fetchAll), executor);
    }

    public CompletableFuture<Event> getEvent(String ticker) {
        return CompletableFuture.supplyAsync(() -> delegate.getEvent(ticker), executor);
    }

    public CompletableFuture<Balance> getBalance() {
        return CompletableFuture.supplyAsync(() -> delegate.portfolio().getBalance(), executor);
    }

    public CompletableFuture<Order> placeOrder(String ticker, Action action, Side side, String countFp, String yesPriceDollars) {
        return CompletableFuture.supplyAsync(() -> delegate.portfolio().placeOrder(ticker, action, side, countFp, yesPriceDollars), executor);
    }

    public CompletableFuture<Order> waitUntilTerminal(Order order, Duration timeout) {
        return CompletableFuture.supplyAsync(() -> order.waitUntilTerminal(timeout), executor);
    }

    public KalshiClient sync() {
        return delegate;
    }
}
