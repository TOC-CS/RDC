import Foundation
import CryptoKit
import Darwin

private enum TestWire {
    static let session = "11111111-1111-4111-8111-111111111111"
    static let otherSession = "33333333-3333-4333-8333-333333333333"
    static let key = Data(repeating: 0x42, count: 32)
    static let requestDomain = Data("RDC-WARM-REQUEST-v1\0".utf8)
    static let receiptDomain = Data("RDC-WARM-RECEIPT-v1\0".utf8)
    static let readyDomain = Data("RDC-WARM-READY-v1\0".utf8)
    static func id(_ number: Int = 1) -> String {
        String(format: "22222222-2222-4222-8222-%012d", number)
    }
    static func json(_ object: [String: Any]) throws -> Data {
        try JSONSerialization.data(withJSONObject: object, options: [.sortedKeys, .withoutEscapingSlashes])
    }
    static func object(_ bytes: Data) throws -> [String: Any] {
        guard let value = try JSONSerialization.jsonObject(with: bytes) as? [String: Any] else {
            throw CocoaError(.fileReadCorruptFile)
        }
        return value
    }
    static func hash(_ bytes: Data) -> String {
        SHA256.hash(data: bytes).map { String(format: "%02x", $0) }.joined()
    }
    static func pack(_ payload: Data, domain: Data = requestDomain) throws -> Data {
        let mac = HMAC<SHA256>.authenticationCode(for: domain + payload, using: SymmetricKey(data: key))
        return try json(["schema": 1, "payload_b64": payload.base64EncodedString(),
                         "mac": mac.map { String(format: "%02x", $0) }.joined()])
    }
    static func unpack(_ bytes: Data, domain: Data) throws -> [String: Any] {
        let outer = try object(bytes)
        guard try json(outer) == bytes, let b64 = outer["payload_b64"] as? String,
              let payload = Data(base64Encoded: b64),
              let text = outer["mac"] as? String, text.count == 64 else {
            throw CocoaError(.fileReadCorruptFile)
        }
        var mac = Data()
        var index = text.startIndex
        for _ in 0..<32 {
            let end = text.index(index, offsetBy: 2)
            guard let byte = UInt8(text[index..<end], radix: 16) else { throw CocoaError(.fileReadCorruptFile) }
            mac.append(byte); index = end
        }
        guard HMAC<SHA256>.isValidAuthenticationCode(mac, authenticating: domain + payload,
                                                     using: SymmetricKey(data: key)) else {
            throw CocoaError(.fileReadCorruptFile)
        }
        return try object(payload)
    }
}

private final class TestTime {
    var wall: Int64 = 1_800_000_000_000
    var uptime = 100.0
    var clock: WarmTerminalMailbox.Clock {
        .init(nowMilliseconds: { self.wall }, uptime: { self.uptime })
    }
}

