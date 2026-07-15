package com.javifalces.kalshi.transport;

import java.util.List;
import java.util.Map;

public record HttpResponseData(int statusCode, String body, Map<String, List<String>> headers) {
    public String firstHeader(String name) {
        List<String> values = headers.get(name);
        return values == null || values.isEmpty() ? null : values.get(0);
    }
}
