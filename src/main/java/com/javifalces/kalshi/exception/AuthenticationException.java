package com.javifalces.kalshi.exception;

public class AuthenticationException extends KalshiApiException {
    public AuthenticationException(int statusCode, String message, String errorCode, String method, String endpoint,
                                   String requestBody, String responseBody) {
        super(statusCode, message, errorCode, method, endpoint, requestBody, responseBody);
    }
}
