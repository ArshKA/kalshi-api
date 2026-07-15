package com.javifalces.kalshi.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.javifalces.kalshi.Action;
import com.javifalces.kalshi.Side;

@JsonIgnoreProperties(ignoreUnknown = true)
public record Fill(String tradeId, String ticker, String orderId, Side side, Action action,
                   String countFp, String yesPriceFixed, String noPriceFixed,
                   String createdTime, Boolean isTaker) {}
