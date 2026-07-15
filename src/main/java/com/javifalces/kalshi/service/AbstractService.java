package com.javifalces.kalshi.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.javifalces.kalshi.KalshiClient;

public abstract class AbstractService {
    protected final KalshiClient client;

    protected AbstractService(KalshiClient client) {
        this.client = client;
    }

    protected JsonNode get(String endpoint) {
        return client.request("GET", endpoint, null, null);
    }

    protected JsonNode post(String endpoint, Object body) {
        return client.request("POST", endpoint, null, body);
    }

    protected JsonNode delete(String endpoint) {
        return client.request("DELETE", endpoint, null, null);
    }
}
