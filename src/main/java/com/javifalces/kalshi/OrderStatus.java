package com.javifalces.kalshi;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.javifalces.kalshi.util.LowercaseEnum;

public enum OrderStatus implements LowercaseEnum {
    RESTING, EXECUTED, CANCELED, PENDING, REJECTED;

    @Override
    public String value() { return name().toLowerCase(); }

    @JsonCreator
    public static OrderStatus fromValue(String value) { return value == null ? null : valueOf(value.toUpperCase()); }
}
