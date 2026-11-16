#!/usr/bin/env python3
"""Read GitHub reports using gh's existing authentication; never store tokens."""

import argparse
import copy
import datetime as dt
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib.parse import urlencode

LIMIT = 1000
REFRESH_MINUTES = (5, 10, 15, 30, 60, 120)
MAX_STATE = 4_000_000
PLUGIN_VERSION = json.loads(Path(__file__).with_name("manifest.json").read_text())["version"]
OWNER = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})\Z")
REPOSITORY = re.compile(r"[A-Za-z0-9-]+/[A-Za-z0-9_.-]+\Z")
ISSUE_URL = re.compile(r"https://github\.com/[A-Za-z0-9-]+/[A-Za-z0-9_.-]+/issues/[1-9][0-9]*\Z")
QUERY = """
query($search: String!, $cursor: String) {
  viewer { login }
  search(query: $search, type: ISSUE, first: 100, after: $cursor) {
    issueCount
    pageInfo { hasNextPage endCursor }
    nodes {
      ... on Issue {
        id number title url updatedAt
        repository { nameWithOwner }
        labels(first: 30) { nodes { name } }
      }
    }
  }
}
"""


class ReportError(Exception):
    pass


def timestamp(value):
    if not isinstance(value, str) or len(value) > 40:
        raise ReportError("GitHub returned an invalid timestamp.")
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("Missing timezone")
        return parsed.astimezone(dt.timezone.utc).isoformat()
    except ValueError as error:
        raise ReportError("GitHub returned an invalid timestamp.") from error


def gh_json(args):
    try:
        result = subprocess.run(
            ["gh", "api", "--hostname", "github.com", *args],
            capture_output=True, timeout=25, check=False,
            env={**os.environ, "GH_PROMPT_DISABLED": "1", "GH_PAGER": "cat"},
        )
    except FileNotFoundError as error:
        raise ReportError("GitHub CLI is missing. Install gh, then run gh auth login.") from error
    except subprocess.TimeoutExpired as error:
        raise ReportError("GitHub timed out. Your previous reports have been kept.") from error
    if result.returncode:
        # Do not echo gh's response: it can contain account or credential details.
        raise ReportError("GitHub request failed. Check your connection, API limits, and gh auth status.")
    if len(result.stdout) > 1_000_000:
        raise ReportError("GitHub returned an oversized response.")
    try:
        payload = json.loads(result.stdout)
    except (ValueError, UnicodeError) as error:
        raise ReportError("GitHub returned invalid JSON.") from error
    if not isinstance(payload, dict) or payload.get("errors"):
        raise ReportError("GitHub could not complete the request. Check API limits and account access.")
    return payload


def normalize_issue(node, owner):
    if not isinstance(node, dict):
        raise ReportError("GitHub returned an invalid report.")
    repository = node.get("repository")
    label_data = node.get("labels")
    if not isinstance(repository, dict) or not isinstance(label_data, dict):
        raise ReportError("GitHub returned invalid repository or label data.")
    repo = repository.get("nameWithOwner", "")
    url = node.get("url", "")
    number = node.get("number")
    title = node.get("title")
    identifier = node.get("id")
    if (not isinstance(repo, str) or not REPOSITORY.fullmatch(repo)
            or repo.split("/")[0].lower() != owner.lower()
            or not isinstance(url, str) or not ISSUE_URL.fullmatch(url)
            or type(number) is not int or number < 1
            or url != f"https://github.com/{repo}/issues/{number}"
            or not isinstance(title, str) or len(title) > 1024
            or not isinstance(identifier, str) or not 1 <= len(identifier) <= 200):
        raise ReportError("GitHub returned an invalid report.")
    labels = label_data.get("nodes")
    if not isinstance(labels, list) or len(labels) > 30:
        raise ReportError("GitHub returned invalid labels.")
    names = []
    for label in labels:
        name = label.get("name") if isinstance(label, dict) else None
        if not isinstance(name, str) or len(name) > 100:
            raise ReportError("GitHub returned an invalid label.")
        names.append(name.lower())
    kind = "other"
    if any(name in {"bug", "bug report", "type: bug", "type:bug"} for name in names):
        kind = "bug"
    elif any(name in {"enhancement", "feature", "feature request", "feature-request",
                      "type: feature", "type:feature"} for name in names):
        kind = "feature"
    return {
        "id": identifier, "number": number, "title": title, "repository": repo,
        "url": url, "updated": timestamp(node.get("updatedAt")), "kind": kind,
    }


