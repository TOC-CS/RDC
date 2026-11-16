import Foundation
import AppKit
import ApplicationServices
import ScreenCaptureKit

// JSON stdin/stdout only. Capture and resize never prompt or activate apps.
// Only the owner's explicit setup command can request OS permission.
// No display capture, focus selection, private AX APIs, or fallback window.
struct WindowFailure: Error { let code: String }
func reject(_ code: String) throws -> Never { throw WindowFailure(code:code) }

@available(macOS 14.0, *)
@main struct WindowPreview {
    @MainActor static func main() async {
        _ = NSApplication.shared
        do {
            let data=FileHandle.standardInput.readDataToEndOfFile()
            guard data.count<=8192, let request=try JSONSerialization.jsonObject(with:data) as? [String:Any],
                  let action=request["action"] as? String else { try reject("window_capture_unavailable") }
            let result=try await run(action,request)
            FileHandle.standardOutput.write(try JSONSerialization.data(withJSONObject:result))
        } catch {
            let code=(error as? WindowFailure)?.code ?? "window_capture_unavailable"
            let data=try! JSONSerialization.data(withJSONObject:["ok":false,"code":code])
            FileHandle.standardOutput.write(data)
        }
    }

    static func identity(_ window: SCWindow) -> [String:Any]? {
        guard let owner=window.owningApplication,
              let app=NSRunningApplication(processIdentifier:owner.processID),
              let launched=app.launchDate else { return nil }
        return ["window_id":Int(window.windowID),"pid":Int(owner.processID),
                "launch_id":String(launched.timeIntervalSince1970),"bundle_id":owner.bundleIdentifier,
                "title":window.title ?? owner.applicationName,
                "width":Int(window.frame.width.rounded()),"height":Int(window.frame.height.rounded())]
    }

    static func run(_ action:String,_ args:[String:Any]) async throws -> [String:Any] {
        if action=="permissions" || action=="request_permission" {
            if action=="request_permission" {
                switch args["permission"] as? String {
                case "accessibility":
                    let options=[kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String:true] as CFDictionary
                    _ = AXIsProcessTrustedWithOptions(options)
                case "screen-recording": _ = CGRequestScreenCaptureAccess()
                default: try reject("invalid_arguments")
                }
            }
            // Requests are asynchronous. Return observed permissions, never
            // interpret a displayed prompt as an owner grant.
            return ["ok":true,"screen_recording":CGPreflightScreenCaptureAccess(),
                    "accessibility":AXIsProcessTrusted()]
        }
        guard CGPreflightScreenCaptureAccess() else { try reject("screen_permission_required") }
        let content=try await SCShareableContent.excludingDesktopWindows(true,onScreenWindowsOnly:false)
        let windows=content.windows.filter { $0.windowLayer==0 && $0.frame.width>0 && $0.frame.height>0 }
        if action=="list" { return ["ok":true,"windows":windows.compactMap(identity)] }
        guard let number=args["window_id"] as? Int,let pid=args["pid"] as? Int,let launch=args["launch_id"] as? String,
              let window=windows.first(where:{Int($0.windowID)==number}),
              let info=identity(window), info["pid"] as? Int==pid, info["launch_id"] as? String==launch else {
            try reject("session_not_found")
        }
        if action=="capture" {
            let filter=SCContentFilter(desktopIndependentWindow:window)
            let config=SCStreamConfiguration()
            let scale=min(2.0,2560.0/window.frame.width,1600.0/window.frame.height)
            config.width=max(1,Int(window.frame.width*scale))
            config.height=max(1,Int(window.frame.height*scale))
            config.showsCursor=true
            config.ignoreShadowsSingleWindow=true
            config.shouldBeOpaque=true
            if #available(macOS 14.2, *) { config.includeChildWindows=false }
            let image=try await SCScreenshotManager.captureImage(contentFilter:filter,configuration:config)
            let bitmap=NSBitmapImageRep(cgImage:image)
            guard let jpeg=bitmap.representation(using:.jpeg,properties:[.compressionFactor:0.8]),jpeg.count<=8*1024*1024 else {
                try reject("window_capture_unavailable")
            }
            return ["ok":true,"data":jpeg.base64EncodedString(),"mime_type":"image/jpeg",
                    "width":image.width,"height":image.height,"window_width":window.frame.width,
                    "window_height":window.frame.height,"cursor_in_image":true]
        }
        guard action=="resize",let width=args["width"] as? Int,let height=args["height"] as? Int,
              (240...2560).contains(width),(180...1600).contains(height) else { try reject("window_capture_unavailable") }
        guard AXIsProcessTrusted() else { try reject("accessibility_permission_required") }
        let application=AXUIElementCreateApplication(pid_t(pid))
        var raw:CFTypeRef?
        guard AXUIElementCopyAttributeValue(application,kAXWindowsAttribute as CFString,&raw) == .success,
              let candidates=raw as? [AXUIElement] else { try reject("resize_unavailable") }
        // Public Accessibility has no portable CGWindowID attribute. Match the
        // owning PID plus exact title and position/size, and refuse ambiguity.
        let matched=candidates.filter { element in
            guard let bounds=rect(element) else { return false }
            var title:CFTypeRef?
            guard AXUIElementCopyAttributeValue(element,kAXTitleAttribute as CFString,&title) == .success else { return false }
            return (title as? String ?? "") == (window.title ?? "") &&
                abs(bounds.minX-window.frame.minX)<2 && abs(bounds.minY-window.frame.minY)<2 &&
                abs(bounds.width-window.frame.width)<2 && abs(bounds.height-window.frame.height)<2
        }
        guard matched.count==1 else { try reject("window_ambiguous") }
        var settable=DarwinBoolean(false)
        guard AXUIElementIsAttributeSettable(matched[0],kAXSizeAttribute as CFString,&settable) == .success,
              settable.boolValue else { try reject("resize_unavailable") }
        var size=CGSize(width:width,height:height)
        guard let value=AXValueCreate(.cgSize,&size),
              AXUIElementSetAttributeValue(matched[0],kAXSizeAttribute as CFString,value) == .success else { try reject("resize_unavailable") }
        try await Task.sleep(nanoseconds:100_000_000)
        guard let actual=rect(matched[0]) else { try reject("session_not_found") }
        return ["ok":true,"width":Int(actual.width.rounded()),"height":Int(actual.height.rounded())]
    }

    static func rect(_ element:AXUIElement) -> CGRect? {
        var positionRaw:CFTypeRef?,sizeRaw:CFTypeRef?
        guard AXUIElementCopyAttributeValue(element,kAXPositionAttribute as CFString,&positionRaw) == .success,
              AXUIElementCopyAttributeValue(element,kAXSizeAttribute as CFString,&sizeRaw) == .success,
              let p=positionRaw,let s=sizeRaw,CFGetTypeID(p)==AXValueGetTypeID(),CFGetTypeID(s)==AXValueGetTypeID() else { return nil }
        var point=CGPoint.zero,size=CGSize.zero
        guard AXValueGetValue(unsafeBitCast(p,to:AXValue.self),.cgPoint,&point),
              AXValueGetValue(unsafeBitCast(s,to:AXValue.self),.cgSize,&size) else { return nil }
        return CGRect(origin:point,size:size)
    }
}
