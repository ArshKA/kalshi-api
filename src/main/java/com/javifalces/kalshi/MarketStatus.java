package com.javifalces.kalshi;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.javifalces.kalshi.util.LowercaseEnum;

public enum MarketStatus implements LowercaseEnum {
    OPEN, CLOSED, SETTLED;

    @Override
    public String value() { return name().toLowerCase(); }

    @JsonCreator
    public static MarketStatus fromValue(String value) { return value == null ? null : valueOf(value.toUpperCase()); }
}
