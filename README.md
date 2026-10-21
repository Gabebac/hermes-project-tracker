# Project Tracker

Hermes desktop plugin: the projects routine — Ongoing (Business, never drops) /
Building / Maintenance / Ideas / Done, with staleness flags for the Sunday review,
per-project done/left checklists and 1-hour session logging.

- Desktop: a **Projects** tab at `/projects` (sidebar + ⌘K "Open Projects")
- Agent tools: `project_add`, `project_set`, `project_log`, `project_item`, `projects_list`, `projects_review`, `projects_brief`
- **Refresh evidence** button (Projects page + right-rail): re-runs the evidence pass on demand —
  reads the pinned and recent desktop sessions from the app's `state.db` (read-only), raises work
  that was never logged, and refreshes the interview questions. Writes `review_brief.json`/`.md`
  to plugin data so a manual interview can reuse the same evidence (`projects_brief` tool).
- Store: plugin-data JSON, shared by the tab and the agent tools

## Install

Desktop app → plugins → Install from Git → `https://github.com/Gabebac/hermes-project-tracker` with **Desktop target checked** (or `hermes plugins install <url>` backend-side).

## Interview evidence

`GET /brief` (also the `projects_brief` tool) builds the weekly-update evidence packet: pinned + recent
sessions (7-day window, `PROJECT_TRACKER_STATE_DB` overridable), unlogged-work candidates matched by
project name, staleness flags, the five question stages with current data, and a pre-rendered `brief`
the Projects tab submits when you press ☻ Interview. Manual runs: say "run Pooh's projects interview"
and call `projects_brief` first — same evidence, no stale questions.
