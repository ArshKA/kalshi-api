package com.javifalces.kalshi;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.javifalces.kalshi.util.LowercaseEnum;

public enum OrderType implements LowercaseEnum {
    LIMIT, MARKET;

    @Override
    public String value() { return name().toLowerCase(); }

    @JsonCreator
    public static OrderType fromValue(String value) { return value == null ? null : valueOf(value.toUpperCase()); }
}
