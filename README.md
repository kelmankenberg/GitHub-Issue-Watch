# OmaRepoReports

A theme-aware bar icon and popup for **all open issues in repositories owned by
the GitHub account authenticated with `gh`**, including private repositories
available to that account. Pull requests are excluded. Organization-owned and
collaborator repositories, Discussions, and off-GitHub feedback are not included.

![OmaRepoReports showing issue summaries, unread activity, and per-report read/unread controls](preview.png)

*Preview uses demonstration reports.*

Requires Omarchy's Quickshell plugin API, Python 3, GNU `timeout`, and GitHub CLI.

## Install

```sh
omarchy plugin add https://github.com/kelmankenberg/OmaRepoReport.git --enable
```

The GitHub icon appears on the right side of the bar. Sign into GitHub CLI as
described below, then click the icon to view your reports.

## GitHub sign-in

**You must be signed into GitHub CLI (`gh`). Being signed into GitHub in a web
browser alone is not enough.** OmaRepoReports automatically uses the active
local GitHub CLI account; no username needs to be configured.

If GitHub CLI is not signed in, run this in a terminal:

```sh
gh auth login --hostname github.com
```

Then click **Refresh** in OmaRepoReports. If you already use `gh`, no additional
sign-in is needed. Use `gh auth status` to check your account. The popup displays
the account it is using and explains the CLI sign-in requirement.

## Use

- Left-click the GitHub icon for a summary, filters, repository/title search,
  and direct report links. Right-click opens the cross-repository GitHub search;
  middle-click refreshes.
- The badge counts open reports with unread activity, **not** total open reports.
  Existing reports start unread. Opening a report or selecting **Mark all
  reviewed** acknowledges its current update timestamp. Later comments or edits
  make it unread again. Acknowledgment is local; it does not change GitHub
  notification state or post anything.
- Each report has a **Mark read** / **Mark unread** button that changes its local
  status without opening the browser, plus an always-visible **Read** / **Unread**
  label. Unread reports also have a colored dot and bold title. The badge updates
  immediately, and manual unread status survives refreshes and shell restarts.
- The first launch checks GitHub, then polls every five minutes. Disable
  **Check GitHub automatically every 5 minutes** to use manual refresh only.
  A paused preference survives shell restarts. Polling is shared across monitors.
- All labels are accepted; common `bug` and `enhancement` / `feature request`
  labels categorize reports. Everything else remains visible under Other.
- GitHub Search limits retrieval to 1,000 issues. The popup discloses truncation;
  total open count and the GitHub link still cover every owned repository.
  Closed reports disappear on refresh; activity on closed issues is not tracked.
- On errors, the previous results remain visible and an `!` badge indicates
  failure. The footer shows the last successful check.

No separate access token, webhook, GitHub Watch subscription, or system service
is needed. No issue bodies or credentials are stored. Issue titles, URLs,
timestamps, and local review state are saved privately under
`${XDG_STATE_HOME:-~/.local/state}/omarchy-github-reports/state.json`.

## Report a bug or suggest a feature

Use **Report a plugin bug** or **Request a plugin feature** in the popup to open
the matching GitHub issue form. These actions submit feedback about
**OmaRepoReports itself**, not the repositories you are monitoring.

You can also open a [bug report](https://github.com/kelmankenberg/OmaRepoReport/issues/new?template=bug_report.yml)
or [feature request](https://github.com/kelmankenberg/OmaRepoReport/issues/new?template=feature_request.yml)
directly. Sign into GitHub in your browser to submit the form; the plugin does
not post issues automatically. Never include tokens, credentials, or private
repository details in a public report.

## Local installation

Copy this folder (not a symlink) to
`~/.config/omarchy/plugins/kel.github-reports`, then run:

```sh
omarchy plugin validate ~/.config/omarchy/plugins/kel.github-reports
omarchy plugin enable kel.github-reports --section right
```

Only the installed copy is live; copy changed source files there after editing.
If the shell still displays old controls after a plugin reload, run
`omarchy restart shell` to clear the running shell's cached QML.

```sh
python3 -m unittest discover -s tests -v
omarchy-shell kel.github-reports status
```
