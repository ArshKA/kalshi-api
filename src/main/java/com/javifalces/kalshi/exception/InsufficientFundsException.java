package com.javifalces.kalshi.exception;

public class InsufficientFundsException extends KalshiApiException {
    public InsufficientFundsException(int statusCode, String message, String errorCode, String method, String endpoint,
                                      String requestBody, String responseBody) {
        super(statusCode, message, errorCode, method, endpoint, requestBody, responseBody);
    }
}
