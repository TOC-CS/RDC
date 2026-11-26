import Foundation
import SwiftUI

final class NoRedirect: NSObject, URLSessionTaskDelegate, @unchecked Sendable {
    func urlSession(_ session: URLSession, task: URLSessionTask,
                    willPerformHTTPRedirection response: HTTPURLResponse,
                    newRequest request: URLRequest,
                    completionHandler: @escaping (URLRequest?) -> Void) {
        completionHandler(nil)
    }
}

@main struct RDCMobileApp: App {
    @State private var terminal = false
    var body: some Scene {
        WindowGroup {
            #if DEBUG
            if let id = DirectTerminalLaunch.requestID(CommandLine.arguments) {
                DirectTerminalLaunch(requestID: id)
            } else {
                normalView
            }
            #else
            normalView
            #endif
        }
    }
    @ViewBuilder private var normalView: some View {
        if terminal { LocalTerminalView(onBack: { terminal = false }) }
        else { StatusView(onOpenTerminal: { terminal = true }) }
    }
}

#if DEBUG
/// Explicit developer-service launch only; not a public URL or background endpoint.
private struct DirectTerminalLaunch: View {
    let requestID: String
    @State private var status = "Waiting for local developer request"
    @State private var started = false
    static func requestID(_ arguments: [String]) -> String? {
        guard arguments.count == 3, arguments[1] == "--rdc-direct-terminal",
              UUID(uuidString: arguments[2])?.uuidString.lowercased() == arguments[2]
        else { return nil }
        return arguments[2]
    }
    var body: some View {
        VStack(spacing: 12) {
            Text("RDC device-local command")
            Text(status)
        }
        .task {
            guard !started else { return }
            started = true
            let id = requestID
            let result = await Task.detached(priority: .userInitiated) {
                do {
                    let fm = FileManager.default
                    let docs = fm.urls(for: .documentDirectory, in: .userDomainMask)[0]
                    let support = fm.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
                    try fm.createDirectory(at: support, withIntermediateDirectories: true)
                    return DirectTerminalMailbox(documents: docs,
                        workspace: support.appendingPathComponent("RDCWorkspace", isDirectory: true)).process(id)
                } catch {
                    return DirectTerminalMailbox.Outcome.refused
                }
            }.value
            switch result {
            case .completed: status = "Result ready"
            case .alreadyClaimed: status = "Request already claimed; no replay"
            case .refused: status = "Request refused"
            case .outcomeUnknown: status = "Outcome unknown; inspect result without replay"
            }
        }
    }
}
#endif

struct StatusView: View {
    let onOpenTerminal: () -> Void
    @Environment(\.scenePhase) private var phase
    @State private var origin = ""
    @State private var secret = ""
    @State private var message = "Connection not checked."
    @State private var active: Task<Void, Never>?
    @State private var generation = UUID()
    @State private var checking = false

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    Text("Independent gateway companion. Check your host with a read-only status token. This app does not grant control of the phone.")
                    TextField("https://your-rdc-host", text: $origin)
                        .textContentType(.URL)
                        .textInputAutocapitalization(.never)
                        .keyboardType(.URL).autocorrectionDisabled()
                        .accessibilityLabel("Gateway HTTPS origin")
                    SecureField("Read-only mobile status token", text: $secret)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .privacySensitive()
                    Button("Check connection", action: check)
                        .disabled(checking)
                    Button("Clear session", role: .cancel) { clear(true) }
                } header: { Text("Connection") }
                Section("Status") {
                    Text(message).accessibilityLabel("Gateway status: \(message)")
                }
            }
            .navigationTitle("RDC Mobile")
            .toolbar { Button("Local terminal", action: onOpenTerminal) }
        }
        .onChange(of: phase) { value in
            if value != .active { clear(false) }
        }
        .onDisappear { clear(true) }
    }

    @MainActor private func clear(_ clearOrigin: Bool) {
        generation = UUID()
        active?.cancel()
        active = nil
        checking = false
        secret = ""
        if clearOrigin { origin = "" }
        message = "Connection not checked."
    }

    @MainActor private func check() {
        guard !checking else { return }
        let raw = secret
        secret = ""
        guard let url = try? GatewayContract.statusURL(origin),
              let token = try? GatewayContract.token(raw) else {
            message = "Enter a trusted HTTPS gateway origin and a valid read-only token."
            return
        }
        let id = UUID()
        generation = id
        checking = true
        message = "Checking your gateway…"
        active = Task {
            let config = URLSessionConfiguration.ephemeral
            config.httpCookieStorage = nil
            config.httpShouldSetCookies = false
            config.urlCredentialStorage = nil
            config.urlCache = nil
            config.requestCachePolicy = .reloadIgnoringLocalCacheData
            config.timeoutIntervalForRequest = 10
            config.timeoutIntervalForResource = 10
            let session = URLSession(configuration: config, delegate: NoRedirect(), delegateQueue: nil)
            defer { session.invalidateAndCancel() }
            var result = "Connection unavailable. Check your gateway and certificate."
            do {
                var request = URLRequest(url: url)
                request.httpMethod = "POST"
                request.setValue("Bearer " + token, forHTTPHeaderField: "Authorization")
                request.setValue("application/json", forHTTPHeaderField: "Accept")
                request.httpBody = Data()
                let (bytes, response) = try await session.bytes(for: request)
                if let http = response as? HTTPURLResponse {
                    if http.statusCode == 401 {
                        result = "Status disabled or token invalid."
                    } else if http.statusCode == 200 {
                        var data = Data()
                        for try await byte in bytes {
                            try Task.checkCancellation()
                            guard data.count < 8192 else { throw GatewayContract.Invalid.input }
                            data.append(byte)
                        }
                        let receipt = try GatewayContract.Status.decode(data)
                        result = "\(receipt.online ? "Paired host connected" : "Paired host offline") · \(receipt.pending_operations) active operations."
                    }
                }
            } catch {
                // Do not expose response, certificate or token details.
            }
            guard generation == id, !Task.isCancelled else { return }
            message = result
            checking = false
            active = nil
        }
    }
}
