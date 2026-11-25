import Foundation
import CryptoKit

/// A bounded command interpreter inside the companion's own private sandbox.
/// No OS shell, subprocess, networking, external file access or evaluation.
struct LocalTerminal {
    struct Result {
        let exitCode: Int
        let output: String
        let elapsedMs: Double
        let runId: String
        let commandDigest: String
        var receipt: String {
            "RDC terminal result | device-local | run=\(runId) | command=\(commandDigest) | exit=\(exitCode) | \(String(format: "%.2f", elapsedMs)) ms\n\(output)"
        }
    }

    private enum Invalid: Error { case input, path, exists, limit, file }
    private static let maximum = 4096
    private let root: URL
    private let fm = FileManager.default

    init(root: URL) { self.root = root.standardizedFileURL }

    private func directory(_ url: URL) throws {
        let attrs = try fm.attributesOfItem(atPath: url.path)
        guard attrs[.type] as? FileAttributeType == .typeDirectory else { throw Invalid.path }
    }
    private func prepare() throws {
        if !fm.fileExists(atPath: root.path) {
            try fm.createDirectory(at: root, withIntermediateDirectories: false, attributes: [.posixPermissions: 0o700])
        }
        try directory(root)
    }
    private func resolve(_ value: String, existing: Bool) throws -> URL {
        let parts = value.split(separator: "/", omittingEmptySubsequences: false)
        guard (1...4).contains(parts.count), parts.allSatisfy({ part in
            part.range(of: #"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$"#, options: .regularExpression) != nil
                && part != "." && part != ".."
        }) else { throw Invalid.path }
        var url = root
        for (index, part) in parts.enumerated() {
            url.appendPathComponent(String(part))
            if index < parts.count - 1 { try directory(url) }
        }
        if existing {
            let attrs = try fm.attributesOfItem(atPath: url.path)
            guard let type = attrs[.type] as? FileAttributeType,
                  type == .typeRegular || type == .typeDirectory else { throw Invalid.path }
        }
        return url
    }
    private func read(_ url: URL) throws -> Data {
        let attrs = try fm.attributesOfItem(atPath: url.path)
        guard attrs[.type] as? FileAttributeType == .typeRegular,
              let size = attrs[.size] as? NSNumber, size.int64Value <= Int64(Self.maximum) else { throw Invalid.limit }
        let file = try FileHandle(forReadingFrom: url)
        defer { try? file.close() }
        let data = try file.read(upToCount: Self.maximum + 1) ?? Data()
        guard data.count <= Self.maximum else { throw Invalid.limit }
        return data
    }
    private func entries(_ url: URL) throws -> String {
        try directory(url)
        let files = try fm.contentsOfDirectory(atPath: url.path)
        guard files.count <= 256 else { throw Invalid.limit }
        let result = files.filter { $0.range(of: #"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$"#, options: .regularExpression) != nil }.sorted().joined(separator: "\n")
        guard result.utf8.count <= Self.maximum else { throw Invalid.limit }
        return result
    }
    func execute(_ input: String) -> Result {
        let start = ProcessInfo.processInfo.systemUptime
        let runId = UUID().uuidString.lowercased()
        let digest = SHA256.hash(data: Data(input.utf8)).map { String(format: "%02x", $0) }.joined()
        func finish(_ code: Int, _ output: String) -> Result {
            Result(exitCode: code, output: output, elapsedMs: (ProcessInfo.processInfo.systemUptime - start) * 1000, runId: runId, commandDigest: digest)
        }
        do {
            guard !input.isEmpty, input.utf8.count <= Self.maximum,
                  !input.unicodeScalars.contains(where: { CharacterSet.controlCharacters.contains($0) }) else { throw Invalid.input }
            let parts = input.split(separator: " ", maxSplits: 2, omittingEmptySubsequences: true).map(String.init)
            guard let command = parts.first else { throw Invalid.input }
            try prepare()
            switch command {
            case "help":
                guard parts.count == 1 else { throw Invalid.input }
                return finish(0, "pwd | ls [folder] | mkdir folder | write file text | cat file | sha256 file | echo text")
            case "pwd":
                guard parts.count == 1 else { throw Invalid.input }
                return finish(0, "/workspace")
            case "echo":
                return finish(0, parts.dropFirst().joined(separator: " "))
            case "ls":
                guard parts.count <= 2 else { throw Invalid.input }
                return finish(0, try entries(parts.count == 1 ? root : resolve(parts[1], existing: true)))
            case "mkdir":
                guard parts.count == 2 else { throw Invalid.input }
                let url = try resolve(parts[1], existing: false)
                try fm.createDirectory(at: url, withIntermediateDirectories: false, attributes: [.posixPermissions: 0o700])
                return finish(0, "Directory created")
            case "write":
                guard parts.count == 3 else { throw Invalid.input }
                let url = try resolve(parts[1], existing: false)
                try Data(parts[2].utf8).write(to: url, options: .withoutOverwriting)
                return finish(0, "File created")
            case "cat", "sha256":
                guard parts.count == 2 else { throw Invalid.input }
                let data = try read(resolve(parts[1], existing: true))
                if command == "sha256" {
                    return finish(0, SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined())
                }
                guard let value = String(data: data, encoding: .utf8) else { throw Invalid.file }
                // Avoid terminal escapes or control characters in output.
                let clean = value.unicodeScalars.filter { !CharacterSet.controlCharacters.contains($0) || $0.value == 10 || $0.value == 9 }
                return finish(0, String(String.UnicodeScalarView(clean)))
            default: throw Invalid.input
            }
        } catch {
            return finish(1, "Command refused or unavailable. Use help; files must be inside /workspace. Existing files are preserved.")
        }
    }
}
