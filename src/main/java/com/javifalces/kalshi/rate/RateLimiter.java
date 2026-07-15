package com.javifalces.kalshi.rate;

public interface RateLimiter {
    double acquire();
    default void updateFromHeaders(Integer remaining, Integer resetAt) {}
}
