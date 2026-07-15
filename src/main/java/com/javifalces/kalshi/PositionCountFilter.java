package com.javifalces.kalshi;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.javifalces.kalshi.util.LowercaseEnum;

public enum PositionCountFilter implements LowercaseEnum {
    POSITION, RESTING_ORDERS;

    @Override
    public String value() { return name().toLowerCase(); }

    @JsonCreator
    public static PositionCountFilter fromValue(String value) {
        return value == null ? null : valueOf(value.toUpperCase().replace('-', '_'));
    }
}
