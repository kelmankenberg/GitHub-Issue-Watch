import datetime as dt
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).parents[1]
SHELL = Path("/usr/share/omarchy/shell")
QUICKSHELL = shutil.which("quickshell")


@unittest.skipUnless(QUICKSHELL and (SHELL / "Commons").is_dir(),
                     "Requires Omarchy and Quickshell")
class LifecycleTest(unittest.TestCase):
    def test_last_widget_stops_polling_and_can_restart_during_cancellation(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory)
            for name in ("Commons", "Ui"):
                (fixture / name).symlink_to(SHELL / name, target_is_directory=True)
            template = (ROOT / "tests/lifecycle.qml.in").read_text()
            (fixture / "shell.qml").write_text(template.replace("@PLUGIN_URL@", ROOT.as_uri()))
            state = fixture / "state/omarchy-github-reports"
            state.mkdir(parents=True, mode=0o700)
            (state / "state.json").write_text(json.dumps({
                "version": 1, "owner": "example", "items": [], "seen": {}, "total": 0,
                "checked": dt.datetime.now(dt.timezone.utc).isoformat(),
                "automatic": True, "refreshMinutes": 120,
                "badgeEnabled": True, "desktopNotifications": True,
            }))
            result = subprocess.run(
                [QUICKSHELL, "--no-color", "-p", str(fixture / "shell.qml")],
                env={**os.environ, "QT_QPA_PLATFORM": "offscreen",
                     "XDG_STATE_HOME": str(fixture / "state")},
                capture_output=True, text=True, timeout=20,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("LIFECYCLE PASSED", result.stdout + result.stderr)
