package com.javifalces.kalshi;

import com.javifalces.kalshi.feed.Feed;
import com.javifalces.kalshi.feed.OrderbookDeltaMessage;
import com.javifalces.kalshi.feed.OrderbookSnapshotMessage;
import com.javifalces.kalshi.feed.TickerMessage;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

class FeedTest {
    @Test
    void feedUsesDemoUrlAndStoresSubscriptions() throws Exception {
        Feed feed = new Feed(TestSupport.client(new TestSupport.FakeTransport()));
        feed.subscribe("ticker", "ABC-123", null);
        assertEquals(Feed.DEMO_WS_BASE, feed.wsUrl());
        assertEquals(1, feed.activeSubscriptions().size());
    }

    @Test
    void dispatchParsesTickerAndOrderbookMessages() throws Exception {
        Feed feed = new Feed(TestSupport.client(new TestSupport.FakeTransport()));
        List<Object> received = new ArrayList<>();
        feed.on("ticker", received::add);
        feed.on("orderbook_delta", received::add);

        feed.dispatch("""
                {"type":"ticker","msg":{"market_ticker":"ABC-123","yes_bid_dollars":"0.45","yes_ask_dollars":"0.55","volume_fp":"1000.00"}}
                """);
        feed.dispatch("""
                {"type":"orderbook_snapshot","msg":{"market_ticker":"ABC-123","yes_dollars":[["0.45","100.00"]],"no_dollars":[["0.55","150.00"]]}}
                """);
        feed.dispatch("""
                {"type":"orderbook_delta","msg":{"market_ticker":"ABC-123","price_dollars":"0.45","delta_fp":"-10.00","side":"yes"}}
                """);

        assertEquals(3, received.size());
        assertInstanceOf(TickerMessage.class, received.get(0));
        assertInstanceOf(OrderbookSnapshotMessage.class, received.get(1));
        assertInstanceOf(OrderbookDeltaMessage.class, received.get(2));
    }
}
