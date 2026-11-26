import Foundation
import CryptoKit
import CoreFoundation
import Darwin

/// Private development companion only: org.tocministries.rdc.warmterminal.
/// No legacy runner, URL scheme, network endpoint, background worker, or shell.
final class WarmTerminalMailbox {
    enum Outcome: String {
        case ready, idle, completed, recovered, deliveryPending
        case refused, stopped, outcomeUnknown
    }
    /// One foreground lifetime. Cancellation is permanent; create a new gate for a new session.
    final class ActivityGate: @unchecked Sendable {
        private let lock = NSLock()
        private var allowed: Bool
        init(active: Bool) { allowed = active }
        var isActive: Bool { lock.lock(); defer { lock.unlock() }; return allowed }
        func cancel() { lock.lock(); allowed = false; lock.unlock() }
    }
    struct Clock {
        let nowMilliseconds: () -> Int64
        let uptime: () -> Double
        static let system = Clock(
            nowMilliseconds: { Int64(Date().timeIntervalSince1970 * 1000) },
            uptime: { ProcessInfo.processInfo.systemUptime })
    }
    /// Internal bounded publication fault seam; never supplied over the wire.
    struct IO {
        let write: (Int32, UnsafeRawPointer, Int) -> Int
        let sync: (Int32) -> Int32
        static let system = IO(write: { Darwin.write($0, $1, $2) },
                               sync: { Darwin.fsync($0) })
    }

    static let bundleID = "org.tocministries.rdc.warmterminal"
    static let maximumClaims = 64
    private static let maximumFrame = 12 * 1024
    private enum Fault: Error { case missing, invalid, exists, io }
    private enum State { case new, active, stopped }
    private struct Request {
        let id: String
        let sequence: Int64
        let expires: Int64
        let command: String
        let commandHash: String
        let requestHash: String
    }

    private let serial = NSLock()
    private let gate: ActivityGate
    private let clock: Clock
    private let io: IO
    private let workspace: URL
    private let sessionID: String
    private let key: SymmetricKey
    private let expires: Int64
    private let initialWall: Int64
    private let initialUptime: Double
    private let monotonicDeadline: Double
    private let documentsFD: Int32
    private let supportFD: Int32
    private let claimsFD: Int32
    private let receiptsFD: Int32
    private let leaseFD: Int32
    private var state = State.new
    private var nextSequence: Int64 = 1
    private var claimCount: Int

    /// support is a private Application Support subdirectory containing owner-provisioned session.json.
    /// documents is this companion's actual Documents directory, never an arbitrary remote path.
    init(documents: URL, support: URL, workspace: URL, sessionID: String,
         gate: ActivityGate, clock: Clock = .system, io: IO = .system) throws {
        guard WarmWire.validID(sessionID) else { throw Fault.invalid }
        var opened: [Int32] = []
        do {
            let docs = try Self.openDirectory(documents, privateDirectory: false); opened.append(docs)
            let support = try Self.openDirectory(support, privateDirectory: true); opened.append(support)
            let provision = try WarmWire.object(Self.read(support, "session.json", limit: 2048, privateFile: true))
            guard Set(provision.keys) == Set(["schema", "session_id", "secret_b64", "expires_at_ms"]),
                  WarmWire.integer(provision["schema"]) == 1,
                  provision["session_id"] as? String == sessionID,
                  let text = provision["secret_b64"] as? String,
                  let secret = Data(base64Encoded: text), secret.count == 32,
                  secret.base64EncodedString() == text,
                  let expiry = WarmWire.integer(provision["expires_at_ms"]) else { throw Fault.invalid }
            let wall = clock.nowMilliseconds(), uptime = clock.uptime()
            guard wall >= 0, wall <= WarmWire.maximumInteger, expiry > wall, expiry - wall <= 600_000,
                  uptime.isFinite, uptime >= 0 else { throw Fault.invalid }

            let lease = "consumer.lock".withCString {
                openat(support, $0, O_RDWR | O_CREAT | O_NOFOLLOW | O_CLOEXEC, 0o600)
            }
            guard lease >= 0 else { throw Fault.io }
            opened.append(lease)
            var info = stat()
            guard fstat(lease, &info) == 0, Self.privateRegular(info),
                  flock(lease, LOCK_EX | LOCK_NB) == 0 else { throw Fault.invalid }
            let claims = try Self.privateChild(support, "claims"); opened.append(claims)
            let receipts = try Self.privateChild(support, "receipts"); opened.append(receipts)
            // One bounded private-ledger scan at initialization; the command loop never scans.
            let count = try Self.countClaims(claims, receipts: receipts)

            self.documentsFD = docs
            self.supportFD = support
            self.claimsFD = claims
            self.receiptsFD = receipts
            self.leaseFD = lease
            self.gate = gate
            self.clock = clock
            self.io = io
            self.workspace = workspace
            self.sessionID = sessionID
            self.key = SymmetricKey(data: secret)
            self.expires = expiry
            self.initialWall = wall
            self.initialUptime = uptime
            self.monotonicDeadline = uptime + Double(expiry - wall) / 1000
            self.claimCount = count
        } catch {
            for fd in opened.reversed() { _ = close(fd) }
            throw Fault.invalid
        }
    }

