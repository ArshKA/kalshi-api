package com.javifalces.kalshi.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

@JsonIgnoreProperties(ignoreUnknown = true)
public record GeneratedApiKey(String id, String privateKey, String name) {}
