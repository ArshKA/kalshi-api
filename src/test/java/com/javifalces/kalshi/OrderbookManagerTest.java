package com.javifalces.kalshi;

import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

class OrderbookManagerTest {
    @Test
    void orderbookManagerMaintainsBidAskState() {
        OrderbookManager manager = new OrderbookManager("ABC-123");
        manager.applySnapshot(List.of(List.of("0.45", "100.00")), List.of(List.of("0.55", "150.00")));
        manager.applyDelta("yes", "0.45", "-10.00");

        assertEquals("0.45", manager.bestBid());
        assertEquals("0.45", manager.bestAsk());
        assertEquals("0", manager.spread());
    }
}
