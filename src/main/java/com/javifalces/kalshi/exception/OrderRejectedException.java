package com.javifalces.kalshi.exception;

public class OrderRejectedException extends KalshiApiException {
    public OrderRejectedException(int statusCode, String message, String errorCode, String method, String endpoint,
                                  String requestBody, String responseBody) {
        super(statusCode, message, errorCode, method, endpoint, requestBody, responseBody);
    }
}
