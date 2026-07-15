package com.javifalces.kalshi;

import com.javifalces.kalshi.model.OrderData;
import java.time.Duration;

public final class Order {
    private final KalshiClient client;
    private OrderData data;

    public Order(KalshiClient client, OrderData data) {
        this.client = client;
        this.data = data;
    }

    public String orderId() { return data.orderId(); }
    public String ticker() { return data.ticker(); }
    public OrderStatus status() { return data.status(); }
    public Action action() { return data.action(); }
    public Side side() { return data.side(); }

    public Order cancel() {
        this.data = client.portfolio().cancelOrder(orderId()).data;
        return this;
    }

    public Order refresh() {
        this.data = client.portfolio().getOrder(orderId()).data;
        return this;
    }

    public Order waitUntilTerminal(Duration timeout) {
        long deadline = System.nanoTime() + timeout.toNanos();
        while (status() == OrderStatus.RESTING || status() == OrderStatus.PENDING) {
            if (System.nanoTime() > deadline) {
                throw new IllegalStateException("Timed out waiting for order to reach a terminal state");
            }
            refresh();
            if (status() == OrderStatus.RESTING || status() == OrderStatus.PENDING) {
                try {
                    Thread.sleep(100);
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    throw new IllegalStateException("Interrupted while waiting for order to reach a terminal state", e);
                }
            }
        }
        return this;
    }

    OrderData raw() { return data; }
}
