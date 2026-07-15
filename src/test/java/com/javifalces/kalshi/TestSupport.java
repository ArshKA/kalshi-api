package com.javifalces.kalshi;

import com.javifalces.kalshi.transport.HttpRequestData;
import com.javifalces.kalshi.transport.HttpResponseData;
import com.javifalces.kalshi.transport.HttpTransport;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.util.ArrayDeque;
import java.util.Base64;
import java.util.Deque;
import java.util.List;
import java.util.Map;

final class TestSupport {
    private TestSupport() {}

    static Path writePrivateKey() throws Exception {
        KeyPairGenerator generator = KeyPairGenerator.getInstance("RSA");
        generator.initialize(2048);
        KeyPair pair = generator.generateKeyPair();
        String pem = "-----BEGIN PRIVATE KEY-----\n"
                + Base64.getMimeEncoder(64, "\n".getBytes()).encodeToString(pair.getPrivate().getEncoded())
                + "\n-----END PRIVATE KEY-----\n";
        Path file = Files.createTempFile("kalshi-test-key", ".pem");
        Files.writeString(file, pem);
        file.toFile().deleteOnExit();
        return file;
    }

    static KalshiClient client(FakeTransport transport) throws Exception {
        return new KalshiClient("fake_key", writePrivateKey(), KalshiClient.DEMO_API_BASE, 10, 1, null, transport);
    }

    static final class FakeTransport implements HttpTransport {
        final Deque<HttpResponseData> responses = new ArrayDeque<>();
        HttpRequestData lastRequest;
        int calls;

        FakeTransport enqueue(int statusCode, String body) {
            responses.add(new HttpResponseData(statusCode, body, Map.of()));
            return this;
        }

        FakeTransport enqueue(int statusCode, String body, Map<String, List<String>> headers) {
            responses.add(new HttpResponseData(statusCode, body, headers));
            return this;
        }

        @Override
        public HttpResponseData execute(HttpRequestData request) throws IOException {
            this.lastRequest = request;
            this.calls++;
            if (responses.isEmpty()) {
                throw new IOException("No fake response queued");
            }
            return responses.removeFirst();
        }
    }
}