private final class Fixture {
    let root: URL
    let documents: URL
    let support: URL
    let workspace: URL
    let time = TestTime()
    let gate = WarmTerminalMailbox.ActivityGate(active: true)
    var sessionID = TestWire.session
    let fm = FileManager.default
    init(_ name: String, under parent: URL) throws {
        root = parent.appendingPathComponent(name, isDirectory: true)
        documents = root.appendingPathComponent("Documents", isDirectory: true)
        support = root.appendingPathComponent("Support", isDirectory: true)
        workspace = support.appendingPathComponent("RDCWorkspace", isDirectory: true)
        for directory in [root, documents, support] {
            try fm.createDirectory(at: directory, withIntermediateDirectories: false,
                                   attributes: [.posixPermissions: 0o700])
        }
        try provision()
    }
    func provision() throws {
        let bytes = try TestWire.json(["schema": 1, "session_id": sessionID,
                                      "secret_b64": TestWire.key.base64EncodedString(),
                                      "expires_at_ms": time.wall + 60_000])
        try bytes.write(to: support.appendingPathComponent("session.json"))
        try fm.setAttributes([.posixPermissions: 0o600],
                             ofItemAtPath: support.appendingPathComponent("session.json").path)
    }
    func make(io: WarmTerminalMailbox.IO = .system,
              gate selectedGate: WarmTerminalMailbox.ActivityGate? = nil) throws -> WarmTerminalMailbox {
        try WarmTerminalMailbox(documents: documents, support: support, workspace: workspace,
                                sessionID: sessionID, gate: selectedGate ?? gate, clock: time.clock, io: io)
    }
    func body(_ command: String = "echo fixture", id: String = TestWire.id(),
              sequence: Int64 = 1, override: [String: Any] = [:]) -> [String: Any] {
        var object: [String: Any] = [
            "schema": 1, "session_id": sessionID, "request_id": id, "sequence": sequence,
            "expires_at_ms": time.wall + 30_000, "command": command,
            "command_sha256": TestWire.hash(Data(command.utf8))]
        for (key, value) in override { object[key] = value }
        return object
    }
    func input(_ sequence: Int64 = 1) -> URL {
        documents.appendingPathComponent("rdc-warm-\(sessionID)-in-\(sequence).json")
    }
    func output(_ sequence: Int64 = 1) -> URL {
        documents.appendingPathComponent("rdc-warm-\(sessionID)-out-\(sequence).json")
    }
    func put(_ body: [String: Any], fileSequence: Int64 = 1) throws {
        try TestWire.pack(TestWire.json(body)).write(to: input(fileSequence))
    }
    func receipt(_ sequence: Int64 = 1) throws -> [String: Any] {
        try TestWire.unpack(Data(contentsOf: output(sequence)), domain: TestWire.receiptDomain)
    }
    var claimCount: Int {
        (try? fm.contentsOfDirectory(atPath: support.appendingPathComponent("claims").path).count) ?? 0
    }
    var hasWorkspace: Bool { fm.fileExists(atPath: workspace.path) }
}

