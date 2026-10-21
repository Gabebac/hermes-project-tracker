"""Agent-facing tools for project-tracker. Handlers MUST return JSON strings."""
from __future__ import annotations

import json

try:
    from . import service
except ImportError:  # pragma: no cover - standalone import
    import service


def _run(fn, *a, **kw) -> str:
    try:
        return json.dumps(fn(*a, **kw), ensure_ascii=False)
    except Exception as e:  # noqa: BLE001 - surface errors as data
        return json.dumps({"error": repr(e)})

TOOLS = [
    {
        "name": "projects_list",
        "description": "List all tracked projects with staleness evaluation.",
        "parameters": {"type": "object", "properties": {}, "required": []},
        "handler": lambda args: _run(service.list_projects),
        "summary": "List projects with staleness",
    },
    {
        "name": "projects_review",
        "description": "Sunday review packet: stale flags with evidence (last activity, next action) + review checklist. Decisions belong to Pooh; never drop/park silently.",
        "parameters": {"type": "object", "properties": {}, "required": []},
        "handler": lambda args: _run(service.review),
        "summary": "Staleness review packet",
    },
    {
        "name": "project_add",
        "description": "Track a new project. label: Business|App|Personal|Idea; section: Ongoing (Business)|Building|Maintenance|Ideas|Done.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "label": {"type": "string", "description": "Business|App|Personal|Idea"},
                "section": {"type": "string"},
                "phase": {"type": "string"},
                "next_action": {"type": "string"},
                "note": {"type": "string"},
                "promote_by": {"type": "string", "description": "YYYY-MM-DD, for Ideas"},
                "repo": {"type": "string"},
            },
            "required": ["name"],
        },
        "handler": lambda args: _run(service.add_project, args.get("name", ""),
                                     label=args.get("label", "App"),
                                     section=args.get("section"),
                                     phase=args.get("phase"),
                                     next_action=args.get("next_action"),
                                     note=args.get("note"),
                                     promote_by=args.get("promote_by"),
                                     repo=args.get("repo")),
        "summary": "Add a tracked project",
    },
    {
        "name": "project_set",
        "description": "Update a project's fields (section moves, phase, next_action, note, promote_by...).",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "section": {"type": "string"},
                "phase": {"type": "string"},
                "current_focus": {"type": "string"},
                "next_action": {"type": "string"},
                "note": {"type": "string"},
                "promote_by": {"type": "string"},
                "last_update": {"type": "string"},
                "label": {"type": "string"},
                "repo": {"type": "string"},
            },
            "required": ["name"],
        },
        "handler": lambda args: _run(service.set_project, args.get("name", ""),
                                     **{k: args.get(k) for k in
                                        ("section", "phase", "current_focus", "next_action",
                                         "note", "promote_by", "last_update", "label", "repo")}),
        "summary": "Update a project",
    },
    {
        "name": "project_log",
        "description": "Log a work session on a project (updates last_update). Use whenever Pooh reports project work.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "text": {"type": "string"},
                "date": {"type": "string", "description": "YYYY-MM-DD, default today"},
            },
            "required": ["name", "text"],
        },
        "handler": lambda args: _run(service.log_session, args.get("name", ""), args.get("text", ""),
                                     when=args.get("date")),
        "summary": "Log a session on a project",
    },
    {
        "name": "projects_brief",
        "description": "Fresh evidence pass for the Sunday interview: pinned + recent desktop sessions (read-only), unlogged-work candidates vs the tracker log, stale flags, and the updated interview questions. Returns a pre-rendered 'brief' string for the interview prompt.",
        "parameters": {
            "type": "object",
            "properties": {
                "days": {"type": "number", "description": "look-back window in days, default 7"},
            },
            "required": [],
        },
        "handler": lambda args: _run(service.build_brief, args.get("days", 7)),
        "summary": "Interview evidence brief",
    },
    {
        "name": "project_item",
        "description": "Mutate a project's checklist. action: add|check|uncheck|remove; side: done|left.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "action": {"type": "string", "description": "add|check|uncheck|remove"},
                "side": {"type": "string", "description": "done|left"},
                "text": {"type": "string"},
            },
            "required": ["name", "action", "side", "text"],
        },
        "handler": lambda args: _run(service.project_item, args.get("name", ""),
                                     args.get("action", ""), args.get("side", ""),
                                     args.get("text", "")),
        "summary": "Mutate a checklist item",
    },
]

TOOL_DEFS = [(t) for t in TOOLS]