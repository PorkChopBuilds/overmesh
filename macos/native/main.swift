import Cocoa
import WebKit

final class DesktopApp: NSObject, NSApplicationDelegate, WKNavigationDelegate, WKUIDelegate {
    var window: NSWindow!
    var web: WKWebView!
    var backend: Process?
    var monitor: Timer?
    var currentURL: URL?
    let smokeTest = CommandLine.arguments.contains("--smoke-test")
    var smokeScheduled = false
    var ready = false
    var quitting = false
    let token = UUID().uuidString
    let data = URL(fileURLWithPath: ProcessInfo.processInfo.environment["OVERMESH_DESKTOP_DATA"] ?? NSHomeDirectory() + "/Library/Application Support/OverMesh")
    var deadline = Date().addingTimeInterval(90)

    func applicationDidFinishLaunching(_ notification: Notification) {
        let menu = NSMenu()
        let appMenuItem = NSMenuItem()
        let appMenu = NSMenu()
        appMenu.addItem(withTitle: "About OverMesh Desktop", action: #selector(NSApplication.orderFrontStandardAboutPanel(_:)), keyEquivalent: "")
        appMenu.addItem(.separator())
        appMenu.addItem(withTitle: "Quit OverMesh Desktop", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        appMenuItem.submenu = appMenu
        menu.addItem(appMenuItem)
        let editItem = NSMenuItem(); let edit = NSMenu(title: "Edit")
        for (title, selector, key) in [("Undo", "undo:", "z"), ("Cut", "cut:", "x"), ("Copy", "copy:", "c"), ("Paste", "paste:", "v"), ("Select All", "selectAll:", "a")] {
            edit.addItem(withTitle: title, action: Selector(selector), keyEquivalent: key)
        }
        editItem.submenu = edit; menu.addItem(editItem)
        NSApp.mainMenu = menu
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1280, height: 850), styleMask: [.titled, .closable, .miniaturizable, .resizable], backing: .buffered, defer: false)
        window.title = "OverMesh Desktop"
        window.minSize = NSSize(width: 850, height: 600)
        window.isReleasedWhenClosed = false
        window.appearance = NSAppearance(named: .darkAqua)
        let config = WKWebViewConfiguration()
        config.websiteDataStore = .default()
        web = WKWebView(frame: window.contentView!.bounds, configuration: config)
        web.autoresizingMask = [.width, .height]
        web.navigationDelegate = self; web.uiDelegate = self
        window.contentView = web
        web.loadHTMLString("<body style='background:#100d17;color:#be80ff;font:20px -apple-system;padding:50px'>Starting OverMesh Desktop…</body>", baseURL: nil)
        window.center(); window.makeKeyAndOrderFront(nil); NSApp.activate(ignoringOtherApps: true)
        startBackend()
    }

    func startBackend() {
        do {
            try FileManager.default.createDirectory(at: data, withIntermediateDirectories: true)
            let logURL = data.appendingPathComponent("Desktop-launcher.log")
            if !FileManager.default.fileExists(atPath: logURL.path) { FileManager.default.createFile(atPath: logURL.path, contents: nil) }
            let log = try FileHandle(forWritingTo: logURL); try log.seekToEnd()
            let process = Process()
            process.executableURL = Bundle.main.resourceURL!.appendingPathComponent("Backend.app/Contents/MacOS/OverMesh")
            process.arguments = ["--no-browser", "--native-desktop"]
            var env = ProcessInfo.processInfo.environment
            env["OVERMESH_DESKTOP_DATA"] = data.path
            env["OVERMESH_NATIVE_TOKEN"] = token
            env["OVERMESH_PARENT_PID"] = String(ProcessInfo.processInfo.processIdentifier)
            process.environment = env
            process.standardOutput = log; process.standardError = log
            process.terminationHandler = { [weak self] child in
                DispatchQueue.main.async { self?.backendStopped(child.terminationStatus) }
            }
            backend = process
            try process.run()
            monitor = Timer.scheduledTimer(withTimeInterval: 0.25, repeats: true) { [weak self] _ in self?.checkStatus() }
        } catch { fail("Could not start the bundled service: \(error.localizedDescription)") }
    }

    func checkStatus() {
        guard let child = backend, child.isRunning, !quitting else { return }
        if let bytes = try? Data(contentsOf: data.appendingPathComponent("desktop-status.json")),
           let status = try? JSONSerialization.jsonObject(with: bytes) as? [String: Any],
           status["native_token"] as? String == token,
           let text = status["url"] as? String, let url = URL(string: text), url.host == "127.0.0.1", url.scheme == "http" {
            ready = true
            if currentURL != url { currentURL = url; web.load(URLRequest(url: url)) }
        } else if !ready && Date() > deadline { fail("The local service did not start within 90 seconds. See OverMesh.log in Library/Application Support/OverMesh.") }
    }

