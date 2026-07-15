package com.javifalces.kalshi.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonNode;
import com.javifalces.kalshi.KalshiClient;
import com.javifalces.kalshi.model.Announcement;
import com.javifalces.kalshi.model.ExchangeStatus;
import com.javifalces.kalshi.util.JsonSupport;
import java.util.List;
import java.util.Map;

public final class ExchangeService extends AbstractService {
    public ExchangeService(KalshiClient client) { super(client); }

    public ExchangeStatus getStatus() {
        return JsonSupport.MAPPER.convertValue(get("/exchange/status"), ExchangeStatus.class);
    }

    public boolean isTrading() {
        ExchangeStatus status = getStatus();
        return Boolean.TRUE.equals(status.tradingActive());
    }

    public Map<String, Object> getSchedule() {
        JsonNode root = get("/exchange/schedule");
        return JsonSupport.MAPPER.convertValue(root.path("schedule"), new TypeReference<Map<String, Object>>() {});
    }

    public List<Announcement> getAnnouncements() {
        JsonNode root = get("/exchange/announcements");
        return JsonSupport.MAPPER.convertValue(root.path("announcements"), new TypeReference<List<Announcement>>() {});
    }

    public long getUserDataTimestamp() {
        return get("/exchange/user_data_timestamp").path("user_data_timestamp").asLong(0L);
    }
}
