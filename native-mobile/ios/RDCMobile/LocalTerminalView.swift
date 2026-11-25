import Foundation
import SwiftUI

struct LocalTerminalView: View {
    let onBack: () -> Void
    @Environment(\.scenePhase) private var phase
    @State private var input = ""
    @State private var receipt = "Device-local sandbox. Type help."
    @State private var busy = false
    @State private var generation = UUID()

    var body: some View {
        NavigationStack {
            Form {
                Section("Execution location") {
                    Text("RDC device-local terminal")
                    Text("This iPhone or iPad only. Files stay inside RDC's private workspace. No unrestricted OS shell or remote SSH.")
                }
                Section("Command") {
                    TextField("Enter local command", text: $input)
                        .accessibilityLabel("RDC local command")
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .font(.system(.body, design: .monospaced))
                    Button("Run local command", action: run)
                        .disabled(busy || input.isEmpty)
                    Button("Clear output") { receipt = "Output cleared."; input = "" }
                        .disabled(busy)
                }
                Section("Result") {
                    Text(receipt).font(.system(.footnote, design: .monospaced))
                        .textSelection(.enabled)
                        .accessibilityLabel(receipt)
                }
            }
            .navigationTitle("Local terminal")
            .toolbar { ToolbarItem(placement: .navigationBarLeading) {
                Button("Gateway status", action: onBack).disabled(busy)
            } }
        }
        .onChange(of: phase) { value in
            if value != .active { generation = UUID(); input = ""; receipt = "Output cleared." }
        }
    }

    private func run() {
        guard !busy, !input.isEmpty else { return }
        let command = input
        input = ""
        busy = true
        receipt = "Running on this device…"
        let id = UUID()
        generation = id
        Task {
            let result = await Task.detached(priority: .userInitiated) {
                let documents = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
                // Application Support is created by Foundation inside this application's container.
                do {
                    try FileManager.default.createDirectory(at: documents, withIntermediateDirectories: true)
                    return LocalTerminal(root: documents.appendingPathComponent("RDCWorkspace", isDirectory: true)).execute(command).receipt
                } catch {
                    return "RDC terminal result | device-local | exit=1 | Workspace unavailable."
                }
            }.value
            busy = false
            guard generation == id else { return }
            receipt = result
        }
    }
}
