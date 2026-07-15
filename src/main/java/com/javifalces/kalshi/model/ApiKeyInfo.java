package com.javifalces.kalshi.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import java.util.List;

@JsonIgnoreProperties(ignoreUnknown = true)
public record ApiKeyInfo(String id, String name, String createdTime, String lastUsed, List<String> scopes) {}
