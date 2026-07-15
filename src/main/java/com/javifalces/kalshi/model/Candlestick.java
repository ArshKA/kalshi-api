package com.javifalces.kalshi.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

@JsonIgnoreProperties(ignoreUnknown = true)
public record Candlestick(long endPeriodTs, String volumeFp, String openInterestFp, PriceCandle price) {}
