package com.javifalces.kalshi.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

@JsonIgnoreProperties(ignoreUnknown = true)
public record Position(String ticker, String eventTicker, String positionFp, String totalTradedDollars,
                       Integer restingOrdersCount, String feesPaidDollars, String realizedPnlDollars) {}