    deinit {
        for fd in [receiptsFD, claimsFD, leaseFD, supportFD, documentsFD] { _ = close(fd) }
    }

    /// Must be called only once for an explicitly provisioned foreground session.
    func activate() -> Outcome {
        serial.lock(); defer { serial.unlock() }
        guard state == .new else { return end(.refused) }
        guard permitted(), claimCount < Self.maximumClaims else { return end(.refused) }
        do {
            let marker = try WarmWire.canonical(["schema": 1, "session_id": sessionID,
                                                "expires_at_ms": expires, "started_at_ms": initialWall])
            // A durable exclusive marker prevents reuse even after app/process restart.
            try writeExclusive(marker, directory: supportFD, name: "session-\(sessionID).activated")
            guard permitted() else { return end(.stopped) }
            let ready = try WarmWire.canonical([
                "schema": 1, "session_id": sessionID, "expires_at_ms": expires,
                "next_sequence": 1, "status": "ready", "bundle_id": Self.bundleID])
            try publish(WarmWire.seal(ready, domain: WarmWire.readyDomain, key: key),
                        name: "rdc-warm-\(sessionID)-ready.json")
            guard permitted() else { return end(.stopped) }
            state = .active
            return .ready
        } catch { return end(.refused) }
    }

    /// Synchronous serial step. The caller supplies a bounded, cancellable foreground polling loop.
    /// Reads only the next exact inbox filename, including while a previous shared delivery is pending.
    func processNext() -> Outcome {
        serial.lock(); defer { serial.unlock() }
        guard state == .active else { return .stopped }
        guard permitted(), nextSequence <= 64 else { return end(.stopped) }
        let frame: Data
        do { frame = try Self.read(documentsFD, inbox(nextSequence), limit: Self.maximumFrame) }
        catch Fault.missing { return .idle }
        catch { return .refused } // Partial, nonregular, symlink, or oversized shared data never claims.
        let request: Request
        do { request = try decodeRequest(frame) }
        catch { return .refused }

        let claim: Data
        do {
            claim = try WarmWire.canonical([
                "schema": 1, "session_id": sessionID, "request_id": request.id,
                "sequence": request.sequence, "request_sha256": request.requestHash,
                "command_sha256": request.commandHash])
        } catch { return .refused }

        // Claims are global to this companion, independent of session rotation or Documents contents.
        do {
            let existing = try Self.read(claimsFD, claimName(request.id), limit: 2048, privateFile: true)
            guard existing == claim else { return end(.refused) }
            return redeliver(request)
        } catch Fault.missing {
            // No claim exists. Only this path may admit execution.
        } catch { return end(.outcomeUnknown) }

        guard claimCount < Self.maximumClaims else { return end(.refused) }
        guard permitted() else { return end(.stopped) }
        guard clock.nowMilliseconds() < request.expires else { return .refused }
        // An orphan private receipt indicates inconsistent private state. Refuse before any effect.
        do {
            _ = try Self.read(receiptsFD, receiptName(request.id), limit: Self.maximumFrame, privateFile: true)
            return end(.refused)
        } catch Fault.missing {} catch { return end(.outcomeUnknown) }

        do {
            guard permitted(), clock.nowMilliseconds() < request.expires else { return end(.stopped) }
            // This marker and its containing directory are durable before LocalTerminal is reached.
            try writeExclusive(claim, directory: claimsFD, name: claimName(request.id))
            claimCount += 1
        } catch { return end(.outcomeUnknown) }
        guard permitted(), clock.nowMilliseconds() < request.expires else { return end(.outcomeUnknown) }

        let execution = LocalTerminal(root: workspace).execute(request.command)
        guard execution.commandDigest == request.commandHash, WarmWire.validID(execution.runId),
              execution.exitCode == 0 || execution.exitCode == 1,
              execution.elapsedMs.isFinite, execution.elapsedMs >= 0, execution.elapsedMs < 30_000,
              execution.output.utf8.count <= 4096, WarmWire.validOutput(execution.output) else {
            return end(.outcomeUnknown)
        }
        do {
            // Device timing is truncated to whole milliseconds; end-to-end host timing remains separate.
            let result = try WarmWire.canonical([
                "schema": 1, "session_id": sessionID, "request_id": request.id,
                "sequence": request.sequence, "request_sha256": request.requestHash,
                "run_id": execution.runId, "command_sha256": execution.commandDigest,
                "exit_code": execution.exitCode, "device_elapsed_ms": Int(execution.elapsedMs),
                "output": execution.output, "execution_location": "mobile_device"])
            let receipt = try WarmWire.seal(result, domain: WarmWire.receiptDomain, key: key)
            // Authoritative create-only private result must sync before any shared output is published.
            try writeExclusive(receipt, directory: receiptsFD, name: receiptName(request.id))
            guard permitted() else { return end(.outcomeUnknown) }
            do {
                try publish(receipt, name: outbox(request.sequence))
                nextSequence += 1
                return .completed
            } catch {
                // Execution is known and its private receipt is durable. Keep this sequence for redelivery.
                return .deliveryPending
            }
        } catch { return end(.outcomeUnknown) }
    }

