package com.javifalces.kalshi;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;

public enum CandlestickPeriod {
    ONE_MINUTE("1m"), FIVE_MINUTES("5m"), ONE_HOUR("1h"), ONE_DAY("1d");

    private final String value;
    CandlestickPeriod(String value) { this.value = value; }
    @JsonValue public String value() { return value; }

    @JsonCreator
    public static CandlestickPeriod fromValue(String value) {
        if (value == null) return null;
        for (CandlestickPeriod period : values()) {
            if (period.value.equalsIgnoreCase(value)) return period;
        }
        throw new IllegalArgumentException("Unknown candlestick period: " + value);
    }
}
