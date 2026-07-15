package com.javifalces.kalshi.util;

import com.fasterxml.jackson.annotation.JsonValue;

public interface LowercaseEnum {
    @JsonValue
    String value();
}