    /// The owner of the foreground task must call this on inactive/background, disappearance, or cancellation.
    /// It changes the gate immediately even if a serial step is currently finishing a private receipt.
    func stop() { gate.cancel() }

    private func end(_ outcome: Outcome) -> Outcome {
        state = .stopped
        gate.cancel()
        return outcome
    }
    private func permitted() -> Bool {
        let wall = clock.nowMilliseconds(), up = clock.uptime()
        return gate.isActive && wall >= initialWall && wall < expires
            && up.isFinite && up >= initialUptime && up < monotonicDeadline
    }
    private func inbox(_ sequence: Int64) -> String { "rdc-warm-\(sessionID)-in-\(sequence).json" }
    private func outbox(_ sequence: Int64) -> String { "rdc-warm-\(sessionID)-out-\(sequence).json" }
    private func claimName(_ id: String) -> String { "claim-\(id).json" }
    private func receiptName(_ id: String) -> String { "receipt-\(id).json" }

    private func decodeRequest(_ bytes: Data) throws -> Request {
        let payload = try WarmWire.unseal(bytes, domain: WarmWire.requestDomain, key: key)
        let body = try WarmWire.object(payload)
        guard Set(body.keys) == Set(["schema", "session_id", "request_id", "sequence",
                                    "expires_at_ms", "command", "command_sha256"]),
              WarmWire.integer(body["schema"]) == 1,
              body["session_id"] as? String == sessionID,
              let id = body["request_id"] as? String, WarmWire.validID(id),
              let sequence = WarmWire.integer(body["sequence"]), (1...64).contains(sequence),
              sequence == nextSequence,
              let expiry = WarmWire.integer(body["expires_at_ms"]), expiry <= expires,
              let command = body["command"] as? String, !command.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
              command.utf8.count <= 4000, WarmWire.validCommand(command),
              let commandHash = body["command_sha256"] as? String,
              WarmWire.digest(Data(command.utf8)) == commandHash else { throw Fault.invalid }
        return Request(id: id, sequence: sequence, expires: expiry, command: command,
                       commandHash: commandHash, requestHash: WarmWire.digest(payload))
    }

