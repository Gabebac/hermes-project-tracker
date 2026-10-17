"""Project Tracker — Hermes plugin.

Owns the projects routine: the lifecycle store behind the vault's [[Projects]]
note and the Projects desktop tab. The agent logs sessions as they happen and
prepares staleness evidence for the Sunday review; the desktop tab shows the
live state.

Components:
- service.py          store + staleness rules + review builder (this file's sibling)
- tools.py            agent-facing tools
- dashboard/plugin_api.py  REST for the desktop tab (same store as the tools)
- desktop/plugin.js   Projects tab for the Hermes desktop app

Layout (plugin_data_dir("project-tracker")):
    projects.json    one record per project
    sessions.jsonl   appended session log (also written by project_log)
"""

from __future__ import annotations


def register(ctx) -> None:
    from . import tools as t

    for item in t.TOOL_DEFS:
        ctx.register_tool(
            name=item["name"],
            toolset="project-tracker",
            schema={
                "name": item["name"],
                "description": item["description"],
                "parameters": item["parameters"],
            },
            handler=item["handler"],
            description=item["description"],
            emoji="\U0001F4E6",
        )


__all__ = ["register"]


def _demo() -> None:  # pragma: no cover - manual smoke check
    # Load the service module directly (package id has a dash, so no plain import)
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "project_tracker_service", Path(__file__).parent / "service.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    p = {"name": "X", "label": "App", "section": "Building",
         "last_update": "2026-01-01", "created": "2026-01-01"}
    assert mod.evaluate_staleness(p, today="2026-01-20")["stale"] is True
    assert mod.evaluate_staleness(p, today="2026-01-10")["stale"] is False
    biz = dict(p, label="Business", section="Ongoing (Business)")
    assert mod.evaluate_staleness(biz, today="2027-01-01")["stale"] is False
    idea = dict(p, label="Idea", section="Ideas", promote_by="2026-01-10")
    r = mod.evaluate_staleness(idea, today="2026-01-20")
    assert r["stale"] is True and r["days_idle"] == 10
    print("project-tracker self-check OK")


if __name__ == "__main__":
    _demo()