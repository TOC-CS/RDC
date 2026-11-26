import Foundation
import Darwin

/// One generic cross-language wire case. The Python runner owns the assertion.
@main struct WarmTerminalInterop {
    static func main() throws {
        guard CommandLine.arguments.count == 3 else { exit(2) }
        let vectorBytes = try Data(contentsOf: URL(fileURLWithPath: CommandLine.arguments[1]))
        guard vectorBytes.count < 32_768,
              let vector = try JSONSerialization.jsonObject(with: vectorBytes) as? [String: Any],
              let session = vector["session_id"] as? String,
              let provisionText = vector["provision_b64"] as? String,
              let requestText = vector["request_b64"] as? String,
              let provision = Data(base64Encoded: provisionText),
              let request = Data(base64Encoded: requestText),
              let now = vector["now_ms"] as? Int64 else { exit(2) }
        let fm = FileManager.default
        let root = fm.temporaryDirectory.appendingPathComponent("rdc-warm-interop-\(getpid())")
        let documents = root.appendingPathComponent("Documents")
        let support = root.appendingPathComponent("Support")
        for folder in [root, documents, support] {
            try fm.createDirectory(at: folder, withIntermediateDirectories: false,
                                   attributes: [.posixPermissions: 0o700])
        }
        defer { try? fm.removeItem(at: root) }
        let provisionURL = support.appendingPathComponent("session.json")
        try provision.write(to: provisionURL)
        try fm.setAttributes([.posixPermissions: 0o600], ofItemAtPath: provisionURL.path)
        let box = try WarmTerminalMailbox(documents: documents, support: support,
            workspace: support.appendingPathComponent("RDCWorkspace"), sessionID: session,
            gate: .init(active: true),
            clock: .init(nowMilliseconds: { now }, uptime: { 100.0 }))
        guard box.activate() == .ready else { exit(3) }
        try request.write(to: documents.appendingPathComponent("rdc-warm-\(session)-in-1.json"))
        guard box.processNext() == .completed else { exit(4) }
        let ready = try Data(contentsOf: documents.appendingPathComponent("rdc-warm-\(session)-ready.json"))
        let receipt = try Data(contentsOf: documents.appendingPathComponent("rdc-warm-\(session)-out-1.json"))
        let result = try JSONSerialization.data(withJSONObject: [
            "ready_b64":ready.base64EncodedString(),
            "receipt_b64":receipt.base64EncodedString()
        ], options: [.sortedKeys])
        try result.write(to: URL(fileURLWithPath: CommandLine.arguments[2]), options: .withoutOverwriting)
        print("cross_language_result_created")
    }
}