    private func redeliver(_ request: Request) -> Outcome {
        do {
            let receipt = try Self.read(receiptsFD, receiptName(request.id),
                                        limit: Self.maximumFrame, privateFile: true)
            let body = try WarmWire.object(WarmWire.unseal(receipt, domain: WarmWire.receiptDomain, key: key))
            guard Set(body.keys) == Set(["schema", "session_id", "request_id", "sequence", "request_sha256",
                                        "run_id", "command_sha256", "exit_code", "device_elapsed_ms",
                                        "output", "execution_location"]),
                  WarmWire.integer(body["schema"]) == 1,
                  body["session_id"] as? String == sessionID, body["request_id"] as? String == request.id,
                  WarmWire.integer(body["sequence"]) == request.sequence,
                  body["request_sha256"] as? String == request.requestHash,
                  body["command_sha256"] as? String == request.commandHash,
                  let run = body["run_id"] as? String, WarmWire.validID(run),
                  let exitCode = WarmWire.integer(body["exit_code"]), exitCode <= 1,
                  let elapsed = WarmWire.integer(body["device_elapsed_ms"]), elapsed < 30_000,
                  let output = body["output"] as? String, output.utf8.count <= 4096, WarmWire.validOutput(output),
                  body["execution_location"] as? String == "mobile_device" else { return end(.outcomeUnknown) }
            guard permitted() else { return end(.stopped) }
            do {
                try publish(receipt, name: outbox(request.sequence))
                nextSequence += 1
                return .recovered
            } catch { return .deliveryPending }
        } catch { return end(.outcomeUnknown) }
    }

    private static func privateRegular(_ info: stat) -> Bool {
        (info.st_mode & S_IFMT) == S_IFREG && info.st_uid == getuid()
            && info.st_mode & 0o077 == 0 && info.st_nlink == 1
    }
    private static func openDirectory(_ url: URL, privateDirectory: Bool) throws -> Int32 {
        let fd = url.path.withCString { open($0, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC) }
        guard fd >= 0 else { throw Fault.io }
        var info = stat()
        guard fstat(fd, &info) == 0, (info.st_mode & S_IFMT) == S_IFDIR, info.st_uid == getuid(),
              !privateDirectory || info.st_mode & 0o077 == 0 else { _ = close(fd); throw Fault.invalid }
        return fd
    }
    private static func privateChild(_ parent: Int32, _ name: String) throws -> Int32 {
        let made = name.withCString { mkdirat(parent, $0, 0o700) }
        guard made == 0 || errno == EEXIST else { throw Fault.io }
        let fd = name.withCString { openat(parent, $0, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC) }
        guard fd >= 0 else { throw Fault.io }
        var info = stat()
        guard fstat(fd, &info) == 0, (info.st_mode & S_IFMT) == S_IFDIR,
              info.st_uid == getuid(), info.st_mode & 0o077 == 0, fsync(parent) == 0 else {
            _ = close(fd); throw Fault.invalid
        }
        return fd
    }
    private static func read(_ directory: Int32, _ name: String, limit: Int,
                             privateFile: Bool = false) throws -> Data {
        let fd = name.withCString { openat(directory, $0, O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC) }
        guard fd >= 0 else { throw errno == ENOENT ? Fault.missing : Fault.invalid }
        let file = FileHandle(fileDescriptor: fd, closeOnDealloc: true)
        defer { try? file.close() }
        var info = stat()
        guard fstat(fd, &info) == 0, (info.st_mode & S_IFMT) == S_IFREG,
              info.st_size > 0, info.st_size <= Int64(limit),
              !privateFile || privateRegular(info) else { throw Fault.invalid }
        let bytes = try file.read(upToCount: limit + 1) ?? Data()
        var after = stat()
        guard bytes.count == Int(info.st_size), fstat(fd, &after) == 0,
              after.st_size == info.st_size else { throw Fault.invalid }
        return bytes
    }
    private static func countClaims(_ directory: Int32, receipts: Int32) throws -> Int {
        let scanFD = ".".withCString { openat(directory, $0, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC) }
        guard scanFD >= 0 else { throw Fault.io }
        guard let scan = fdopendir(scanFD) else { _ = close(scanFD); throw Fault.io }
        defer { _ = closedir(scan) }
        var count = 0
        while true {
            errno = 0
            guard let entry = readdir(scan) else {
                if errno != 0 { throw Fault.io }
                break
            }
            let capacity = MemoryLayout.size(ofValue: entry.pointee.d_name)
            let name = withUnsafePointer(to: &entry.pointee.d_name) {
                $0.withMemoryRebound(to: CChar.self, capacity: capacity) { String(cString: $0) }
            }
            if name == "." || name == ".." { continue }
            count += 1
            guard count <= maximumClaims, name.hasPrefix("claim-"), name.hasSuffix(".json") else { throw Fault.invalid }
            let id = String(name.dropFirst(6).dropLast(5))
            let claim = try WarmWire.object(read(directory, name, limit: 2048, privateFile: true))
            guard WarmWire.validID(id),
                  Set(claim.keys) == Set(["schema", "session_id", "request_id", "sequence",
                                         "request_sha256", "command_sha256"]),
                  WarmWire.integer(claim["schema"]) == 1,
                  claim["request_id"] as? String == id,
                  let session = claim["session_id"] as? String, WarmWire.validID(session),
                  let sequence = WarmWire.integer(claim["sequence"]), (1...64).contains(sequence),
                  let requestHash = claim["request_sha256"] as? String, WarmWire.validDigest(requestHash),
                  let commandHash = claim["command_sha256"] as? String, WarmWire.validDigest(commandHash) else { throw Fault.invalid }
            // A new session cannot evade an earlier unknown effect. Prior session keys may have
            // rotated, so reconcile only complete owner-only private receipts and their exact claim
            // binding. This structural path is never used for shared or incoming transport data.
            let receipt = try WarmWire.privateReceiptBody(
                read(receipts, "receipt-\(id).json", limit: maximumFrame, privateFile: true))
            guard Set(receipt.keys) == Set(["schema", "session_id", "request_id", "sequence", "request_sha256",
                                           "run_id", "command_sha256", "exit_code", "device_elapsed_ms",
                                           "output", "execution_location"]),
                  WarmWire.integer(receipt["schema"]) == 1,
                  receipt["session_id"] as? String == session, receipt["request_id"] as? String == id,
                  WarmWire.integer(receipt["sequence"]) == sequence,
                  receipt["request_sha256"] as? String == requestHash,
                  receipt["command_sha256"] as? String == commandHash,
                  let run = receipt["run_id"] as? String, WarmWire.validID(run),
                  let exitCode = WarmWire.integer(receipt["exit_code"]), exitCode <= 1,
                  let elapsed = WarmWire.integer(receipt["device_elapsed_ms"]), elapsed < 30_000,
                  let output = receipt["output"] as? String, output.utf8.count <= 4096,
                  WarmWire.validOutput(output), receipt["execution_location"] as? String == "mobile_device"
            else { throw Fault.invalid }
        }
        return count
    }

