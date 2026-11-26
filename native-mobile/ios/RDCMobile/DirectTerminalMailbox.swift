import Foundation
import CryptoKit
import CoreFoundation
import Darwin

/// Developer-connection qualification only. No network listener or URL scheme.
/// The OS-authorized companion container is the transport boundary.
struct DirectTerminalMailbox {
    enum Outcome: String { case completed, alreadyClaimed, refused, outcomeUnknown }
    let documents: URL
    let workspace: URL
    private let fm = FileManager.default

    /// Internal publisher seam for bounded fault verification. No remote control surface.
    struct ReceiptIO {
        let write: (Int32, UnsafeRawPointer, Int) -> Int
        let sync: (Int32) -> Int32
        static let system = ReceiptIO(
            write: { Darwin.write($0, $1, $2) },
            sync: { Darwin.fsync($0) })
    }
    let receiptIO: ReceiptIO
    init(documents: URL, workspace: URL, receiptIO: ReceiptIO = .system) {
        self.documents = documents
        self.workspace = workspace
        self.receiptIO = receiptIO
    }


    private func exists(_ path: URL) -> Bool {
        var value = stat()
        return path.path.withCString { lstat($0, &value) } == 0
    }
    private func digest(_ value: String) -> String {
        SHA256.hash(data: Data(value.utf8)).map { String(format: "%02x", $0) }.joined()
    }
    private func validID(_ id: String) -> Bool {
        UUID(uuidString: id)?.uuidString.lowercased() == id
    }
    private func readRequest(_ path: URL) throws -> Data {
        let fd = path.path.withCString { open($0, O_RDONLY | O_NOFOLLOW | O_NONBLOCK) }
        guard fd >= 0 else { throw CocoaError(.fileReadUnknown) }
        let file = FileHandle(fileDescriptor: fd, closeOnDealloc: true)
        defer { try? file.close() }
        var info = stat()
        guard fstat(fd, &info) == 0, (info.st_mode & S_IFMT) == S_IFREG,
              info.st_size > 0, info.st_size <= 8192 else { throw CocoaError(.fileReadCorruptFile) }
        let data = try file.read(upToCount: 8193) ?? Data()
        guard data.count == Int(info.st_size) else { throw CocoaError(.fileReadCorruptFile) }
        return data
    }
    // An exclusive durable marker fences this UUID before execution.
    // An interrupted or failed publication never permits re-execution.
    private func claim(_ path: URL) -> Outcome? {
        let fd = path.path.withCString { open($0, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, 0o600) }
        if fd < 0 { return errno == EEXIST ? .alreadyClaimed : .refused }
        let synced = fsync(fd) == 0
        _ = close(fd)
        guard synced else { return .outcomeUnknown }
        let directoryFD = documents.path.withCString { open($0, O_RDONLY | O_DIRECTORY | O_NOFOLLOW) }
        guard directoryFD >= 0 else { return .outcomeUnknown }
        let directorySynced = fsync(directoryFD) == 0
        _ = close(directoryFD)
        return directorySynced ? nil : .outcomeUnknown
    }
    // The durable claim survives every publication failure. Never replay a UUID.
    // Only a complete write and successful file/directory sync report completion.
    private func publishReceipt(_ bytes: Data, requestID: String) throws {
        guard !bytes.isEmpty, bytes.count <= 32768, validID(requestID) else {
            throw CocoaError(.fileWriteUnknown)
        }
        let directoryFD = documents.path.withCString {
            open($0, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC)
        }
        guard directoryFD >= 0 else { throw CocoaError(.fileWriteUnknown) }
        defer { _ = close(directoryFD) }
        let name = "rdc-result-" + requestID + ".json"
        var fd = name.withCString {
            openat(directoryFD, $0, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0o600)
        }
        guard fd >= 0 else { throw CocoaError(.fileWriteUnknown) }
        defer { if fd >= 0 { _ = close(fd) } }
        try bytes.withUnsafeBytes { raw in
            guard let start = raw.baseAddress else { throw CocoaError(.fileWriteUnknown) }
            var written = 0
            var attempts = 0
            while written < bytes.count {
                guard attempts < 64 else { throw CocoaError(.fileWriteUnknown) }
                attempts += 1
                let remaining = bytes.count - written
                let count = receiptIO.write(fd, start.advanced(by: written), remaining)
                if count < 0 && errno == EINTR { continue }
                guard count > 0, count <= remaining else { throw CocoaError(.fileWriteUnknown) }
                written += count
            }
        }
        func synchronize(_ descriptor: Int32) throws {
            for _ in 0..<8 {
                if receiptIO.sync(descriptor) == 0 { return }
                if errno != EINTR { break }
            }
            throw CocoaError(.fileWriteUnknown)
        }
        try synchronize(fd)
        let closeResult = close(fd)
        fd = -1 // A close error is uncertain; never close the descriptor again.
        guard closeResult == 0 else { throw CocoaError(.fileWriteUnknown) }
        try synchronize(directoryFD)
    }

    func process(_ id: String) -> Outcome {
        guard validID(id) else { return .refused }
        let request = documents.appendingPathComponent("rdc-request-"+id+".json")
        let result = documents.appendingPathComponent("rdc-result-"+id+".json")
        let marker = documents.appendingPathComponent("rdc-claim-"+id)
        if exists(marker) { return .alreadyClaimed }
        if exists(result) { return .refused }
        guard let attributes = try? fm.attributesOfItem(atPath: documents.path),
              attributes[.type] as? FileAttributeType == .typeDirectory,
              let data = try? readRequest(request),
              let raw = try? JSONSerialization.jsonObject(with: data) as? [String:Any],
              Set(raw.keys) == Set(["schema","request_id","command","command_sha256"]),
              let schema = raw["schema"] as? NSNumber,
              CFGetTypeID(schema) != CFBooleanGetTypeID(), schema.doubleValue == 1,
              raw["request_id"] as? String == id,
              let command = raw["command"] as? String,
              !command.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
              command.utf8.count <= 4000,
              !command.unicodeScalars.contains(where: { CharacterSet.controlCharacters.contains($0) }),
              raw["command_sha256"] as? String == digest(command)
        else { return .refused }
        if let refusal = claim(marker) { return refusal }
        // The claim is persistent; never remove it, even on errors.
        if exists(result) { return .outcomeUnknown }
        let execution = LocalTerminal(root: workspace).execute(command)
        let payload: [String:Any] = ["schema":1,"request_id":id,
            "run_id":execution.runId,"command_sha256":execution.commandDigest,
            "exit_code":execution.exitCode,"device_elapsed_ms":execution.elapsedMs,
            "output":execution.output,"execution_location":"mobile_device"]
        do {
            let bytes = try JSONSerialization.data(withJSONObject: payload)
            guard bytes.count <= 32768 else { return .outcomeUnknown }
            try publishReceipt(bytes, requestID: id)
            return .completed
        } catch { return .outcomeUnknown }
    }
}
