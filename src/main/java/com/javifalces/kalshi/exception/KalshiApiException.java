package com.javifalces.kalshi.exception;

public class KalshiApiException extends KalshiException {
    private final int statusCode;
    private final String errorCode;
    private final String method;
    private final String endpoint;
    private final String requestBody;
    private final String responseBody;

    public KalshiApiException(int statusCode, String message, String errorCode, String method, String endpoint,
                              String requestBody, String responseBody) {
        super(buildMessage(statusCode, message, method, endpoint));
        this.statusCode = statusCode;
        this.errorCode = errorCode;
        this.method = method;
        this.endpoint = endpoint;
        this.requestBody = requestBody;
        this.responseBody = responseBody;
    }

    private static String buildMessage(int statusCode, String message, String method, String endpoint) {
        String context = method != null && endpoint != null ? " [" + method + " " + endpoint + "]" : "";
        return statusCode + " " + message + context;
    }

    public int getStatusCode() { return statusCode; }
    public String getErrorCode() { return errorCode; }
    public String getMethod() { return method; }
    public String getEndpoint() { return endpoint; }
    public String getRequestBody() { return requestBody; }
    public String getResponseBody() { return responseBody; }
    public boolean isRetryable() { return statusCode == 429 || (statusCode >= 500 && statusCode < 600); }

    @Override
    public String toString() {
        return getClass().getSimpleName() + "{statusCode=" + statusCode + ", errorCode='" + errorCode + "', endpoint='" + endpoint + "'}";
    }
}
