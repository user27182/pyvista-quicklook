import AppKit
import Foundation
import QuickLookUI
import SceneKit
import UniformTypeIdentifiers

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

/// Whether the file's type is one this app exported. A type macOS owns, a gzip archive
/// or a folder, keeps whatever preview macOS gives it when there is no mesh to show.
func isOwnType(_ url: URL) -> Bool {
    let type = (try? url.resourceValues(forKeys: [.contentTypeKey]))?.contentType
    return type?.identifier.hasPrefix(utiPrefix) ?? false
}

let utiPrefix = "io.github.user27182.pyvista-quicklook"

/// Returns the opening of a failure, which is all the details view has room for.
func briefly(_ reason: String, limit: Int = 200) -> String {
    let joined = reason.split(whereSeparator: \.isNewline).map(String.init).prefix(2)
        .joined(separator: " ")
    return joined.count > limit ? String(joined.prefix(limit)) + "…" : joined
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

/// Builds the account of a file that Quick Look gives one it cannot open: its icon on
/// the left, and its name, size, and date beside it. Shown for a file of a type this app
/// exported that turns out to hold no mesh; a type macOS owns keeps its own preview.
@MainActor
func detailsView(_ url: URL, reason: String) -> NSView {
    let icon = NSImageView(image: NSWorkspace.shared.icon(forFile: url.path))
    icon.imageScaling = .scaleProportionallyUpOrDown
    icon.translatesAutoresizingMaskIntoConstraints = false

    let name = NSTextField(labelWithString: url.lastPathComponent)
    name.font = NSFont.systemFont(ofSize: 28, weight: .bold)
    name.lineBreakMode = .byTruncatingMiddle

    let values = try? url.resourceValues(forKeys: [.fileSizeKey, .contentModificationDateKey])
    var lines: [String] = []
    if let bytes = values?.fileSize {
        lines.append(ByteCountFormatter.string(fromByteCount: Int64(bytes), countStyle: .file))
    }
    if let modified = values?.contentModificationDate {
        let stamp = DateFormatter.localizedString(from: modified, dateStyle: .medium, timeStyle: .medium)
        lines.append("Last modified \(stamp)")
    }
    let facts = NSTextField(labelWithString: lines.joined(separator: "\n"))
    facts.font = NSFont.systemFont(ofSize: 16)
    facts.textColor = .secondaryLabelColor

    let note = NSTextField(wrappingLabelWithString: briefly(reason))
    note.font = NSFont.systemFont(ofSize: 11)
    note.textColor = .tertiaryLabelColor
    note.isHidden = reason.isEmpty

    let text = NSStackView(views: [name, facts, note])
    text.orientation = .vertical
    text.alignment = .leading
    text.spacing = 8

    let row = NSStackView(views: [icon, text])
    row.orientation = .horizontal
    row.alignment = .centerY
    row.spacing = 24
    row.translatesAutoresizingMaskIntoConstraints = false

    let container = NSView()
    container.addSubview(row)
    NSLayoutConstraint.activate([
        icon.widthAnchor.constraint(equalToConstant: 128),
        icon.heightAnchor.constraint(equalToConstant: 128),
        row.centerXAnchor.constraint(equalTo: container.centerXAnchor),
        row.centerYAnchor.constraint(equalTo: container.centerYAnchor),
        row.leadingAnchor.constraint(greaterThanOrEqualTo: container.leadingAnchor, constant: 24),
        row.trailingAnchor.constraint(lessThanOrEqualTo: container.trailingAnchor, constant: -24),
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
    /// Handed back for a file this extension has nothing to add to.
    static let noPreview = NSError(
        domain: utiPrefix,
        code: 1,
        userInfo: [NSLocalizedDescriptionKey: "No mesh to preview."]
    )

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
            let isFolder = (try? url.resourceValues(forKeys: [.isDirectoryKey]))?.isDirectory
            if isFolder == true, !holdsDicomFiles(url) {
                // Hand an ordinary folder straight back, without waiting on the service,
                // so Quick Look shows the folder preview it would have shown anyway.
                pvqlLog("declining an ordinary folder")
                DispatchQueue.main.async { handler(Self.noPreview) }
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
                } else if !isOwnType(url) {
                    // The type belongs to macOS, so its own preview is the right one.
                    pvqlLog("declining, not a mesh: \(briefly(message))")
                    DispatchQueue.main.async { handler(Self.noPreview) }
                    return
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
