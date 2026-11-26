import Foundation
import SwiftUI
import UIKit

/// A separate development target. Its shared Documents directory contains only
/// authenticated mailbox frames; the legacy unsigned cold runner is not linked.
@main @MainActor struct RDCWarmTerminalApp: App {
    @StateObject private var session = WarmTerminalSession()
    var body: some Scene {
        WindowGroup { WarmTerminalSessionView(session: session) }
    }
}

@MainActor private final class WarmTerminalSession: ObservableObject {
    @Published private(set) var status = "Waiting for an authorized development session"
    private var started = false
    private var task: Task<Void, Never>?
    private var gate: WarmTerminalMailbox.ActivityGate?

    private static var sessionID: String? {
        let args = CommandLine.arguments
        guard args.count == 3, args[1] == "--rdc-warm-terminal",
              UUID(uuidString: args[2])?.uuidString.lowercased() == args[2]
        else { return nil }
        return args[2]
    }

    /// This bootstrap creates no session, key, command or execution claim.
    private static func folders() throws -> (URL, URL) {
        let fm = FileManager.default
        let documents = fm.urls(for: .documentDirectory, in: .userDomainMask)[0]
        let support = fm.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("RDCWarmTerminal", isDirectory: true)
        for folder in [documents, support] {
            try fm.createDirectory(at: folder, withIntermediateDirectories: true,
                                   attributes: [.posixPermissions: 0o700])
            try fm.setAttributes([.posixPermissions: 0o700], ofItemAtPath: folder.path)
        }
        return (documents, support)
    }

    func beginIfActive(_ phase: ScenePhase) {
        guard phase == .active, !started, UIApplication.shared.isProtectedDataAvailable else { return }
        let locations: (URL, URL)
        do { locations = try Self.folders() }
        catch { status = "Local storage unavailable"; return }
        guard let sessionID = Self.sessionID else { return }
        started = true
        let activity = WarmTerminalMailbox.ActivityGate(active: true)
        gate = activity
        let documents = locations.0, support = locations.1
        status = "Checking the authorized session"
        task = Task.detached(priority: .userInitiated) { [weak self] in
            await withTaskCancellationHandler {
                do {
                    let box = try WarmTerminalMailbox(documents: documents, support: support,
                        workspace: support.appendingPathComponent("RDCWorkspace", isDirectory: true),
                        sessionID: sessionID, gate: activity)
                    guard box.activate() == .ready else {
                        await self?.finish("Session unavailable", activity: activity)
                        return
                    }
                    await self?.report("Ready for authorized USB commands")
                    // A second independent bound backs the session's wall/monotonic expiry.
                    for _ in 0..<24_000 {
                        guard !Task.isCancelled, activity.isActive else { break }
                        let outcome = box.processNext()
                        if outcome == .stopped || outcome == .outcomeUnknown {
                            await self?.finish(outcome == .outcomeUnknown
                                ? "Result recovery required" : "Session stopped", activity: activity)
                            box.stop()
                            return
                        }
                        // Partial incoming frames are re-read, never claimed or executed.
                        try await Task.sleep(nanoseconds: 25_000_000)
                    }
                    box.stop()
                    await self?.finish("Session stopped", activity: activity)
                } catch {
                    activity.cancel()
                    await self?.finish("Session stopped", activity: activity)
                }
            } onCancel: {
                activity.cancel()
            }
        }
    }

    private func report(_ value: String) {
        if gate?.isActive == true { status = value }
    }

    private func finish(_ value: String, activity: WarmTerminalMailbox.ActivityGate) {
        guard gate === activity else { return }
        status = value
        task = nil
    }

    func stop() {
        guard started else { return }
        gate?.cancel()
        task?.cancel()
        status = "Session stopped"
    }

    deinit { gate?.cancel(); task?.cancel() }
}

private struct WarmTerminalSessionView: View {
    @Environment(\.scenePhase) private var phase
    @ObservedObject var session: WarmTerminalSession
    var body: some View {
        VStack(spacing: 16) {
            Text("RDC warm terminal").font(.title)
            Text(session.status).accessibilityLabel(session.status)
            Text("Device-local commands in the RDC workspace.")
                .font(.caption)
        }
        .padding()
        .task { session.beginIfActive(phase) }
        .onChange(of: phase) { value in
            if value == .active { session.beginIfActive(value) }
            else { session.stop() }
        }
        .onReceive(NotificationCenter.default.publisher(
            for: UIApplication.protectedDataWillBecomeUnavailableNotification)) { _ in session.stop() }
        .onReceive(NotificationCenter.default.publisher(
            for: UIApplication.protectedDataDidBecomeAvailableNotification)) { _ in
                session.beginIfActive(phase)
            }
        .onDisappear { session.stop() }
    }
}
