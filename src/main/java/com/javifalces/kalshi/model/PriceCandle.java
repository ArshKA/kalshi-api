package com.javifalces.kalshi.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

@JsonIgnoreProperties(ignoreUnknown = true)
public record PriceCandle(String openDollars, String highDollars, String lowDollars, String closeDollars) {}
