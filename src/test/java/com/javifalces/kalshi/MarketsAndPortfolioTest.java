package com.javifalces.kalshi;

import org.junit.jupiter.api.Test;

import java.time.Duration;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

class MarketsAndPortfolioTest {
    @Test
    void getMarketParsesMarketData() throws Exception {
        TestSupport.FakeTransport transport = new TestSupport.FakeTransport()
                .enqueue(200, """
                        {"market":{"ticker":"KXTEST-A","event_ticker":"KXTEST","title":"Test Market","status":"open","yes_bid_dollars":"0.45","yes_ask_dollars":"0.55"}}
                        """);
        KalshiClient client = TestSupport.client(transport);

        Market market = client.getMarket("KXTEST-A");

        assertEquals("KXTEST-A", market.ticker());
        assertEquals("Test Market", market.title());
        assertEquals("0.45", market.yesBidDollars());
    }

    @Test
    void getMarketsSupportsFiltersAndPagination() throws Exception {
        TestSupport.FakeTransport transport = new TestSupport.FakeTransport()
                .enqueue(200, """
                        {"markets":[{"ticker":"M1"}],"cursor":"page2"}
                        """)
                .enqueue(200, """
                        {"markets":[{"ticker":"M2"}],"cursor":""}
                        """);
        KalshiClient client = TestSupport.client(transport);

        List<Market> markets = client.getMarkets("INXD", "KXTEST", MarketStatus.OPEN, 50, true);

        assertEquals(2, markets.size());
        assertEquals(2, transport.calls);
        assertTrue(transport.lastRequest.uri().toString().contains("status=open"));
        assertTrue(transport.lastRequest.uri().toString().contains("limit=50"));
    }

    @Test
    void marketCandlesticksResolveSeriesFromEvent() throws Exception {
        TestSupport.FakeTransport transport = new TestSupport.FakeTransport()
                .enqueue(200, """
                        {"market":{"ticker":"KXTEST-A","series_ticker":null,"event_ticker":"KXTEST"}}
                        """)
                .enqueue(200, """
                        {"event":{"event_ticker":"KXTEST","series_ticker":"KXSERIES"}}
                        """)
                .enqueue(200, """
                        {"ticker":"KXTEST-A","candlesticks":[]}
                        """);
        KalshiClient client = TestSupport.client(transport);

        Market market = client.getMarket("KXTEST-A");

        assertEquals("KXTEST-A", market.getCandlesticks(1, 2).ticker());
    }

    @Test
    void portfolioPlaceCancelAndWaitForOrder() throws Exception {
        TestSupport.FakeTransport transport = new TestSupport.FakeTransport()
                .enqueue(200, """
                        {"order":{"order_id":"order-1","ticker":"KXTEST","status":"resting","action":"buy","side":"yes"}}
                        """)
                .enqueue(200, """
                        {"order":{"order_id":"order-1","ticker":"KXTEST","status":"executed","action":"buy","side":"yes"}}
                        """);
        KalshiClient client = TestSupport.client(transport);

        Order order = client.portfolio().placeOrder("KXTEST", Action.BUY, Side.YES, "10", "0.50");
        order.waitUntilTerminal(Duration.ofSeconds(1));

        assertEquals(OrderStatus.EXECUTED, order.status());
    }
}
