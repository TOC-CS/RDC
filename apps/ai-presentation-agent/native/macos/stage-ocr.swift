import Foundation
import AppKit
import Vision

// Offline OCR observer for an operator-authorized captured camera frame.
// No camera is opened here. Never pass a screenshot from presentation output
// back into the cue system.
guard CommandLine.arguments.count == 2 else {
  fputs("Usage: stage-ocr IMAGE_FILE\n", stderr)
  exit(2)
}
let path = CommandLine.arguments[1]
let buffer: Data? = path == "-" ?
  FileHandle.standardInput.readDataToEndOfFile() :
  (try? Data(contentsOf: URL(fileURLWithPath: path)))
guard let raw = buffer, let bitmap = NSBitmapImageRep(data: raw),
  let cg = bitmap.cgImage else {
  fputs("Unable to decode visual frame.\n", stderr)
  exit(4)
}
let request = VNRecognizeTextRequest()
request.recognitionLevel = .fast
request.usesLanguageCorrection = false
try VNImageRequestHandler(cgImage: cg, options: [:]).perform([request])
let candidates = (request.results ?? []).compactMap { observation in
  observation.topCandidates(1).first
}.filter { $0.confidence >= 0.20 }
let text = candidates.map { $0.string }.joined(separator: " ")
let confidence = candidates.isEmpty ? 0 : Double(candidates.reduce(Float(0)) {
  $0 + $1.confidence
}) / Double(candidates.count)
let payload: [String: Any] = ["text": text,
  "confidence": confidence, "lineCount": candidates.count,
  "kind": "vision-ocr", "engine": "Apple Vision"]
let encoded = try JSONSerialization.data(withJSONObject: payload, options: [.sortedKeys])
print(String(decoding: encoded, as: UTF8.self))
