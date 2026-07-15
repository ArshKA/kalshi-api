package com.javifalces.kalshi.util;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.GeneralSecurityException;
import java.security.KeyFactory;
import java.security.PrivateKey;
import java.security.spec.PKCS8EncodedKeySpec;
import java.util.Base64;

public final class PemUtils {
    private PemUtils() {}

    public static PrivateKey readPrivateKey(Path path) {
        try {
            String pem = Files.readString(path)
                    .replace("-----BEGIN PRIVATE KEY-----", "")
                    .replace("-----END PRIVATE KEY-----", "")
                    .replaceAll("\\s+", "");
            byte[] encoded = Base64.getDecoder().decode(pem);
            return KeyFactory.getInstance("RSA").generatePrivate(new PKCS8EncodedKeySpec(encoded));
        } catch (IOException | GeneralSecurityException e) {
            throw new IllegalArgumentException("Unable to read PKCS#8 RSA private key from " + path, e);
        }
    }
}
