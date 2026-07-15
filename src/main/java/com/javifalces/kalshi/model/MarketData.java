package com.javifalces.kalshi.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.javifalces.kalshi.MarketStatus;

@JsonIgnoreProperties(ignoreUnknown = true)
public record MarketData(String ticker, String eventTicker, String seriesTicker, String title,
                         MarketStatus status, String yesBidDollars, String yesAskDollars, String volumeFp) {}
