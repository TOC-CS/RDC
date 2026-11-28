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
    var body: some Scene { WindowGroup { StatusView() } }
}

struct StatusView: View {
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
