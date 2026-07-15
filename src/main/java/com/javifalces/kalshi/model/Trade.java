package com.javifalces.kalshi.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.javifalces.kalshi.Side;

@JsonIgnoreProperties(ignoreUnknown = true)
public record Trade(String tradeId, String marketTicker, String countFp,
                    String yesPriceDollars, Side takerSide, Long ts) {}
