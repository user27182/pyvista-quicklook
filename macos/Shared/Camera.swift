import Foundation
import SceneKit

/// Returns a camera three quarters round and a little above the scene, with +z up.
func previewCamera(for scene: SCNScene) -> SCNNode {
    let (center, radius) = scene.rootNode.boundingSphere
    let camera = SCNCamera()
    camera.zNear = 0.01
    camera.zFar = Double(radius) * 100

    let node = SCNNode()
    node.camera = camera

    let middle = SCNVector3(CGFloat(center.x), CGFloat(center.y), CGFloat(center.z))
    let offset = SCNVector3(1, 1, 0.85)
    let length = sqrt(offset.x * offset.x + offset.y * offset.y + offset.z * offset.z)
    let distance = CGFloat(radius) * 2.6
    node.position = SCNVector3(
        middle.x + offset.x / length * distance,
        middle.y + offset.y / length * distance,
        middle.z + offset.z / length * distance
    )
    scene.rootNode.addChildNode(node)
    node.look(at: middle, up: SCNVector3(0, 0, 1), localFront: SCNVector3(0, 0, -1))
    return node
}
