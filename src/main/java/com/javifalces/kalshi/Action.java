package com.javifalces.kalshi;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.javifalces.kalshi.util.LowercaseEnum;

public enum Action implements LowercaseEnum {
    BUY, SELL;

    @Override
    public String value() { return name().toLowerCase(); }

    @JsonCreator
    public static Action fromValue(String value) { return value == null ? null : valueOf(value.toUpperCase()); }
}
