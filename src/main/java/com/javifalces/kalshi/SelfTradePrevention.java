package com.javifalces.kalshi;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.javifalces.kalshi.util.LowercaseEnum;

public enum SelfTradePrevention implements LowercaseEnum {
    CANCEL_NEWEST, CANCEL_OLDEST, CANCEL_BOTH;

    @Override
    public String value() { return name().toLowerCase(); }

    @JsonCreator
    public static SelfTradePrevention fromValue(String value) {
        return value == null ? null : valueOf(value.toUpperCase().replace('-', '_'));
    }
}
