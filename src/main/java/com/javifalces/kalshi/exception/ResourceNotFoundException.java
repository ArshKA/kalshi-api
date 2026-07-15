package com.javifalces.kalshi.exception;

public class ResourceNotFoundException extends KalshiApiException {
    public ResourceNotFoundException(int statusCode, String message, String errorCode, String method, String endpoint,
                                     String requestBody, String responseBody) {
        super(statusCode, message, errorCode, method, endpoint, requestBody, responseBody);
    }
}
