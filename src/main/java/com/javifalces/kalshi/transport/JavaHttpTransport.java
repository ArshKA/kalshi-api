package com.javifalces.kalshi.transport;

import java.io.IOException;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.concurrent.CompletableFuture;

public class JavaHttpTransport implements HttpTransport {
    private final HttpClient httpClient;

    public JavaHttpTransport() {
        this(HttpClient.newBuilder().build());
    }

    public JavaHttpTransport(HttpClient httpClient) {
        this.httpClient = httpClient;
    }

    @Override
    public HttpResponseData execute(HttpRequestData request) throws IOException, InterruptedException {
        HttpRequest httpRequest = buildRequest(request);
        HttpResponse<String> response = httpClient.send(httpRequest, HttpResponse.BodyHandlers.ofString());
        return new HttpResponseData(response.statusCode(), response.body(), response.headers().map());
    }

    @Override
    public CompletableFuture<HttpResponseData> executeAsync(HttpRequestData request) {
        HttpRequest httpRequest = buildRequest(request);
        return httpClient.sendAsync(httpRequest, HttpResponse.BodyHandlers.ofString())
                .thenApply(response -> new HttpResponseData(response.statusCode(), response.body(), response.headers().map()));
    }

    private HttpRequest buildRequest(HttpRequestData request) {
        HttpRequest.Builder builder = HttpRequest.newBuilder(request.uri())
                .timeout(Duration.ofSeconds(request.timeoutSeconds()));
        request.headers().forEach(builder::header);
        if (request.body() == null) {
            builder.method(request.method(), HttpRequest.BodyPublishers.noBody());
        } else {
            builder.method(request.method(), HttpRequest.BodyPublishers.ofString(request.body()));
        }
        return builder.build();
    }
}
