package com.javifalces.kalshi;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

class ExchangeAndApiKeysTest {
    @Test
    void exchangeEndpointsParseResponses() throws Exception {
        TestSupport.FakeTransport transport = new TestSupport.FakeTransport()
                .enqueue(200, """
                        {"exchange_active":true,"trading_active":true}
                        """)
                .enqueue(200, """
                        {"schedule":{"standard_hours":[]}}
                        """);
        KalshiClient client = TestSupport.client(transport);

        assertTrue(client.exchange().isTrading());
        assertTrue(client.exchange().getSchedule().containsKey("standard_hours"));
    }

    @Test
    void apiKeyEndpointsParseResponses() throws Exception {
        TestSupport.FakeTransport transport = new TestSupport.FakeTransport()
                .enqueue(200, """
                        {"api_keys":[{"id":"key-001","name":"Trading Bot","scopes":["read","trade"]}]}
                        """)
                .enqueue(200, """
                        {"api_key_id":"new-key"}
                        """)
                .enqueue(200, """
                        {"usage_tier":"standard","read_limit":20,"write_limit":10}
                        """);
        KalshiClient client = TestSupport.client(transport);

        assertEquals(1, client.apiKeys().list().size());
        assertEquals("new-key", client.apiKeys().create("PUBLIC", "My Key"));
        assertEquals(20, client.apiKeys().getLimits().readLimit());
    }
}
