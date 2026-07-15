package com.javifalces.kalshi.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.javifalces.kalshi.Action;
import com.javifalces.kalshi.OrderStatus;
import com.javifalces.kalshi.OrderType;
import com.javifalces.kalshi.Side;

@JsonIgnoreProperties(ignoreUnknown = true)
public record OrderData(String orderId, String ticker, Action action, Side side,
                        String initialCountFp, String remainingCountFp,
                        String yesPriceDollars, String noPriceDollars,
                        OrderStatus status, OrderType type) {}
