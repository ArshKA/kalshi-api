package com.javifalces.kalshi;

import com.javifalces.kalshi.rate.TokenBucketRateLimiter;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class TokenBucketRateLimiterTest {
    @Test
    void rateLimiterRefillsAtConfiguredRate() {
        class FakeClock implements TokenBucketRateLimiter.TimeSource, TokenBucketRateLimiter.Sleeper {
            double now;
            List<Double> sleeps = new ArrayList<>();
            @Override public double monotonicSeconds() { return now; }
            @Override public void sleep(double seconds) { sleeps.add(seconds); now += seconds + 1e-6; }
        }
        FakeClock clock = new FakeClock();
        TokenBucketRateLimiter limiter = new TokenBucketRateLimiter(2.0, 4.0, clock, clock);

        for (int i = 0; i < 4; i++) {
            assertEquals(0.0, limiter.acquire());
        }
        clock.now += 1.0;
        assertEquals(0.0, limiter.acquire());
        assertEquals(0.0, limiter.acquire());
        assertTrue(limiter.acquire() >= 0.49);
        assertTrue(clock.sleeps.get(clock.sleeps.size() - 1) >= 0.49);
    }
}
