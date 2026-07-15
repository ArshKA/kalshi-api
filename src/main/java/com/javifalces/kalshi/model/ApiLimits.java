package com.javifalces.kalshi.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

@JsonIgnoreProperties(ignoreUnknown = true)
public record ApiLimits(String usageTier, Integer readLimit, Integer writeLimit) {}