def fetch_reports(owner, request=gh_json):
    if not OWNER.fullmatch(owner):
        raise ReportError("GitHub returned an invalid account name.")
    items = {}
    cursor = None
    total = 0
    for _ in range(LIMIT // 100):
        args = ["graphql", "-f", f"query={QUERY}", "-f",
                f"search=is:issue is:open user:{owner} sort:updated-desc"]
        if cursor:
            args += ["-f", f"cursor={cursor}"]
        payload = request(args)
        data = payload.get("data")
        if not isinstance(data, dict) or not isinstance(data.get("viewer"), dict):
            raise ReportError("GitHub returned invalid account data.")
        viewer = data["viewer"].get("login")
        if not isinstance(viewer, str) or viewer.lower() != owner.lower():
            raise ReportError("The GitHub account changed during refresh. Please refresh again.")
        search = data.get("search")
        if not isinstance(search, dict) or not isinstance(search.get("pageInfo"), dict):
            raise ReportError("GitHub returned invalid search data.")
        total = search.get("issueCount")
        nodes = search.get("nodes")
        page = search["pageInfo"]
        if (type(total) is not int or total < 0 or not isinstance(nodes, list)
                or len(nodes) > 100 or type(page.get("hasNextPage")) is not bool):
            raise ReportError("GitHub returned an invalid report list.")
        for node in nodes:
            issue = normalize_issue(node, owner)
            items[issue["id"]] = issue
        if not page["hasNextPage"]:
            break
        cursor = page.get("endCursor")
        if not isinstance(cursor, str) or not 1 <= len(cursor) <= 1024:
            raise ReportError("GitHub returned an invalid page cursor.")
    rows = sorted(items.values(), key=lambda issue: issue["updated"], reverse=True)
    return rows, total


def empty_state():
    return {"version": 1, "owner": "", "items": [], "seen": {}, "total": 0,
            "checked": "", "automatic": True, "refreshMinutes": 5,
            "badgeEnabled": True, "desktopNotifications": False}


def load_state(path):
    if not path.exists():
        return empty_state()
    if path.stat().st_size > MAX_STATE:
        raise ReportError("The report cache is too large. Move state.json aside to rebuild it.")
    try:
        state = json.loads(path.read_text())
        if (not isinstance(state, dict) or state.get("version") != 1
                or not isinstance(state.get("items"), list) or len(state["items"]) > LIMIT
                or not isinstance(state.get("seen"), dict) or len(state["seen"]) > LIMIT
                or type(state.get("automatic")) is not bool
                or not isinstance(state.get("checked"), str)
                or type(state.get("total")) is not int or state["total"] < 0
                or not isinstance(state.get("owner"), str)
                or (state["owner"] and not OWNER.fullmatch(state["owner"]))):
            raise ValueError("Invalid cache structure")
        defaults = empty_state()
        for key in ("refreshMinutes", "badgeEnabled", "desktopNotifications"):
            state.setdefault(key, defaults[key])
        if (type(state["refreshMinutes"]) is not int or state["refreshMinutes"] not in REFRESH_MINUTES
                or type(state["badgeEnabled"]) is not bool
                or type(state["desktopNotifications"]) is not bool):
            raise ValueError("Invalid preferences")
        if state.get("checked"):
            timestamp(state["checked"])
        for issue in state["items"]:
            # Reuse the network validator for persisted text and navigation targets.
            normalize_issue({
                "id": issue["id"], "number": issue["number"], "title": issue["title"],
                "url": issue["url"], "repository": {"nameWithOwner": issue["repository"]},
                "updatedAt": issue["updated"], "labels": {"nodes": []},
            }, state["owner"])
            if issue["kind"] not in {"bug", "feature", "other"}:
                raise ValueError("Invalid category")
        for key, value in state["seen"].items():
            if not isinstance(key, str) or len(key) > 200:
                raise ValueError("Invalid seen identifier")
            timestamp(value)
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        raise ReportError("The report cache is invalid. Move state.json aside to rebuild it.") from error
    return state


def save_state(path, state):
    data = json.dumps(state, ensure_ascii=True)
    if len(data) > MAX_STATE:
        raise ReportError("The report cache exceeds its storage limit.")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def refresh(state, now=None, request=gh_json):
    now = now or dt.datetime.now(dt.timezone.utc)
    owner = request(["user"]).get("login", "")
    if not isinstance(owner, str) or not OWNER.fullmatch(owner):
        raise ReportError("GitHub returned an invalid account name.")
    items, total = fetch_reports(owner, request)
    updated = copy.deepcopy(state)
    seen = state["seen"] if state["owner"].lower() == owner.lower() else {}
    updated.update(owner=owner, items=items, total=total, checked=now.isoformat(),
                   seen={row["id"]: seen[row["id"]] for row in items if row["id"] in seen})
    return updated


def mark_reviewed(state, identifier, reviewed=True):
    updated = copy.deepcopy(state)
    for row in updated["items"]:
        if identifier == "all" or row["id"] == identifier:
            if reviewed:
                updated["seen"][row["id"]] = row["updated"]
            else:
                updated["seen"].pop(row["id"], None)
    return updated


def refresh_due(state, now):
    if not state["automatic"]:
        return False
    return not state["checked"] or (
        now - dt.datetime.fromisoformat(timestamp(state["checked"]))
    ).total_seconds() >= state["refreshMinutes"] * 60


def new_activity(previous, current):
    if not previous["checked"] or previous["owner"].lower() != current["owner"].lower():
        return 0
    known = {row["id"]: row["updated"] for row in previous["items"]}
    return sum(known.get(row["id"]) != row["updated"] for row in current["items"])


def view(state):
    result = {key: value for key, value in state.items() if key != "seen"}
    result["items"] = [
        {**row, "unread": state["seen"].get(row["id"]) != row["updated"]}
        for row in state["items"]
    ]
    result["unread"] = sum(row["unread"] for row in result["items"])
    result["truncated"] = state["total"] > len(state["items"])
    result["refreshOptions"] = [0, *REFRESH_MINUTES]
    result["pluginVersion"] = PLUGIN_VERSION
    result["url"] = "https://github.com/issues?" + urlencode({
        "q": f'is:issue is:open user:{state["owner"]} sort:created-desc',
    }) if state["owner"] else "https://github.com/issues"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=[
        "load", "poll", "refresh", "read", "unread", "automatic", "schedule", "badge", "notifications",
    ])
    parser.add_argument("value", nargs="?")
    args = parser.parse_args()
    directory = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) / "omarchy-github-reports"
    try:
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        with (directory / "state.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            path = directory / "state.json"
            state = load_state(path)
            now = dt.datetime.now(dt.timezone.utc)
            activity = 0
            if args.action == "refresh" or (args.action == "poll" and refresh_due(state, now)):
                previous = state
                state = refresh(previous, now)
                activity = new_activity(previous, state)
                save_state(path, state)
            elif args.action in {"read", "unread"}:
                if not args.value or (args.value != "all" and not any(
                        row["id"] == args.value for row in state["items"])):
                    raise ReportError("The report is no longer in the cache. Refresh and try again.")
                state = mark_reviewed(state, args.value, reviewed=args.action == "read")
                save_state(path, state)
            elif args.action == "schedule":
                if args.value not in {str(value) for value in (0, *REFRESH_MINUTES)}:
                    raise ReportError("Choose manual-only or a supported interval from 5 to 120 minutes.")
                minutes = int(args.value)
                state["automatic"] = minutes != 0
                if minutes:
                    state["refreshMinutes"] = minutes
                save_state(path, state)
            elif args.action in {"automatic", "badge", "notifications"}:
                if args.value not in {"on", "off"}:
                    raise ReportError("This setting must be on or off.")
                key = {"automatic": "automatic", "badge": "badgeEnabled",
                       "notifications": "desktopNotifications"}[args.action]
                state[key] = args.value == "on"
                save_state(path, state)
            print(json.dumps({**view(state), "newActivity": activity}))
    except (ReportError, OSError) as error:
        print(json.dumps({"error": str(error)}))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
