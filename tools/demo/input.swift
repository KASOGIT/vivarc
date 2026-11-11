// Real macOS input for the demo recording (a visible, eased pointer; CDP input shows no cursor).
// Commands, chained with ';':
//   move X Y [ms] | click X Y [ms] | rclick X Y | scroll STEPS DY | key KEYCODE [cmd,alt,ctrl,shift] | type TEXT | wait MS
// X/Y are screen points. `type` takes lowercase letters, digits 1-2, space and '.'.
import Foundation
import CoreGraphics

let src = CGEventSource(stateID: .hidSystemState)
func pos() -> CGPoint { CGEvent(source: nil)!.location }
func post(_ type: CGEventType, _ p: CGPoint, _ button: CGMouseButton = .left) {
  CGEvent(mouseEventSource: src, mouseType: type, mouseCursorPosition: p, mouseButton: button)?.post(tap: .cghidEventTap)
}
func move(_ x: Double, _ y: Double, _ ms: Double) {
  let a = pos(); let steps = max(1, Int(ms / 8))
  for i in 1...steps {
    var t = Double(i) / Double(steps); t = t < 0.5 ? 2 * t * t : 1 - pow(-2 * t + 2, 2) / 2
    post(.mouseMoved, CGPoint(x: a.x + (x - a.x) * t, y: a.y + (y - a.y) * t))
    usleep(8000)
  }
}
func press(_ x: Double, _ y: Double, right: Bool) {
  let p = CGPoint(x: x, y: y)
  post(right ? .rightMouseDown : .leftMouseDown, p, right ? .right : .left)
  usleep(60000)
  post(right ? .rightMouseUp : .leftMouseUp, p, right ? .right : .left)
}
func flags(_ s: String) -> CGEventFlags {
  var f = CGEventFlags()
  for m in s.split(separator: ",") {
    switch m { case "cmd": f.insert(.maskCommand); case "alt": f.insert(.maskAlternate)
    case "ctrl": f.insert(.maskControl); case "shift": f.insert(.maskShift); default: break }
  }
  return f
}
func key(_ code: UInt16, _ f: CGEventFlags) {
  for down in [true, false] {
    let e = CGEvent(keyboardEventSource: src, virtualKey: code, keyDown: down)!
    e.flags = f; e.post(tap: .cghidEventTap); usleep(30000)
  }
}
// Vivaldi drops key events that only carry a unicode string, so text is typed with real key codes (US layout).
let codes: [Character: UInt16] = ["a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7, "c": 8, "v": 9,
  "b": 11, "q": 12, "w": 13, "e": 14, "r": 15, "y": 16, "t": 17, "o": 31, "u": 32, "i": 34, "p": 35, "l": 37,
  "j": 38, "k": 40, "n": 45, "m": 46, " ": 49, ".": 47, "1": 18, "2": 19]
func type(_ text: String) {
  for ch in text {
    key(codes[ch]!, CGEventFlags())
    usleep(UInt32(35000 + Int.random(in: 0...25000)))
  }
}
for cmd in CommandLine.arguments.dropFirst().joined(separator: " ").split(separator: ";") {
  let p = cmd.trimmingCharacters(in: .whitespaces).split(separator: " ", maxSplits: 1).map(String.init)
  guard let op = p.first else { continue }
  let rest = p.count > 1 ? p[1] : ""
  let n = rest.split(separator: " ").compactMap { Double($0) }
  switch op {
  case "move": move(n[0], n[1], n.count > 2 ? n[2] : 500)
  case "click": move(n[0], n[1], n.count > 2 ? n[2] : 500); usleep(80000); press(n[0], n[1], right: false)
  case "rclick": move(n[0], n[1], 400); usleep(80000); press(n[0], n[1], right: true)
  case "scroll":
    for _ in 0..<Int(n[0]) {
      CGEvent(scrollWheelEvent2Source: src, units: .pixel, wheelCount: 1, wheel1: Int32(n[1]), wheel2: 0, wheel3: 0)?.post(tap: .cghidEventTap)
      usleep(16000)
    }
  case "key": let k = rest.split(separator: " "); key(UInt16(k[0])!, flags(k.count > 1 ? String(k[1]) : ""))
  case "type": type(rest)
  case "wait": usleep(UInt32(n[0] * 1000))
  default: FileHandle.standardError.write("unknown \(op)\n".data(using: .utf8)!)
  }
}
