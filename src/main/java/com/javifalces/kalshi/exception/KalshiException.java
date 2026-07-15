package com.javifalces.kalshi.exception;

public class KalshiException extends RuntimeException {
    public KalshiException(String message) {
        super(message);
    }

    public KalshiException(String message, Throwable cause) {
        super(message, cause);
    }
}
