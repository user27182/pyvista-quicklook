import AppKit

/// Window showing the state of the Quick Look integration.
final class StatusController: NSObject, NSApplicationDelegate {
    let window = NSWindow(
        contentRect: NSRect(x: 0, y: 0, width: 720, height: 520),
        styleMask: [.titled, .closable, .miniaturizable, .resizable],
        backing: .buffered,
        defer: false
    )
    let textView = NSTextView()
    let runButton = NSButton(title: "Run Diagnostics", target: nil, action: nil)

    func applicationDidFinishLaunching(_ notification: Notification) {
        buildMenu()
        buildWindow()
        runDiagnostics()
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        true
    }

    /// Installs a minimal main menu so the standard shortcuts work.
    func buildMenu() {
        let mainMenu = NSMenu()
        let appItem = NSMenuItem()
        let appMenu = NSMenu()
        appMenu.addItem(withTitle: "Quit PyVista Quick Look", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        appItem.submenu = appMenu
        mainMenu.addItem(appItem)
        NSApp.mainMenu = mainMenu
    }

    /// Lays out the diagnostics window.
    func buildWindow() {
        window.title = "PyVista Quick Look"
        window.center()

        let scroll = NSScrollView()
        scroll.hasVerticalScroller = true
        scroll.borderType = .bezelBorder
        scroll.documentView = textView
        textView.isEditable = false
        textView.font = NSFont.monospacedSystemFont(ofSize: 12, weight: .regular)
        textView.textContainerInset = NSSize(width: 8, height: 8)
        textView.autoresizingMask = [.width]

        runButton.target = self
        runButton.action = #selector(runDiagnostics)
        let configButton = NSButton(title: "Open Config File", target: self, action: #selector(openConfig))
        let cacheButton = NSButton(title: "Reveal Cache", target: self, action: #selector(revealCache))

        let buttons = NSStackView(views: [runButton, configButton, cacheButton])
        buttons.orientation = .horizontal
        buttons.spacing = 8

        let stack = NSStackView(views: [scroll, buttons])
        stack.orientation = .vertical
        stack.spacing = 12
        stack.edgeInsets = NSEdgeInsets(top: 16, left: 16, bottom: 16, right: 16)
        stack.translatesAutoresizingMaskIntoConstraints = false
        scroll.setContentHuggingPriority(.defaultLow, for: .vertical)

        window.contentView = NSView()
        window.contentView?.addSubview(stack)
        if let content = window.contentView {
            NSLayoutConstraint.activate([
                stack.topAnchor.constraint(equalTo: content.topAnchor),
                stack.bottomAnchor.constraint(equalTo: content.bottomAnchor),
                stack.leadingAnchor.constraint(equalTo: content.leadingAnchor),
                stack.trailingAnchor.constraint(equalTo: content.trailingAnchor),
            ])
        }
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    /// Runs `pvql doctor` and shows its report.
    @objc func runDiagnostics() {
        runButton.isEnabled = false
        textView.string = "Running diagnostics…\n"
        DispatchQueue.global(qos: .userInitiated).async {
            let report: String
            do {
                let result = try Helper.run(["doctor"])
                report = [result.output, result.errors].filter { !$0.isEmpty }.joined(separator: "\n")
            } catch {
                report = (error as? Helper.Failure)?.message ?? error.localizedDescription
            }
            DispatchQueue.main.async {
                self.textView.string = report
                self.runButton.isEnabled = true
            }
        }
    }

    /// Opens the configuration file, creating it first when it does not exist.
    @objc func openConfig() {
        let path = URL(fileURLWithPath: realHome())
            .appendingPathComponent("Library/Application Support/PyVistaQuickLook/config.json")
        if !FileManager.default.fileExists(atPath: path.path) {
            _ = try? Helper.run(["config", "--init"])
        }
        NSWorkspace.shared.open(path)
    }

    /// Reveals the preview cache in the Finder.
    @objc func revealCache() {
        let path = URL(fileURLWithPath: realHome())
            .appendingPathComponent("Library/Caches/PyVistaQuickLook")
        try? FileManager.default.createDirectory(at: path, withIntermediateDirectories: true)
        NSWorkspace.shared.selectFile(nil, inFileViewerRootedAtPath: path.path)
    }
}

let controller = StatusController()
let application = NSApplication.shared
application.delegate = controller
application.setActivationPolicy(.regular)
application.run()
