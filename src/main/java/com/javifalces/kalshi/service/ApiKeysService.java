package com.javifalces.kalshi.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonNode;
import com.javifalces.kalshi.KalshiClient;
import com.javifalces.kalshi.model.ApiKeyInfo;
import com.javifalces.kalshi.model.ApiLimits;
import com.javifalces.kalshi.model.GeneratedApiKey;
import com.javifalces.kalshi.util.JsonSupport;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class ApiKeysService extends AbstractService {
    public ApiKeysService(KalshiClient client) { super(client); }

    public List<ApiKeyInfo> list() {
        JsonNode root = get("/api_keys");
        return JsonSupport.MAPPER.convertValue(root.path("api_keys"), new TypeReference<List<ApiKeyInfo>>() {});
    }

    public String create(String publicKey, String name) {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("public_key", publicKey);
        body.put("name", name);
        return post("/api_keys", body).path("api_key_id").asText();
    }

    public GeneratedApiKey generate(String name) {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("name", name);
        return JsonSupport.MAPPER.convertValue(post("/api_keys/generate", body), GeneratedApiKey.class);
    }

    public void deleteKey(String keyId) {
        delete("/api_keys/" + keyId);
    }

    public ApiLimits getLimits() {
        return JsonSupport.MAPPER.convertValue(get("/account/limits"), ApiLimits.class);
    }
}
