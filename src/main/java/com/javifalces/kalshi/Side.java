package com.javifalces.kalshi;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.javifalces.kalshi.util.LowercaseEnum;

public enum Side implements LowercaseEnum {
    YES, NO;

    @Override
    public String value() { return name().toLowerCase(); }

    @JsonCreator
    public static Side fromValue(String value) { return value == null ? null : valueOf(value.toUpperCase()); }
}
