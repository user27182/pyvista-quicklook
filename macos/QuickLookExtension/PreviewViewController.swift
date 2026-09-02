import AppKit
import Foundation
import QuickLookUI
import SceneKit

/// What to put in the panel once the render service has answered.
enum Preview {
    case scene(SCNScene)
    case image(Data)
    case text(String)
    case message(String)
}

/// How much of a text file is shown.
let textPreviewLimit = 2_000_000

/// Returns the file's contents when it reads as text, which a claimed file may turn out to be.
func textContents(of url: URL) -> String? {
    guard let handle = try? FileHandle(forReadingFrom: url) else {
        return nil
    }
    defer { try? handle.close() }
    let data = handle.readData(ofLength: textPreviewLimit)
    guard !data.isEmpty, !data.contains(0) else {
        return nil
    }
    let controls = data.filter { $0 < 0x20 && $0 != 0x09 && $0 != 0x0A && $0 != 0x0D }.count
    guard controls * 100 < data.count else {
        return nil
    }
    guard let text = String(data: data, encoding: .utf8) ?? String(data: data, encoding: .isoLatin1) else {
        return nil
    }
    let size = (try? url.resourceValues(forKeys: [.fileSizeKey]).fileSize) ?? data.count
    return size > data.count ? text + "\n\n[first \(data.count / 1_000_000) MB of \(size / 1_000_000) MB]" : text
}

/// Builds a view that lets the reader turn the mesh with the mouse.
@MainActor
func sceneView(for scene: SCNScene) -> SCNView {
    let view = SCNView()
    view.scene = scene
    view.allowsCameraControl = true
    view.autoenablesDefaultLighting = true
    view.antialiasingMode = .multisampling4X
    view.backgroundColor = .clear

    view.pointOfView = previewCamera(for: scene)
    return view
}

/// Builds a scrolling view of a file's text, for claimed files that are not meshes.
@MainActor
func textView(_ text: String) -> NSView {
    let view = NSTextView()
    view.string = text
    view.isEditable = false
    view.isSelectable = true
    view.font = NSFont.monospacedSystemFont(ofSize: 11, weight: .regular)
    view.textContainerInset = NSSize(width: 12, height: 12)
    view.autoresizingMask = [.width]
    view.isVerticallyResizable = true
    view.isHorizontallyResizable = false
    view.textContainer?.widthTracksTextView = true

    let scroll = NSScrollView()
    scroll.hasVerticalScroller = true
    scroll.documentView = view
    return scroll
}

/// Builds a view showing text, used when a mesh cannot be previewed.
@MainActor
func messageView(_ text: String) -> NSView {
    let field = NSTextField(wrappingLabelWithString: text)
    field.font = NSFont.monospacedSystemFont(ofSize: 11, weight: .regular)
    field.isSelectable = true
    field.translatesAutoresizingMaskIntoConstraints = false

    let container = NSView()
    container.addSubview(field)
    NSLayoutConstraint.activate([
        field.topAnchor.constraint(equalTo: container.topAnchor, constant: 16),
        field.leadingAnchor.constraint(equalTo: container.leadingAnchor, constant: 16),
        field.trailingAnchor.constraint(equalTo: container.trailingAnchor, constant: -16),
        field.bottomAnchor.constraint(lessThanOrEqualTo: container.bottomAnchor, constant: -16),
    ])
    return container
}

/// Shows PyVista-readable mesh files in the Quick Look panel.
@objc(PVQLPreviewViewController)
final class PVQLPreviewViewController: NSViewController, QLPreviewingController {
    override func loadView() {
        view = NSView(frame: NSRect(x: 0, y: 0, width: 800, height: 600))
    }

    /// Fills the panel with a view, pinned to every edge so it resizes with it.
    @MainActor
    func show(_ replacement: NSView) {
        view.subviews.forEach { $0.removeFromSuperview() }
        replacement.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(replacement)
        NSLayoutConstraint.activate([
            replacement.topAnchor.constraint(equalTo: view.topAnchor),
            replacement.bottomAnchor.constraint(equalTo: view.bottomAnchor),
            replacement.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            replacement.trailingAnchor.constraint(equalTo: view.trailingAnchor),
        ])
        view.layoutSubtreeIfNeeded()
    }

    func preparePreviewOfFile(
        at url: URL,
        completionHandler handler: @escaping (Error?) -> Void
    ) {
        pvqlLog("preview requested for \(url.path)")
        DispatchQueue.global(qos: .userInitiated).async {
            // Only file work here; AppKit views are built on the main thread below.
            let outcome: Preview
            do {
                switch try Helper.requestPreview(url) {
                case let .scene(sceneURL):
                    defer { try? FileManager.default.removeItem(at: sceneURL) }
                    outcome = .scene(try SCNScene(url: sceneURL, options: nil))
                case let .image(png):
                    outcome = .image(png)
                }
            } catch {
                let message = (error as? Helper.Failure)?.message ?? error.localizedDescription
                pvqlLog("not a mesh: \(message.prefix(120))")
                if let text = textContents(of: url) {
                    outcome = .text(text)
                } else {
                    outcome = .message("Could not preview \(url.lastPathComponent)\n\n\(message)")
                }
            }

            DispatchQueue.main.async {
                switch outcome {
                case let .scene(scene):
                    self.show(sceneView(for: scene))
                    pvqlLog("showing an interactive scene in \(self.view.bounds.size)")
                case let .image(png):
                    let imageView = NSImageView()
                    imageView.imageScaling = .scaleProportionallyUpOrDown
                    imageView.image = NSImage(data: png)
                    self.show(imageView)
                    pvqlLog("showing a rendered image in \(self.view.bounds.size)")
                case let .text(text):
                    self.show(textView(text))
                    pvqlLog("showing text, \(text.count) characters")
                case let .message(text):
                    self.show(messageView(text))
                    pvqlLog("showing a message: \(text.prefix(120))")
                }
                handler(nil)
            }
        }
    }
}
