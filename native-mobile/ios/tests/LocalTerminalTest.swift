import Foundation

@main struct LocalTerminalTest {
    static func main() throws {
        let temp = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: temp, withIntermediateDirectories: false)
        defer { try? FileManager.default.removeItem(at: temp) }
        let root = temp.appendingPathComponent("workspace")
        let terminal = LocalTerminal(root: root)
        var count = 0
        func check(_ label: String, _ condition: @autoclosure () -> Bool) {
            count += 1
            precondition(condition(), label)
            print("PASS \(label)")
        }
        check("virtual cwd", terminal.execute("pwd").output == "/workspace")
        check("literal echo", terminal.execute("echo a; b").output == "a; b")
        check("mkdir", terminal.execute("mkdir sub").exitCode == 0)
        check("write", terminal.execute("write sub/test.txt abc").exitCode == 0)
        check("read", terminal.execute("cat sub/test.txt").output == "abc")
        check("hash", terminal.execute("sha256 sub/test.txt").output == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
        check("no overwrite", terminal.execute("write sub/test.txt replacement").exitCode != 0)
        check("traversal", terminal.execute("cat ../outside").exitCode != 0)
        let outside = temp.appendingPathComponent("outside")
        try Data("outside".utf8).write(to: outside)
        try FileManager.default.createSymbolicLink(at: root.appendingPathComponent("link"), withDestinationURL: outside)
        check("symlink refused", terminal.execute("cat link").exitCode != 0)
        check("unsupported shell", terminal.execute("sh -c id").exitCode != 0)
        check("bounded input", terminal.execute("echo "+String(repeating: "x",count: 4096)).exitCode != 0)
        check("listing", terminal.execute("ls sub").output == "test.txt")
        print("LOCAL_TERMINAL_CASES=\(count)")
    }
}
