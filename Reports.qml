pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io

QtObject {
  id: root
  property var data: ({ items: [], unread: 0, total: 0, automatic: true, checked: "", owner: "", truncated: false, url: "https://github.com/issues" })
  property string error: ""
  property bool loaded: false
  property bool busy: false
  property bool started: false
  property string action: ""
  property var pending: []
  readonly property string helperPath: decodeURIComponent(String(Qt.resolvedUrl("backend.py")).replace(/^file:\/\//, ""))

  function start() {
    if (started) return
    started = true
    run(["load"])
  }

  function run(args) {
    if (busy) {
      if (args[0] !== "poll") {
        if (pending.length < 20) pending = pending.concat([args])
        else error = "Too many pending actions. Wait for the refresh to finish and try again."
      }
      return
    }
    action = args[0]
    busy = true
    helper.command = ["/usr/bin/timeout", "--kill-after=2s", "290s", "python3", helperPath].concat(args)
    helper.running = true
    startup.restart()
  }

  property Process helper: Process {
    stdout: StdioCollector { id: output; waitForEnd: true }
    stderr: StdioCollector { waitForEnd: true }
    onStarted: startup.stop()
    onExited: function(exitCode) {
      startup.stop()
      root.busy = false
      try {
        if (output.text.length > 4000000) throw new Error("Report response exceeds the size limit.")
        var payload = JSON.parse(output.text)
        if (exitCode !== 0 || payload.error) {
          root.error = payload.error || "The report helper timed out or failed."
        } else {
          root.data = payload
          root.loaded = true
          root.error = ""
        }
      } catch (error) {
        root.error = "Could not read the report helper response."
      }
      if (root.action === "load" && !root.error) {
        Qt.callLater(function() { root.run(["poll"]) })
      } else if (root.pending.length > 0) {
        var next = root.pending[0]
        root.pending = root.pending.slice(1)
        Qt.callLater(function() { root.run(next) })
      }
    }
  }

  property Timer startup: Timer {
    interval: 3000
    onTriggered: {
      helper.running = false
      root.busy = false
      root.error = "Could not start the report helper. Check that python3 and timeout are installed."
    }
  }

  property Timer timer: Timer {
    interval: 300000
    repeat: true
    running: root.started && root.loaded && root.data.automatic
    onTriggered: root.run(["poll"])
  }
}
