package com.javifalces.kalshi;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

class AsyncKalshiClientTest {
    @Test
    void asyncWrapperDelegatesToSyncClient() throws Exception {
        TestSupport.FakeTransport transport = new TestSupport.FakeTransport()
                .enqueue(200, """
                        {"market":{"ticker":"KXTEST-A"}}
                        """);
        AsyncKalshiClient client = new AsyncKalshiClient(TestSupport.client(transport));

        assertEquals("KXTEST-A", client.getMarket("KXTEST-A").join().ticker());
    }
}
