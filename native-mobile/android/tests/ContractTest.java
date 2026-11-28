import org.tocministries.rdc.mobile.GatewayContract;
public final class ContractTest {
    private static void reject(String input) {
        try { GatewayContract.statusUri(input); throw new AssertionError("accepted unsafe origin"); }
        catch (IllegalArgumentException expected) {}
    }
    public static void main(String[] args) {
        if (!GatewayContract.statusUri("https://rdc.example:8443/").toString()
                .equals("https://rdc.example:8443/mobile/status")) throw new AssertionError("origin mismatch");
        for (String url : new String[]{"http://rdc.example","https://user@rdc.example",
            "https://rdc.example/path","https://rdc.example/?token=secret",
            "https://rdc.example/#frag","https://rdc.example:0","https://rdc.example:65536",
            "https:///invalid","file:///tmp/x"}) reject(url);
        String token="0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcd";
        if (!GatewayContract.token(token).equals(token)) throw new AssertionError("valid token rejected");
        for(String invalid:new String[]{"","Bearer "+token,token+"\nsecret","a".repeat(1025)}) {
            try { GatewayContract.token(invalid); throw new AssertionError("unsafe token accepted"); }
            catch(IllegalArgumentException expected){}
        }
        System.out.println("Android JVM contract passed.");
    }
}