    private func synchronize(_ fd: Int32) throws {
        for _ in 0..<8 {
            if io.sync(fd) == 0 { return }
            if errno != EINTR { break }
        }
        throw Fault.io
    }
    private func writeExclusive(_ bytes: Data, directory: Int32, name: String,
                                syncDirectory: Bool = true) throws {
        guard !bytes.isEmpty, bytes.count <= Self.maximumFrame else { throw Fault.invalid }
        var fd = name.withCString {
            openat(directory, $0, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0o600)
        }
        guard fd >= 0 else { throw errno == EEXIST ? Fault.exists : Fault.io }
        defer { if fd >= 0 { _ = close(fd) } }
        try bytes.withUnsafeBytes { raw in
            guard let start = raw.baseAddress else { throw Fault.io }
            var position = 0, attempts = 0
            while position < bytes.count {
                guard attempts < 64 else { throw Fault.io }
                attempts += 1
                let count = io.write(fd, start.advanced(by: position), bytes.count - position)
                if count < 0 && errno == EINTR { continue }
                guard count > 0, count <= bytes.count - position else { throw Fault.io }
                position += count
            }
        }
        try synchronize(fd)
        let result = close(fd)
        fd = -1
        guard result == 0 else { throw Fault.io }
        if syncDirectory { try synchronize(directory) }
    }
    private func publish(_ bytes: Data, name: String) throws {
        let temporary = name + ".pending"
        // Only a transport staging leaf may be removed. Private claims/results are never replaced or deleted.
        let removed = temporary.withCString { unlinkat(documentsFD, $0, 0) }
        guard removed == 0 || errno == ENOENT else { throw Fault.io }
        defer { _ = temporary.withCString { unlinkat(documentsFD, $0, 0) } }
        try writeExclusive(bytes, directory: documentsFD, name: temporary, syncDirectory: false)
        let moved = temporary.withCString { from in
            name.withCString { to in renameat(documentsFD, from, documentsFD, to) }
        }
        guard moved == 0 else { throw Fault.io }
        try synchronize(documentsFD)
    }
}

