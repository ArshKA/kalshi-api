package com.javifalces.kalshi.transport;

import java.net.URI;
import java.util.Map;

public record HttpRequestData(String method, URI uri, Map<String, String> headers, String body, int timeoutSeconds) {}