    func backendStopped(_ status: Int32) {
        monitor?.invalidate()
        if quitting { NSApp.reply(toApplicationShouldTerminate: true); return }
        if status == 73 { fail("OverMesh is already running. Shut down the browser version using its power button, then open OverMesh Desktop again. Both versions use the same settings and radio history.") }
        else if status == 0 && ready { NSApp.terminate(nil) }
        else { fail("The local service stopped (code \(status)). Details are in Library/Application Support/OverMesh/OverMesh.log and Desktop-launcher.log.") }
    }

    func fail(_ message: String) {
        guard !quitting else { return }
        monitor?.invalidate()
        if smokeTest {
            let result: [String: Any] = ["ok": false, "error": message]
            if let bytes = try? JSONSerialization.data(withJSONObject: result) { try? bytes.write(to: data.appendingPathComponent("native-smoke.json")) }
            NSApp.terminate(nil); return
        }
        let alert = NSAlert(); alert.messageText = "OverMesh Desktop"; alert.informativeText = message
        alert.addButton(withTitle: "Quit"); alert.runModal(); NSApp.terminate(nil)
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool { window.makeKeyAndOrderFront(nil); return true }
    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        quitting = true; monitor?.invalidate()
        guard let process = backend, process.isRunning else { return .terminateNow }
        process.terminate()
        DispatchQueue.main.asyncAfter(deadline: .now() + 8) { [weak self] in
            if process.isRunning { kill(process.processIdentifier, SIGKILL) }
            if self?.quitting == true { NSApp.reply(toApplicationShouldTerminate: true) }
        }
        return .terminateLater
    }

    func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = action.request.url else { decisionHandler(.cancel); return }
        if url.scheme == "about" || (url.host == "127.0.0.1" && url.port == currentURL?.port) { decisionHandler(.allow) }
        else { if action.navigationType == .linkActivated, ["https", "http"].contains(url.scheme ?? "") { NSWorkspace.shared.open(url) }; decisionHandler(.cancel) }
    }
    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        guard smokeTest, ready, !smokeScheduled, webView.url?.host == "127.0.0.1" else { return }
        smokeScheduled = true
        DispatchQueue.main.asyncAfter(deadline: .now() + 3) {
            webView.evaluateJavaScript("JSON.stringify({title:document.title,header:!!document.getElementById('header'),accent:getComputedStyle(document.documentElement).getPropertyValue('--accent').trim(),text:document.body.innerText.slice(0,500)})") { value, error in
                var result: [String: Any] = ["ok": false]
                if let text = value as? String, let bytes = text.data(using: .utf8), let page = try? JSONSerialization.jsonObject(with: bytes) as? [String: Any] {
                    result = ["ok": page["header"] as? Bool == true, "page": page]
                } else { result["error"] = error?.localizedDescription ?? "Dashboard could not be inspected" }
                if let bytes = try? JSONSerialization.data(withJSONObject: result, options: .prettyPrinted) { try? bytes.write(to: self.data.appendingPathComponent("native-smoke.json")) }
                webView.takeSnapshot(with: nil) { image, _ in
                    if let image = image, let tiff = image.tiffRepresentation, let bitmap = NSBitmapImageRep(data: tiff), let png = bitmap.representation(using: .png, properties: [:]) { try? png.write(to: self.data.appendingPathComponent("native-preview.png")) }
                    NSApp.terminate(nil)
                }
            }
        }
    }
    func webViewWebContentProcessDidTerminate(_ webView: WKWebView) { webView.reload() }
    func webView(_ webView: WKWebView, runJavaScriptAlertPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping () -> Void) {
        let alert = NSAlert(); alert.messageText = message; alert.runModal(); completionHandler()
    }
    func webView(_ webView: WKWebView, runJavaScriptConfirmPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (Bool) -> Void) {
        let alert = NSAlert(); alert.messageText = message; alert.addButton(withTitle: "OK"); alert.addButton(withTitle: "Cancel"); completionHandler(alert.runModal() == .alertFirstButtonReturn)
    }
}
let application = NSApplication.shared
let delegate = DesktopApp()
application.delegate = delegate
application.setActivationPolicy(.regular)
application.run()
