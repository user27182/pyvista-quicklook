import AppKit
import Foundation
import QuickLookUI
import SceneKit

/// Builds a view that lets the reader turn the mesh with the mouse.
func sceneView(for scene: SCNScene, frame: NSRect) -> SCNView {
    let view = SCNView(frame: frame)
    view.autoresizingMask = [.width, .height]
    view.scene = scene
    view.allowsCameraControl = true
    view.autoenablesDefaultLighting = true
    view.antialiasingMode = .multisampling4X
    view.backgroundColor = .clear

    let (center, radius) = scene.rootNode.boundingSphere
    let camera = SCNCamera()
    camera.zNear = 0.01
    camera.zFar = Double(radius) * 100
    let cameraNode = SCNNode()
    cameraNode.camera = camera
    cameraNode.position = SCNVector3(
        CGFloat(center.x),
        CGFloat(center.y),
        CGFloat(center.z) + CGFloat(radius) * 3.2
    )
    scene.rootNode.addChildNode(cameraNode)
    view.pointOfView = cameraNode
    return view
}

/// Builds a view showing text, used when a mesh cannot be previewed.
func messageView(_ text: String, frame: NSRect) -> NSView {
    let field = NSTextField(wrappingLabelWithString: text)
    field.font = NSFont.monospacedSystemFont(ofSize: 11, weight: .regular)
    field.isSelectable = true
    field.translatesAutoresizingMaskIntoConstraints = false

    let scroll = NSScrollView(frame: frame)
    scroll.autoresizingMask = [.width, .height]
    scroll.hasVerticalScroller = true
    scroll.drawsBackground = false

    let container = NSView(frame: frame)
    container.addSubview(field)
    NSLayoutConstraint.activate([
        field.topAnchor.constraint(equalTo: container.topAnchor, constant: 16),
        field.leadingAnchor.constraint(equalTo: container.leadingAnchor, constant: 16),
        field.trailingAnchor.constraint(equalTo: container.trailingAnchor, constant: -16),
    ])
    scroll.documentView = container
    return scroll
}

/// Shows PyVista-readable mesh files in the Quick Look panel.
@objc(PVQLPreviewViewController)
final class PVQLPreviewViewController: NSViewController, QLPreviewingController {
    override func loadView() {
        view = NSView(frame: NSRect(x: 0, y: 0, width: 800, height: 600))
    }

    /// Replaces whatever the panel is showing with a new view.
    func show(_ replacement: NSView) {
        view.subviews.forEach { $0.removeFromSuperview() }
        replacement.frame = view.bounds
        view.addSubview(replacement)
    }

    func preparePreviewOfFile(
        at url: URL,
        completionHandler handler: @escaping (Error?) -> Void
    ) {
        pvqlLog("preview requested for \(url.path)")
        DispatchQueue.global(qos: .userInitiated).async {
            var replacement: NSView

            do {
                switch try Helper.requestPreview(url) {
                case let .scene(sceneURL):
                    defer { try? FileManager.default.removeItem(at: sceneURL) }
                    let scene = try SCNScene(url: sceneURL, options: nil)
                    replacement = sceneView(for: scene, frame: self.view.bounds)
                    pvqlLog("showing an interactive scene")
                case let .image(png):
                    let imageView = NSImageView(frame: self.view.bounds)
                    imageView.autoresizingMask = [.width, .height]
                    imageView.imageScaling = .scaleProportionallyUpOrDown
                    imageView.image = NSImage(data: png)
                    replacement = imageView
                    pvqlLog("showing a rendered image")
                }
            } catch {
                let message = (error as? Helper.Failure)?.message ?? error.localizedDescription
                pvqlLog("preview failed: \(message)")
                replacement = messageView(
                    "Could not preview \(url.lastPathComponent)\n\n\(message)",
                    frame: self.view.bounds
                )
            }

            let ready = replacement
            DispatchQueue.main.async {
                self.show(ready)
                handler(nil)
            }
        }
    }
}
