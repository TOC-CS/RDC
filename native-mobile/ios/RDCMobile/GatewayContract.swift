import Foundation

enum GatewayContract {
    enum Invalid: Error { case input }

    static func statusURL(_ input: String) throws -> URL {
        guard input.utf8.count <= 2048,
              var parts = URLComponents(string: input.trimmingCharacters(in: .whitespacesAndNewlines)),
              parts.scheme?.lowercased() == "https",
              let host = parts.host, !host.isEmpty,
              parts.user == nil, parts.password == nil,
              parts.query == nil, parts.fragment == nil,
              parts.percentEncodedPath.isEmpty || parts.percentEncodedPath == "/",
              parts.port.map({ (1...65535).contains($0) }) ?? true else { throw Invalid.input }
        parts.scheme = "https"
        parts.path = "/mobile/status"
        guard let url = parts.url else { throw Invalid.input }
        return url
    }

    static func token(_ input: String) throws -> String {
        let value = input.trimmingCharacters(in: .whitespacesAndNewlines)
        guard input.utf8.count <= 1024,
              (40...1024).contains(value.utf8.count),
              value.utf8.allSatisfy({ (65...90).contains($0) || (97...122).contains($0)
                                      || (48...57).contains($0) || $0 == 45 || $0 == 95 })
        else { throw Invalid.input }
        return value
    }

    struct Status: Decodable {
        let ok: Bool
        let online: Bool
        let pending_operations: Int64

        static func decode(_ data: Data) throws -> Status {
            guard data.count <= 8192 else { throw Invalid.input }
            let status = try JSONDecoder().decode(Self.self, from: data)
            guard status.ok, (0...9_007_199_254_740_991).contains(status.pending_operations)
            else { throw Invalid.input }
            return status
        }
    }
}
