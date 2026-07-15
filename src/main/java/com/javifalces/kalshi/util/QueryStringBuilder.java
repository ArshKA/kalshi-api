package com.javifalces.kalshi.util;

import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.StringJoiner;

public final class QueryStringBuilder {
    private QueryStringBuilder() {}

    public static String build(Map<String, ?> params) {
        if (params == null || params.isEmpty()) {
            return "";
        }
        StringJoiner joiner = new StringJoiner("&");
        params.forEach((key, value) -> {
            if (value != null) {
                joiner.add(encode(key) + "=" + encode(value.toString()));
            }
        });
        String query = joiner.toString();
        return query.isEmpty() ? "" : "?" + query;
    }

    private static String encode(String value) {
        return URLEncoder.encode(value, StandardCharsets.UTF_8);
    }
}
