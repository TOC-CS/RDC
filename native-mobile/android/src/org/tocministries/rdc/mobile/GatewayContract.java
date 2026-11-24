package org.tocministries.rdc.mobile;
import java.net.URI;

/** Strict gateway origin and read-only bearer validation. */
public final class GatewayContract {
    private GatewayContract() {}
    public static URI statusUri(String input) {
        if (input == null || input.length() > 2048) throw new IllegalArgumentException();
        URI uri = URI.create(input.trim());
        String path = uri.getRawPath();
        int port = uri.getPort();
        if (!"https".equalsIgnoreCase(uri.getScheme()) || uri.getHost() == null
                || uri.getHost().isEmpty() || uri.getRawUserInfo() != null
                || uri.getRawQuery() != null || uri.getRawFragment() != null
                || (port != -1 && (port < 1 || port > 65535))
                || !(path == null || path.isEmpty() || "/".equals(path))) {
            throw new IllegalArgumentException();
        }
        return URI.create("https://" + uri.getRawAuthority() + "/mobile/status");
    }
    public static String token(String input) {
        if (input == null || input.length() > 1024) throw new IllegalArgumentException();
        String value = input.trim();
        if (!value.matches("[A-Za-z0-9_-]{40,1024}")) throw new IllegalArgumentException();
        return value;
    }
}
