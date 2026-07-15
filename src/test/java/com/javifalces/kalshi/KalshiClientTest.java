package com.javifalces.kalshi;

import com.javifalces.kalshi.exception.AuthenticationException;
import com.javifalces.kalshi.exception.InsufficientFundsException;
import com.javifalces.kalshi.exception.KalshiApiException;
import com.javifalces.kalshi.exception.OrderRejectedException;
import com.javifalces.kalshi.exception.ResourceNotFoundException;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

class KalshiClientTest {
    @Test
    void authHeadersGenerated() throws Exception {
        TestSupport.FakeTransport transport = new TestSupport.FakeTransport().enqueue(200, "{}");
        KalshiClient client = TestSupport.client(transport);

        client.get("/test");

        assertEquals("fake_key", transport.lastRequest.headers().get("KALSHI-ACCESS-KEY"));
        assertNotNull(transport.lastRequest.headers().get("KALSHI-ACCESS-SIGNATURE"));
        assertNotNull(transport.lastRequest.headers().get("KALSHI-ACCESS-TIMESTAMP"));
    }

    @Test
    void handleSuccess() throws Exception {
        KalshiClient client = TestSupport.client(new TestSupport.FakeTransport().enqueue(200, """
                {"data":"ok"}
                """));
        assertEquals("ok", client.get("/test").path("data").asText());
    }

    @Test
    void handle401RaisesAuthenticationError() throws Exception {
        KalshiClient client = TestSupport.client(new TestSupport.FakeTransport().enqueue(401, """
                {"message":"Unauthorized"}
                """));
        assertThrows(AuthenticationException.class, () -> client.get("/test"));
    }

    @Test
    void handle404RaisesNotFound() throws Exception {
        KalshiClient client = TestSupport.client(new TestSupport.FakeTransport().enqueue(404, """
                {"message":"Not found"}
                """));
        assertThrows(ResourceNotFoundException.class, () -> client.get("/markets/BAD"));
    }

    @Test
    void insufficientFundsErrorMapsByCode() throws Exception {
        KalshiClient client = TestSupport.client(new TestSupport.FakeTransport().enqueue(400, """
                {"code":"insufficient_funds","message":"No money"}
                """));
        assertThrows(InsufficientFundsException.class, () -> client.post("/portfolio/orders", java.util.Map.of()));
    }

    @Test
    void orderRejectedCodeMaps() throws Exception {
        KalshiClient client = TestSupport.client(new TestSupport.FakeTransport().enqueue(400, """
                {"code":"order_rejected","message":"Rejected"}
                """));
        KalshiApiException ex = assertThrows(OrderRejectedException.class, () -> client.post("/portfolio/orders", java.util.Map.of("ticker", "X")));
        assertTrue(ex.getMessage().contains("[POST /portfolio/orders]"));
        assertEquals("order_rejected", ex.getErrorCode());
    }
}
