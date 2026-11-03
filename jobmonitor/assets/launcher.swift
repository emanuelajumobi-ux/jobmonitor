// Hauptprogramm von Job-Monitor.app (von `make app` übersetzt).
//   ohne Argumente:            startet das App-Fenster über Contents/Resources/start.sh (wie bisher das zsh-Skript)
//   --notify <Titel> <Text>:   Mitteilung im Namen der App (benachrichtigung.py ruft das über `open -n -g` auf)
// Mitteilungen gehen nur aus einer über LaunchServices gestarteten App mit laufender NSApplication; deshalb steckt das
// hier im Hauptprogramm. Beim ersten Mal fragt macOS, ob Job-Monitor Mitteilungen senden darf. Ein Klick auf die
// Mitteilung startet die App ohne Argumente, also das Fenster. Auf stderr: NICHT_ERLAUBT bzw. die Fehlermeldung.
import AppKit
import UserNotifications

func fehler(_ text: String) {
    FileHandle.standardError.write("\(text)\n".data(using: .utf8)!)
}

let args = CommandLine.arguments
if let i = args.firstIndex(of: "--notify"), args.count >= i + 3 {
    let app = NSApplication.shared
    app.setActivationPolicy(.accessory)          // kein Dock-Symbol, kein Fenster
    let center = UNUserNotificationCenter.current()
    func ende(_ code: Int32) { DispatchQueue.main.async { exit(code) } }
    center.requestAuthorization(options: [.alert, .sound]) { granted, error in
        if let error = error { fehler(error.localizedDescription) }
        guard granted else {
            fehler("NICHT_ERLAUBT")
            return ende(2)
        }
        let content = UNMutableNotificationContent()
        content.title = args[i + 1]
        content.body = args[i + 2]
        content.sound = .default
        center.add(UNNotificationRequest(identifier: UUID().uuidString, content: content, trigger: nil)) { error in
            if let error = error { fehler(error.localizedDescription) }
            ende(error == nil ? 0 : 1)
        }
    }
    DispatchQueue.main.asyncAfter(deadline: .now() + 120) { fehler("Zeitüberschreitung"); exit(1) }
    app.run()
}

let script = Bundle.main.bundleURL.appendingPathComponent("Contents/Resources/start.sh").path
let argv: [UnsafeMutablePointer<CChar>?] = [strdup("/bin/zsh"), strdup(script), nil]
execv("/bin/zsh", argv)
fehler("start.sh nicht ausführbar: \(script)")
exit(1)
