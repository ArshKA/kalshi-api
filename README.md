# java-kalshi

A Maven-managed Java client for the [Kalshi](https://kalshi.com) trading API.

## Highlights

- RSA-PSS authenticated HTTP client
- Sync client plus `CompletableFuture` async facade
- Markets, events, portfolio, exchange, history, and API keys services
- WebSocket feed message parsing and subscription tracking
- Local orderbook manager and token-bucket rate limiter
- JUnit coverage for the core preserved behaviors

## Project layout

- `/src/main/java/com/javifalces/kalshi` - Java SDK
- `/src/test/java/com/javifalces/kalshi` - JUnit tests
- `/pykalshi`, `/tests`, `/web` - original Python implementation retained as migration reference

## Requirements

- Java 17+
- Maven 3.9+

## Build

```bash
mvn compile
```

## Test

```bash
mvn test
```

## Quick start

```java
import com.javifalces.kalshi.KalshiClient;
import java.nio.file.Path;

KalshiClient client = new KalshiClient(
    System.getenv("KALSHI_API_KEY_ID"),
    Path.of(System.getenv("KALSHI_PRIVATE_KEY_PATH")),
    true
);

var markets = client.getMarkets(null, null, null, 10, false);
var balance = client.portfolio().getBalance();
var status = client.exchange().getStatus();
```

## WebSocket feed

```java
import com.javifalces.kalshi.feed.Feed;

Feed feed = new Feed(client);
feed.on("ticker", message -> System.out.println(message));
feed.subscribe("ticker", "KXBTC-25MAR15-B100000", null);
```

## Credentials

Set the same environment variables used by the previous Python client:

```bash
export KALSHI_API_KEY_ID="your-key-id"
export KALSHI_PRIVATE_KEY_PATH="/absolute/path/to/private_key.pem"
```

The Java client expects a PKCS#8 PEM RSA private key.

## Notes

- The Java port preserves the core repo behavior around signing, request handling, service APIs, feed parsing, and orderbook state.
- The Python source remains in the repository as a reference while the migration artifacts are kept in sync.
