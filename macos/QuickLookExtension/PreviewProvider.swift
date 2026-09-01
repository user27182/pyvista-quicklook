import Foundation
import ImageIO
import QuickLookUI
import UniformTypeIdentifiers

/// Returns the pixel dimensions of encoded image data.
func imageSize(_ data: Data) -> CGSize? {
    guard let source = CGImageSourceCreateWithData(data as CFData, nil),
          let properties = CGImageSourceCopyPropertiesAtIndex(source, 0, nil) as? [CFString: Any],
          let width = properties[kCGImagePropertyPixelWidth] as? Double,
          let height = properties[kCGImagePropertyPixelHeight] as? Double
    else {
        return nil
    }
    return CGSize(width: width, height: height)
}

/// Supplies Quick Look previews for mesh files that PyVista can read.
@objc(PVQLPreviewProvider)
final class PVQLPreviewProvider: QLPreviewProvider, QLPreviewingController {
    func providePreview(
        for request: QLFilePreviewRequest,
        completionHandler handler: @escaping (QLPreviewReply?, Error?) -> Void
    ) {
        let url = request.fileURL
        pvqlLog("preview requested for \(url.path)")
        DispatchQueue.global(qos: .userInitiated).async {
            do {
                let png = try Helper.requestPreview(url)
                let size = imageSize(png) ?? CGSize(width: 1024, height: 1024)
                let reply = QLPreviewReply(dataOfContentType: .png, contentSize: size) { _ in png }
                reply.title = url.lastPathComponent
                handler(reply, nil)
            } catch {
                let message = (error as? Helper.Failure)?.message ?? error.localizedDescription
                pvqlLog("preview failed: \(message)")
                let text = "Could not preview \(url.lastPathComponent)\n\n\(message)\n"
                let reply = QLPreviewReply(
                    dataOfContentType: .plainText,
                    contentSize: CGSize(width: 800, height: 600)
                ) { _ in Data(text.utf8) }
                reply.title = url.lastPathComponent
                handler(reply, nil)
            }
        }
    }
}
