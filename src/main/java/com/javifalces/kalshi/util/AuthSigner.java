package com.javifalces.kalshi.util;

import java.nio.charset.StandardCharsets;
import java.security.GeneralSecurityException;
import java.security.PrivateKey;
import java.security.Signature;
import java.security.spec.MGF1ParameterSpec;
import java.security.spec.PSSParameterSpec;
import java.util.Base64;

public final class AuthSigner {
    private final PrivateKey privateKey;

    public AuthSigner(PrivateKey privateKey) {
        this.privateKey = privateKey;
    }

    public SignedRequest sign(String method, String path, long timestampMillis) {
        String payload = timestampMillis + method + path;
        try {
            Signature signature = Signature.getInstance("RSASSA-PSS");
            signature.setParameter(new PSSParameterSpec("SHA-256", "MGF1", MGF1ParameterSpec.SHA256, 32, 1));
            signature.initSign(privateKey);
            signature.update(payload.getBytes(StandardCharsets.UTF_8));
            return new SignedRequest(Long.toString(timestampMillis), Base64.getEncoder().encodeToString(signature.sign()));
        } catch (GeneralSecurityException e) {
            throw new IllegalStateException("Unable to sign request", e);
        }
    }

    public record SignedRequest(String timestamp, String signature) {}
}
