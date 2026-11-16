import copy
import contextlib
import datetime as dt
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("backend", Path(__file__).parents[1] / "backend.py")
backend = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(backend)


def node(identifier="I_1", title="A report", labels=None):
    return {
        "id": identifier, "number": 7, "title": title,
        "url": "https://github.com/example/app/issues/7",
        "repository": {"nameWithOwner": "example/app"},
        "updatedAt": "2026-11-16T17:00:00Z",
        "labels": {"nodes": [{"name": label} for label in labels or []]},
    }


def page(nodes, more=False, cursor=None, total=None):
    return {"data": {"viewer": {"login": "example"}, "search": {
        "issueCount": len(nodes) if total is None else total, "nodes": nodes,
        "pageInfo": {"hasNextPage": more, "endCursor": cursor},
    }}}


class ReportsTest(unittest.TestCase):
    def test_paginated_reports_include_unlabeled_and_markup_is_literal(self):
        pages = [page([node(labels=["bug"])], True, "next", 2),
                 page([node("I_2", '<img src="https://invalid/tracker">')], total=2)]
        calls = []

        def request(args):
            calls.append(args)
            return pages.pop(0)

        rows, total = backend.fetch_reports("example", request)
        self.assertEqual(total, 2)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]["title"], '<img src="https://invalid/tracker">')
        self.assertEqual(rows[1]["kind"], "other")
        self.assertIn("cursor=next", calls[1])
        self.assertIn("search=is:issue is:open user:example sort:updated-desc", calls[0])

    def test_badge_survives_reload_and_tracks_changes_not_refreshes(self):
        state = backend.empty_state()
        state.update(owner="example", items=[backend.normalize_issue(node(), "example")], total=1)
        self.assertEqual(backend.view(state)["unread"], 1)
        state = backend.mark_reviewed(state, "I_1")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            backend.save_state(path, state)
            state = backend.load_state(path)
        self.assertEqual(backend.view(state)["unread"], 0)
        state["items"][0]["updated"] = "2026-11-16T18:00:00+00:00"
        self.assertEqual(backend.view(state)["unread"], 1)
        self.assertEqual(backend.view(backend.mark_reviewed(state, "all"))["unread"], 0)

    def test_refresh_prunes_closed_reports_and_resets_review_on_account_change(self):
        state = backend.empty_state()
        state.update(owner="old-owner", seen={"I_1": "2026-11-16T17:00:00+00:00",
                                            "closed": "2026-11-16T17:00:00+00:00"})
        replies = [{"login": "example"}, page([node()])]
        updated = backend.refresh(state, request=lambda args: replies.pop(0))
        self.assertEqual(updated["seen"], {})
        self.assertEqual(backend.view(updated)["unread"], 1)
        self.assertEqual(state["owner"], "old-owner")

    def test_individual_read_unread_actions_persist_without_affecting_other_reports(self):
        state = backend.empty_state()
        state.update(owner="example", total=2, items=[
            backend.normalize_issue(node(identifier), "example") for identifier in ("I_1", "I_2")
        ])
        state = backend.mark_reviewed(state, "all")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "omarchy-github-reports"
            path.mkdir()
            backend.save_state(path / "state.json", state)
            for action, expected in [("unread", True), ("read", False), ("unread", True)]:
                with self.subTest(action=action), \
                        patch.dict("os.environ", {"XDG_STATE_HOME": directory}), \
                        patch("sys.argv", ["backend.py", action, "I_1"]), \
                        contextlib.redirect_stdout(io.StringIO()) as output, \
                        patch.object(backend, "gh_json", side_effect=AssertionError("Unexpected network access")):
                    self.assertEqual(backend.main(), 0)
                    self.assertEqual(json.loads(output.getvalue())["unread"], int(expected))
                state = backend.load_state(path / "state.json")
                rows = backend.view(state)["items"]
                self.assertEqual([row["unread"] for row in rows], [expected, False])
            replies = [{"login": "example"}, page([node("I_1"), node("I_2")])]
            refreshed = backend.refresh(state, request=lambda args: replies.pop(0))
            self.assertEqual([row["unread"] for row in backend.view(refreshed)["items"]], [True, False])

    def test_read_unread_reject_missing_reports_without_altering_state(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "omarchy-github-reports"
            path.mkdir()
            backend.save_state(path / "state.json", backend.empty_state())
            before = (path / "state.json").read_bytes()
            for action in ("read", "unread"):
                with self.subTest(action=action), \
                        patch.dict("os.environ", {"XDG_STATE_HOME": directory}), \
                        patch("sys.argv", ["backend.py", action, "missing"]), \
                        contextlib.redirect_stdout(io.StringIO()) as output:
                    self.assertEqual(backend.main(), 1)
                    self.assertIn("error", json.loads(output.getvalue()))
                    self.assertEqual((path / "state.json").read_bytes(), before)

    def test_failed_refresh_does_not_mutate_previous_results(self):
        state = backend.empty_state()
        before = copy.deepcopy(state)

        def request(args):
            if args == ["user"]:
                return {"login": "example"}
            raise backend.ReportError("Offline")

        with self.assertRaises(backend.ReportError):
            backend.refresh(state, request=request)
        self.assertEqual(state, before)

    def test_rejects_untrusted_navigation_and_missing_timestamp(self):
        for changes in [
            {"url": "https://evil.example/app/issues/7"},
            {"url": "javascript:alert(1)"},
            {"updatedAt": "not-a-date"},
            {"updatedAt": "2026-11-16T17:00:00"},
            {"repository": {"nameWithOwner": "someone-else/app"}},
            {"repository": None},
            {"labels": None},
        ]:
            with self.subTest(changes=changes), self.assertRaises(backend.ReportError):
                backend.normalize_issue({**node(), **changes}, "example")

    def test_bad_pagination_and_account_switch_are_reported(self):
        for reply in [
            {"data": []},
            {"data": {"viewer": {"login": "someone-else"}}},
            page([node()], more=True, cursor=None),
        ]:
            with self.subTest(reply=reply), self.assertRaises(backend.ReportError):
                backend.fetch_reports("example", lambda args: reply)

    def test_thousand_result_limit_is_explicit(self):
        calls = []

        def request(args):
            calls.append(args)
            return page([node(f"I_{len(calls)}")], more=True, cursor="next", total=1001)

        rows, total = backend.fetch_reports("example", request)
        state = backend.empty_state()
        state.update(owner="example", items=rows, total=total)
        self.assertEqual(len(calls), 10)
        self.assertEqual(total, 1001)
        self.assertTrue(backend.view(state)["truncated"])

    def test_categories_and_truncated_search(self):
        self.assertEqual(backend.normalize_issue(node(labels=["enhancement"]), "example")["kind"], "feature")
        self.assertEqual(backend.normalize_issue(node(labels=["type: bug"]), "example")["kind"], "bug")
        state = backend.empty_state()
        state.update(owner="example", total=1001)
        self.assertTrue(backend.view(state)["truncated"])
        self.assertIn("user%3Aexample", backend.view(state)["url"])

    def test_corrupt_cache_is_not_silently_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            path.write_text(json.dumps({"version": 99}))
            with self.assertRaises(backend.ReportError):
                backend.load_state(path)

    def test_paused_poll_does_not_contact_github_and_manual_refresh_still_works(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "omarchy-github-reports"
            path.mkdir()
            state = backend.empty_state()
            state["automatic"] = False
            backend.save_state(path / "state.json", state)
            with patch.dict("os.environ", {"XDG_STATE_HOME": directory}), \
                    patch.object(backend, "refresh", return_value=state) as refresh, \
                    contextlib.redirect_stdout(io.StringIO()):
                with patch("sys.argv", ["backend.py", "poll"]):
                    self.assertEqual(backend.main(), 0)
                    refresh.assert_not_called()
                with patch("sys.argv", ["backend.py", "refresh"]):
                    self.assertEqual(backend.main(), 0)
                    refresh.assert_called_once()
            self.assertFalse(backend.load_state(path / "state.json")["automatic"])

    def test_existing_cache_keeps_review_history_and_paused_preference(self):
        state = backend.empty_state()
        state.update(owner="example", automatic=False, total=1,
                     items=[backend.normalize_issue(node(), "example")])
        state = backend.mark_reviewed(state, "all")
        for key in ("refreshMinutes", "badgeEnabled", "desktopNotifications"):
            state.pop(key)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            backend.save_state(path, state)
            migrated = backend.load_state(path)
        self.assertFalse(migrated["automatic"])
        self.assertEqual(migrated["refreshMinutes"], 5)
        self.assertTrue(migrated["badgeEnabled"])
        self.assertFalse(migrated["desktopNotifications"])
        self.assertEqual(backend.view(migrated)["unread"], 0)

    def test_two_hour_schedule_waits_until_due_and_manual_mode_stops_polling(self):
        checked = dt.datetime(2026, 11, 16, 17, tzinfo=dt.timezone.utc)
        state = backend.empty_state()
        state.update(checked=checked.isoformat(), refreshMinutes=120)
        self.assertFalse(backend.refresh_due(state, checked + dt.timedelta(minutes=119, seconds=59)))
        self.assertTrue(backend.refresh_due(state, checked + dt.timedelta(hours=2)))
        state["automatic"] = False
        self.assertFalse(backend.refresh_due(state, checked + dt.timedelta(days=1)))

    def test_schedule_and_notification_preferences_persist_without_affecting_reports(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "omarchy-github-reports"
            path.mkdir()
            state = backend.empty_state()
            state.update(owner="example", total=1, items=[backend.normalize_issue(node(), "example")])
            backend.save_state(path / "state.json", state)
            for action, value in [("schedule", "120"), ("badge", "off"),
                                  ("notifications", "on"), ("schedule", "0")]:
                with patch.dict("os.environ", {"XDG_STATE_HOME": directory}), \
                        patch("sys.argv", ["backend.py", action, value]), \
                        patch.object(backend, "refresh", side_effect=AssertionError("Unexpected network access")), \
                        contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(backend.main(), 0)
            updated = backend.load_state(path / "state.json")
            self.assertFalse(updated["automatic"])
            self.assertEqual(updated["refreshMinutes"], 120)
            self.assertFalse(updated["badgeEnabled"])
            self.assertTrue(updated["desktopNotifications"])
            self.assertEqual(updated["items"], state["items"])
            self.assertEqual(backend.view(updated)["unread"], 1)

    def test_invalid_schedules_and_preferences_do_not_overwrite_state(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "omarchy-github-reports"
            path.mkdir()
            backend.save_state(path / "state.json", backend.empty_state())
            before = (path / "state.json").read_bytes()
            for action, value in [("schedule", "121"), ("schedule", "1"), ("schedule", "-5"),
                                  ("schedule", "5.0"), ("schedule", "bad"), ("notifications", "yes")]:
                with self.subTest(action=action, value=value), \
                        patch.dict("os.environ", {"XDG_STATE_HOME": directory}), \
                        patch("sys.argv", ["backend.py", action, value]), \
                        contextlib.redirect_stdout(io.StringIO()) as output:
                    self.assertEqual(backend.main(), 1)
                    self.assertIn("error", json.loads(output.getvalue()))
                    self.assertEqual((path / "state.json").read_bytes(), before)

    def test_notification_activity_counts_only_new_or_updated_reports_after_first_check(self):
        state = backend.empty_state()
        state.update(owner="example", checked="2026-11-16T17:00:00+00:00",
                     items=[backend.normalize_issue(node(), "example")], total=1)
        updated = copy.deepcopy(state)
        updated["items"][0]["updated"] = "2026-11-16T18:00:00+00:00"
        updated["items"].append(backend.normalize_issue(node("I_2", '<img src="https://invalid/tracker">'), "example"))
        self.assertEqual(backend.new_activity(state, updated), 2)
        self.assertEqual(backend.new_activity(state, backend.mark_reviewed(state, "all")), 0)
        self.assertEqual(backend.new_activity(backend.empty_state(), updated), 0)
        updated["owner"] = "different-account"
        self.assertEqual(backend.new_activity(state, updated), 0)

    def test_untrusted_text_never_reaches_auto_text_or_shared_tooltip(self):
        root = Path(__file__).parents[1]
        widget = (root / "BarWidget.qml").read_text()
        plain = (root / "PlainText.qml").read_text()
        self.assertIn("textFormat: Text.PlainText", plain)
        self.assertIn("textFormat: Text.PlainText", widget)
        tooltip = widget.split("tooltipText:", 1)[1].split("onPressed:", 1)[0]
        self.assertNotIn(".title", tooltip)
        self.assertNotIn("Reports.error\n", tooltip)
        self.assertNotIn("omarchy-notification", widget)


if __name__ == "__main__":
    unittest.main()