@main struct WarmTerminalTest {
    static func main() throws {
        let fm = FileManager.default
        let root = fm.temporaryDirectory.appendingPathComponent("rdc-warm-draft-tests-\(getpid())", isDirectory: true)
        try fm.createDirectory(at: root, withIntermediateDirectories: false, attributes: [.posixPermissions: 0o700])
        defer { try? fm.removeItem(at: root) }

        if CommandLine.arguments.dropFirst().first == "--activation-red" {
            let f = try Fixture("activation-red", under: root)
            let box = try f.make()
            let result = box.activate()
            let untouched = try fm.contentsOfDirectory(atPath: f.documents.path).isEmpty
                && fm.contentsOfDirectory(atPath: f.support.path) == ["session.json"]
                && !f.hasWorkspace
            if result != .ready {
                print(untouched ? "CHECK FAIL activation_valid_session_expected_ready_no_effects" :
                                  "CHECK FAIL activation_refused_with_unexpected_effects")
                print("{\"checks\":1,\"passed\":0,\"failed\":1}")
                exit(1)
            }
            print("CHECK PASS activation_valid_session_expected_ready")
            print("{\"checks\":1,\"passed\":1,\"failed\":0}")
            return
        }

        var checks = 0
        func check(_ label: String, _ operation: () throws -> Bool) {
            checks += 1
            do {
                guard try operation() else { throw CocoaError(.fileReadCorruptFile) }
                print("CHECK PASS \(label)")
            } catch {
                print("CHECK FAIL \(label)")
                print("{\"checks\":\(checks),\"passed\":\(checks - 1),\"failed\":1}")
                exit(1)
            }
        }

        check("authenticated_activation_and_exact_result") {
            let f = try Fixture("01", under: root); let box = try f.make()
            guard box.activate() == .ready else { return false }
            let ready = try TestWire.unpack(Data(contentsOf: f.documents.appendingPathComponent("rdc-warm-\(f.sessionID)-ready.json")),
                                           domain: TestWire.readyDomain)
            let body = f.body("echo fixture / café")
            try f.put(body)
            guard box.processNext() == .completed else { return false }
            let receipt = try f.receipt()
            let expectedRequestDigest = TestWire.hash(try TestWire.json(body))
            return ready["bundle_id"] as? String == "org.tocministries.rdc.warmterminal"
                && receipt["output"] as? String == "fixture / café"
                && receipt["request_sha256"] as? String == expectedRequestDigest
                && receipt["session_id"] as? String == f.sessionID
                && f.claimCount == 1
        }
        check("altered_mac_cannot_claim") {
            let f = try Fixture("02", under: root); let box = try f.make()
            guard box.activate() == .ready else { return false }
            var outer = try TestWire.object(TestWire.pack(TestWire.json(f.body("write forbidden.txt value"))))
            outer["mac"] = String(repeating: "0", count: 64)
            try TestWire.json(outer).write(to: f.input())
            return box.processNext() == .refused && f.claimCount == 0 && !f.hasWorkspace
        }
        check("new_session_cannot_evade_claim_without_private_receipt") {
            let f = try Fixture("03", under: root)
            var syncs = 0
            let io = WarmTerminalMailbox.IO(write: { Darwin.write($0, $1, $2) }, sync: { fd in
                syncs += 1
                let result = Darwin.fsync(fd)
                if syncs == 6 { f.gate.cancel() }
                return result
            })
            var first: WarmTerminalMailbox? = try f.make(io: io)
            guard first?.activate() == .ready else { return false }
            try f.put(f.body("write absent.txt value"))
            guard first?.processNext() == .outcomeUnknown else { return false }
            first = nil
            f.sessionID = TestWire.otherSession
            try f.provision()
            do {
                let second = try f.make(gate: .init(active: true))
                return second.activate() == .refused && second.processNext() == .stopped
                    && f.claimCount == 1 && !f.hasWorkspace
            } catch {
                return f.claimCount == 1 && !f.hasWorkspace
            }
        }
        check("authenticated_noncanonical_body_cannot_claim") {
            let f = try Fixture("04", under: root); let box = try f.make()
            guard box.activate() == .ready else { return false }
            let raw = Data(" ".utf8) + (try TestWire.json(f.body()))
            try TestWire.pack(raw).write(to: f.input())
            return box.processNext() == .refused && f.claimCount == 0
        }
        check("wrong_session_cannot_claim") {
            let f = try Fixture("05", under: root); let box = try f.make()
            guard box.activate() == .ready else { return false }
            try f.put(f.body(override: ["session_id": TestWire.otherSession]))
            return box.processNext() == .refused && f.claimCount == 0
        }
        check("expired_request_cannot_claim") {
            let f = try Fixture("06", under: root); let box = try f.make()
            guard box.activate() == .ready else { return false }
            try f.put(f.body(override: ["expires_at_ms": f.time.wall]))
            return box.processNext() == .refused && f.claimCount == 0
        }
        check("future_sequence_cannot_skip") {
            let f = try Fixture("07", under: root); let box = try f.make()
            guard box.activate() == .ready else { return false }
            try f.put(f.body(sequence: 2), fileSequence: 1)
            return box.processNext() == .refused && f.claimCount == 0
        }
        check("command_utf8_limit_cannot_claim") {
            let f = try Fixture("08", under: root); let box = try f.make()
            guard box.activate() == .ready else { return false }
            try f.put(f.body("echo " + String(repeating: "é", count: 2000)))
            return box.processNext() == .refused && f.claimCount == 0
        }
        check("global_claim_survives_session_rotation") {
            let f = try Fixture("09", under: root)
            var first: WarmTerminalMailbox? = try f.make()
            guard first?.activate() == .ready else { return false }
            try f.put(f.body("write once.txt original"))
            guard first?.processNext() == .completed else { return false }
            first = nil
            f.sessionID = TestWire.otherSession
            try f.provision()
            let second = try f.make(gate: .init(active: true))
            guard second.activate() == .ready else { return false }
            try f.put(f.body("write once.txt replacement"))
            let result = second.processNext()
            let original = try String(contentsOf: f.workspace.appendingPathComponent("once.txt"), encoding: .utf8)
            return result == .refused && original == "original" && f.claimCount == 1
        }
        check("activated_session_cannot_restart") {
            let f = try Fixture("10", under: root)
            var first: WarmTerminalMailbox? = try f.make()
            guard first?.activate() == .ready else { return false }
            first = nil
            let second = try f.make(gate: .init(active: true))
            return second.activate() == .refused && second.processNext() == .stopped && !f.hasWorkspace
        }
        check("inactive_gate_prevents_claim") {
            let f = try Fixture("11", under: root); let box = try f.make()
            guard box.activate() == .ready else { return false }
            try f.put(f.body("write absent.txt value"))
            f.gate.cancel()
            return box.processNext() == .stopped && f.claimCount == 0 && !f.hasWorkspace
        }
        check("cancel_after_claim_prevents_effect_and_stops") {
            let f = try Fixture("12", under: root)
            var syncs = 0
            let io = WarmTerminalMailbox.IO(write: { Darwin.write($0, $1, $2) }, sync: { fd in
                syncs += 1
                let result = Darwin.fsync(fd)
                if syncs == 6 { f.gate.cancel() }
                return result
            })
            let box = try f.make(io: io)
            guard box.activate() == .ready else { return false }
            try f.put(f.body("write absent.txt value"))
            return box.processNext() == .outcomeUnknown && f.claimCount == 1
                && !f.hasWorkspace && box.processNext() == .stopped
        }
        check("private_receipt_sync_failure_never_reexecutes") {
            let f = try Fixture("13", under: root)
            var syncs = 0
            let io = WarmTerminalMailbox.IO(write: { Darwin.write($0, $1, $2) }, sync: { fd in
                syncs += 1
                if syncs == 7 { errno = EIO; return -1 }
                return Darwin.fsync(fd)
            })
            let box = try f.make(io: io)
            guard box.activate() == .ready else { return false }
            try f.put(f.body("write once.txt original"))
            let result = box.processNext()
            let original = try String(contentsOf: f.workspace.appendingPathComponent("once.txt"), encoding: .utf8)
            return result == .outcomeUnknown && box.processNext() == .stopped
                && original == "original" && f.claimCount == 1 && !fm.fileExists(atPath: f.output().path)
        }
        check("shared_delivery_recovers_private_result_without_execution") {
            let f = try Fixture("14", under: root)
            var syncs = 0
            let io = WarmTerminalMailbox.IO(write: { Darwin.write($0, $1, $2) }, sync: { fd in
                syncs += 1
                if syncs == 9 { errno = EIO; return -1 }
                return Darwin.fsync(fd)
            })
            let box = try f.make(io: io)
            guard box.activate() == .ready else { return false }
            try f.put(f.body("write once.txt original"))
            guard box.processNext() == .deliveryPending, box.processNext() == .recovered else { return false }
            let receipt = try f.receipt()
            let original = try String(contentsOf: f.workspace.appendingPathComponent("once.txt"), encoding: .utf8)
            return receipt["exit_code"] as? Int == 0 && original == "original" && f.claimCount == 1
        }
        check("symlink_request_cannot_claim") {
            let f = try Fixture("15", under: root); let box = try f.make()
            guard box.activate() == .ready else { return false }
            let outside = f.root.appendingPathComponent("outside.json")
            try TestWire.pack(TestWire.json(f.body("write absent.txt value"))).write(to: outside)
            try fm.createSymbolicLink(at: f.input(), withDestinationURL: outside)
            return box.processNext() == .refused && f.claimCount == 0 && !f.hasWorkspace
        }
        check("incomplete_frame_never_claims_then_complete_frame_runs") {
            let f = try Fixture("16", under: root); let box = try f.make()
            guard box.activate() == .ready else { return false }
            let frame = try TestWire.pack(TestWire.json(f.body()))
            try frame.prefix(12).write(to: f.input())
            guard box.processNext() == .refused, f.claimCount == 0 else { return false }
            try frame.write(to: f.input())
            return box.processNext() == .completed && f.claimCount == 1
        }
        print("{\"checks\":\(checks),\"passed\":\(checks),\"failed\":0}")
    }
}
