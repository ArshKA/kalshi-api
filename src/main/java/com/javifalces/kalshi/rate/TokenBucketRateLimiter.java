package com.javifalces.kalshi.rate;

public class TokenBucketRateLimiter implements RateLimiter {
    private final double requestsPerSecond;
    private final double burst;
    private final Sleeper sleeper;
    private double tokens;
    private double lastRefillAt;

    public TokenBucketRateLimiter(double requestsPerSecond, double burst) {
        this(requestsPerSecond, burst, new SystemSleeper(), System::nanoTime);
    }

    public TokenBucketRateLimiter(double requestsPerSecond, double burst, Sleeper sleeper, TimeSource timeSource) {
        this.requestsPerSecond = requestsPerSecond;
        this.burst = burst;
        this.sleeper = sleeper.withTimeSource(timeSource);
        this.tokens = burst;
        this.lastRefillAt = timeSource.monotonicSeconds();
    }

    @Override
    public synchronized double acquire() {
        double now = sleeper.timeSource().monotonicSeconds();
        refill(now);
        if (tokens >= 1.0) {
            tokens -= 1.0;
            return 0.0;
        }
        double wait = (1.0 - tokens) / requestsPerSecond;
        sleeper.sleep(wait);
        refill(sleeper.timeSource().monotonicSeconds());
        tokens = Math.max(0.0, tokens - 1.0);
        return wait;
    }

    private void refill(double now) {
        double elapsed = Math.max(0.0, now - lastRefillAt);
        tokens = Math.min(burst, tokens + elapsed * requestsPerSecond);
        lastRefillAt = now;
    }

    public interface TimeSource {
        double monotonicSeconds();
    }

    public interface Sleeper {
        void sleep(double seconds);
        default Sleeper withTimeSource(TimeSource source) {
            return new BoundSleeper(this, source);
        }
        default TimeSource timeSource() {
            return () -> System.nanoTime() / 1_000_000_000.0;
        }
    }

    private record BoundSleeper(Sleeper delegate, TimeSource timeSource) implements Sleeper {
        @Override public void sleep(double seconds) { delegate.sleep(seconds); }
    }

    private static class SystemSleeper implements Sleeper {
        @Override
        public void sleep(double seconds) {
            try {
                Thread.sleep(Math.max(0L, Math.round(seconds * 1000)));
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                throw new RuntimeException(e);
            }
        }
    }
}
