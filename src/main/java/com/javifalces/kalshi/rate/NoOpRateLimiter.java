package com.javifalces.kalshi.rate;

public class NoOpRateLimiter implements RateLimiter {
    @Override
    public double acquire() {
        return 0.0;
    }
}
