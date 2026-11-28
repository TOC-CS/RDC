import Foundation

@main struct ContractTest {
    static func main() throws {
        let url = try GatewayContract.statusURL("https://rdc.example:8443/")
        precondition(url.absoluteString == "https://rdc.example:8443/mobile/status")
        for bad in ["http://rdc.example","https://user@rdc.example","https://rdc.example/path","https://rdc.example/?token=secret","https://rdc.example/#frag","https://rdc.example:0","https://rdc.example:65536","https:///invalid","file:///tmp/x"] {
            do { _ = try GatewayContract.statusURL(bad); fatalError("unsafe URL") }
            catch GatewayContract.Invalid.input {}
        }
        let token = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcd"
        let valid = try GatewayContract.token(token)
        precondition(valid == token)
        for bad in ["","Bearer "+token,token+"\nsecret",String(repeating:"a",count:1025)] {
            do { _ = try GatewayContract.token(bad); fatalError("unsafe token") }
            catch GatewayContract.Invalid.input {}
        }
        let receipt = try GatewayContract.Status.decode(Data(#"{"ok":true,"online":false,"pending_operations":4}"#.utf8))
        precondition(!receipt.online && receipt.pending_operations == 4)
        for bad in [#"{"ok":false,"online":true,"pending_operations":4}"#,
                    #"{"ok":true,"online":"true","pending_operations":4}"#,
                    #"{"ok":true,"online":true,"pending_operations":-1}"#,
                    #"{"ok":true,"online":true,"pending_operations":1.5}"#] {
            do { _ = try GatewayContract.Status.decode(Data(bad.utf8)); fatalError("unsafe receipt") }
            catch {}
        }
        print("iOS Swift contract passed.")
    }
}
