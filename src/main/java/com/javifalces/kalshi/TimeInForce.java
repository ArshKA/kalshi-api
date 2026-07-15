package com.javifalces.kalshi;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.javifalces.kalshi.util.LowercaseEnum;

public enum TimeInForce implements LowercaseEnum {
    GTC, IOC, FOK;

    @Override
    public String value() { return name().toLowerCase(); }

    @JsonCreator
    public static TimeInForce fromValue(String value) { return value == null ? null : valueOf(value.toUpperCase()); }
}
