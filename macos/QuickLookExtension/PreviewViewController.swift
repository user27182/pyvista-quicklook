import AppKit
import Foundation
import QuickLookUI
import SceneKit

/// What to put in the panel once the render service has answered.
enum Preview {
    case scene(SCNScene)
    case image(Data)
    case text(String)
    case details(URL, String)
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

/// How many entries of a folder are examined when looking for a DICOM series.
let dicomSampleSize = 8

/// Returns whether a folder holds DICOM slices, the one kind of folder that is a dataset.
/// Every DICOM file carries "DICM" after a 128 byte preamble, whatever it is named.
func holdsDicomFiles(_ url: URL) -> Bool {
    let manager = FileManager.default
    let entries = (try? manager.contentsOfDirectory(
        at: url,
        includingPropertiesForKeys: [.isRegularFileKey],
        options: [.skipsHiddenFiles, .skipsSubdirectoryDescendants]
    )) ?? []
    for entry in entries.sorted(by: { $0.lastPathComponent < $1.lastPathComponent })
        .prefix(dicomSampleSize) {
        guard let handle = try? FileHandle(forReadingFrom: entry) else {
            continue
        }
        defer { try? handle.close() }
        let head = handle.readData(ofLength: 132)
        if head.count == 132, head.suffix(4) == Data("DICM".utf8) {
            return true
        }
    }
    return false
}

/// Builds the Finder's own account of a file: its icon, name, size, and date. Shown for
/// a claimed file that holds no mesh, such as a gzip archive of something else.
@MainActor
func detailsView(_ url: URL, reason: String) -> NSView {
    let icon = NSImageView(image: NSWorkspace.shared.icon(forFile: url.path))
    icon.imageScaling = .scaleProportionallyUpOrDown

    let name = NSTextField(labelWithString: url.lastPathComponent)
    name.font = NSFont.systemFont(ofSize: 20, weight: .semibold)
    name.lineBreakMode = .byTruncatingMiddle
    name.alignment = .center

    let keys: Set<URLResourceKey> = [
        .fileSizeKey, .totalFileSizeKey, .contentModificationDateKey, .isDirectoryKey,
    ]
    let values = try? url.resourceValues(forKeys: keys)
    var lines: [String] = []
    if values?.isDirectory == true {
        let entries = (try? FileManager.default.contentsOfDirectory(atPath: url.path)) ?? []
        lines.append(entries.count == 1 ? "1 item" : "\(entries.count) items")
    } else if let bytes = values?.totalFileSize ?? values?.fileSize {
        lines.append(ByteCountFormatter.string(fromByteCount: Int64(bytes), countStyle: .file))
    }
    if let modified = values?.contentModificationDate {
        let stamp = DateFormatter.localizedString(from: modified, dateStyle: .medium, timeStyle: .short)
        lines.append("Last modified \(stamp)")
    }
    let facts = NSTextField(labelWithString: lines.joined(separator: "\n"))
    facts.font = NSFont.systemFont(ofSize: 13)
    facts.textColor = .secondaryLabelColor
    facts.alignment = .center

    let note = NSTextField(wrappingLabelWithString: reason)
    note.isHidden = reason.isEmpty
    note.font = NSFont.systemFont(ofSize: 11)
    note.textColor = .tertiaryLabelColor
    note.alignment = .center
    note.isSelectable = true
    note.setContentCompressionResistancePriority(.defaultLow, for: .vertical)

    let stack = NSStackView(views: [icon, name, facts, note])
    stack.orientation = .vertical
    stack.alignment = .centerX
    stack.spacing = 10
    stack.translatesAutoresizingMaskIntoConstraints = false

    let container = NSView()
    container.addSubview(stack)
    NSLayoutConstraint.activate([
        icon.widthAnchor.constraint(equalToConstant: 96),
        icon.heightAnchor.constraint(equalToConstant: 96),
        stack.centerYAnchor.constraint(equalTo: container.centerYAnchor),
        stack.leadingAnchor.constraint(equalTo: container.leadingAnchor, constant: 24),
        stack.trailingAnchor.constraint(equalTo: container.trailingAnchor, constant: -24),
    ])
    return container
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
            var isFolder: ObjCBool = false
            FileManager.default.fileExists(atPath: url.path, isDirectory: &isFolder)
            if isFolder.boolValue, !holdsDicomFiles(url) {
                // Answer for an ordinary folder here, rather than waiting on the service.
                DispatchQueue.main.async {
                    self.show(detailsView(url, reason: ""))
                    pvqlLog("showing folder details")
                    handler(nil)
                }
                return
            }

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
                let failure = error as? Helper.Failure
                let message = failure?.message ?? error.localizedDescription
                pvqlLog("not a mesh: \(message.prefix(120))")
                if failure?.isSetup == true {
                    outcome = .message("Could not preview \(url.lastPathComponent)\n\n\(message)")
                } else if let text = textContents(of: url) {
                    outcome = .text(text)
                } else {
                    outcome = .details(url, message)
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
                case let .details(fileURL, reason):
                    self.show(detailsView(fileURL, reason: reason))
                    pvqlLog("showing file details: \(reason.prefix(80))")
                case let .message(text):
                    self.show(messageView(text))
                    pvqlLog("showing a message: \(text.prefix(120))")
                }
                handler(nil)
            }
        }
    }
}