/// Exact-byte authenticated codec. Only ASCII field names are used by the wire schemas.
private enum WarmWire {
    static let maximumInteger: Int64 = 9_007_199_254_740_991
    static let requestDomain = Data("RDC-WARM-REQUEST-v1\0".utf8)
    static let receiptDomain = Data("RDC-WARM-RECEIPT-v1\0".utf8)
    static let readyDomain = Data("RDC-WARM-READY-v1\0".utf8)
    private enum Invalid: Error { case frame }
    static func validID(_ value: String) -> Bool { UUID(uuidString: value)?.uuidString.lowercased() == value }
    static func validDigest(_ value: String) -> Bool {
        let bytes = value.utf8
        return bytes.count == 64 && bytes.allSatisfy { (48...57).contains($0) || (97...102).contains($0) }
    }
    static func integer(_ value: Any?) -> Int64? {
        guard let number = value as? NSNumber, CFGetTypeID(number) != CFBooleanGetTypeID() else { return nil }
        let type = String(cString: number.objCType)
        guard type != "f", type != "d" else { return nil }
        let result = number.int64Value
        return result >= 0 && result <= maximumInteger && number.doubleValue == Double(result) ? result : nil
    }
    static func validCommand(_ value: String) -> Bool {
        !value.unicodeScalars.contains { $0.value <= 31 || (127...159).contains($0.value) }
    }
    static func validOutput(_ value: String) -> Bool {
        !value.unicodeScalars.contains {
            ($0.value <= 31 || (127...159).contains($0.value)) && $0.value != 9 && $0.value != 10
        }
    }
    static func digest(_ bytes: Data) -> String {
        SHA256.hash(data: bytes).map { String(format: "%02x", $0) }.joined()
    }
    static func canonical(_ object: [String: Any]) throws -> Data {
        try JSONSerialization.data(withJSONObject: object, options: [.sortedKeys, .withoutEscapingSlashes])
    }
    static func object(_ bytes: Data) throws -> [String: Any] {
        guard !bytes.isEmpty, bytes.count <= 12 * 1024,
              let object = try JSONSerialization.jsonObject(with: bytes) as? [String: Any],
              try canonical(object) == bytes else { throw Invalid.frame }
        return object
    }
    static func seal(_ payload: Data, domain: Data, key: SymmetricKey) throws -> Data {
        let mac = HMAC<SHA256>.authenticationCode(for: domain + payload, using: key)
        let result = try canonical([
            "schema": 1, "payload_b64": payload.base64EncodedString(),
            "mac": mac.map { String(format: "%02x", $0) }.joined()])
        guard result.count <= 12 * 1024 else { throw Invalid.frame }
        return result
    }
    /// Structural reconciliation only for a regular owner-only file read from private receipts/.
    /// It cannot authenticate shared data and must never replace unseal() on a transport path.
    static func privateReceiptBody(_ frame: Data) throws -> [String: Any] {
        let envelope = try object(frame)
        guard Set(envelope.keys) == Set(["schema", "payload_b64", "mac"]),
              integer(envelope["schema"]) == 1,
              let encoded = envelope["payload_b64"] as? String,
              let payload = Data(base64Encoded: encoded), !payload.isEmpty, payload.count <= 12 * 1024,
              payload.base64EncodedString() == encoded,
              let text = envelope["mac"] as? String, validDigest(text) else { throw Invalid.frame }
        return try object(payload)
    }
    static func unseal(_ frame: Data, domain: Data, key: SymmetricKey) throws -> Data {
        let envelope = try object(frame)
        guard Set(envelope.keys) == Set(["schema", "payload_b64", "mac"]),
              integer(envelope["schema"]) == 1,
              let encoded = envelope["payload_b64"] as? String,
              let payload = Data(base64Encoded: encoded), !payload.isEmpty, payload.count <= 12 * 1024,
              payload.base64EncodedString() == encoded,
              let text = envelope["mac"] as? String, validDigest(text) else { throw Invalid.frame }
        var mac = Data()
        let characters = Array(text.utf8)
        func nibble(_ value: UInt8) -> UInt8 { value <= 57 ? value - 48 : value - 87 }
        for index in stride(from: 0, to: 64, by: 2) {
            mac.append(nibble(characters[index]) * 16 + nibble(characters[index + 1]))
        }
        guard HMAC<SHA256>.isValidAuthenticationCode(mac, authenticating: domain + payload, using: key) else {
            throw Invalid.frame
        }
        return payload
    }
}
