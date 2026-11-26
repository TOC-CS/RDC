import Foundation
import SwiftUI

struct LocalTerminalView: View {
    let onBack: () -> Void
    @Environment(\.scenePhase) private var phase
    @State private var input = ""
    @State private var receiptHeader = ""
    @State private var output = "Device-local sandbox. Type help."
    @FocusState private var commandFocused: Bool
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
                        .focused($commandFocused)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .font(.system(.body, design: .monospaced))
                    Button("Run local command", action: run)
                        .disabled(busy || input.isEmpty)
                    Button("Clear output") { receiptHeader = ""; output = "Output cleared."; input = ""; commandFocused = false }
                        .disabled(busy)
                }
                Section("Result") {
                    // Keep the bounded execution identity distinct from output
                    // and editable values. Do not make the receipt a text view.
                    if !receiptHeader.isEmpty {
                        Text(receiptHeader)
                            .font(.system(.footnote, design: .monospaced))
                            .accessibilityLabel(Text(receiptHeader))
                            .accessibilityIdentifier("rdc-terminal-receipt")
                    }
                    Text(output)
                        .font(.system(.footnote, design: .monospaced))
                        .accessibilityLabel(Text(output))
                        .accessibilityIdentifier("rdc-terminal-output")
                }
            }
            .navigationTitle("Local terminal")
            .toolbar { ToolbarItem(placement: .navigationBarLeading) {
                Button("Gateway status", action: onBack).disabled(busy)
            } }
        }
        .onChange(of: phase) { value in
            if value != .active { generation = UUID(); input = ""; receiptHeader = ""; output = "Output cleared."; commandFocused = false }
        }
    }

    private func run() {
        guard !busy, !input.isEmpty else { return }
        let command = input
        commandFocused = false
        input = ""
        busy = true
        receiptHeader = ""
        output = "Running on this device…"
        let id = UUID()
        generation = id
        Task {
            let result = await Task.detached(priority: .userInitiated) {
                let documents = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
                // Application Support is created by Foundation inside this application's container.
                do {
                    try FileManager.default.createDirectory(at: documents, withIntermediateDirectories: true)
                    let result = LocalTerminal(root: documents.appendingPathComponent("RDCWorkspace", isDirectory: true)).execute(command)
                    return (result.header, result.output)
                } catch {
                    return ("", "Workspace unavailable.")
                }
            }.value
            busy = false
            guard generation == id else { return }
            receiptHeader = result.0
            output = result.1
        }
    }
}
