package com.javifalces.kalshi.transport;

import java.io.IOException;
import java.util.concurrent.CompletableFuture;

public interface HttpTransport {
    HttpResponseData execute(HttpRequestData request) throws IOException, InterruptedException;

    default CompletableFuture<HttpResponseData> executeAsync(HttpRequestData request) {
        return CompletableFuture.supplyAsync(() -> {
            try {
                return execute(request);
            } catch (IOException e) {
                throw new RuntimeException(e);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                throw new RuntimeException(e);
            }
        });
    }
}
