"""Store + staleness rules for project-tracker.

Source of truth: projects.json in plugin data. The vault's [[Projects]] note
is the human-facing mirror the agent maintains; this store is the live one.
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime
from pathlib import Path

# ponytail: process-local writes (no lock) — one agent session + one desktop
# tab hitting the same store; if two writers ever race, revisit with an
# atomic-rename lock or move to SQLite.
SECTIONS = ["Ongoing (Business)", "Building", "Maintenance", "Ideas", "Done"]
SECTIONS_BY_LABEL = {
    "Business": "Ongoing (Business)",
}

# Staleness: section overrides label rule (Pooh's Sunday-review rules)
STALE_DAYS_SECTION = {"Maintenance": 42, "Ideas": 21}
STALE_DAYS_LABEL = {"App": 14, "Personal": 21}  # Business = never drops


def _data_dir() -> Path:
    env = os.environ.get("PROJECT_TRACKER_DATA")
    if env:
        return Path(env)
    from plugins.plugin_storage import plugin_data_dir

    return Path(plugin_data_dir("project-tracker"))


def _store_path() -> Path:
    p = _data_dir()
    p.mkdir(parents=True, exist_ok=True)
    return p / "projects.json"


def _sessions_path() -> Path:
    return _data_dir() / "sessions.jsonl"


def _load() -> dict:
    p = _store_path()
    if not p.exists():
        return {"projects": {}}
    return json.loads(p.read_text())


def _save(store: dict) -> None:
    _store_path().write_text(json.dumps(store, indent=2, ensure_ascii=False))


def _today() -> str:
    return date.today().isoformat()


def _days_between(a: str, b: str) -> int:
    return (date.fromisoformat(b) - date.fromisoformat(a)).days


def evaluate_staleness(p: dict, today: str | None = None) -> dict:
    """One rule per Pooh's staleness table. Returns a flag with evidence."""
    today = today or _today()
    section = p.get("section", "")
    label = p.get("label", "")
    if section == "Ongoing (Business)" or label == "Business":
        return {"stale": False, "rule": "Business never drops — it pauses, doesn't die", "days_idle": None}
    if section == "Ideas":
        by = p.get("promote_by")
        rule = "Ideas: promote within 3 Sundays or drop/park"
        if by and _days_between(by, today) > 0:
            return {"stale": True, "rule": rule + " — overdue", "days_idle": _days_between(by, today), "overdue_by": by}
        if by:
            return {"stale": False, "rule": rule + f" — decide by {by}", "days_idle": None}
        return {"stale": False, "rule": rule + " — no promote-by set", "days_idle": None}
    days = STALE_DAYS_SECTION.get(section) or STALE_DAYS_LABEL.get(label)
    if days is None:
        return {"stale": False, "rule": "no staleness rule", "days_idle": None}
    last = p.get("last_update") or p.get("created") or today
    idle = _days_between(last, today)
    return {
        "stale": idle > days,
        "rule": f"no logged session for {days} days flags it",
        "days_idle": idle,
        "last_update": last,
    }


def add_project(name: str, label: str = "App", section: str | None = None,
                phase: str | None = None, next_action: str | None = None,
                note: str | None = None, promote_by: str | None = None,
                repo: str | None = None) -> dict:
    store = _load()
    name = name.strip()
    if not name:
        return {"error": "project name required"}
    if name in store["projects"]:
        return {"error": f"'{name}' already exists — use project_set"}
    section = section or SECTIONS_BY_LABEL.get(label, "Building")
    if section not in SECTIONS:
        return {"error": f"section must be one of {SECTIONS}"}
    if label not in ("Business", "App", "Personal", "Idea"):
        return {"error": "label must be Business|App|Personal|Idea"}
    p = {
        "name": name, "label": label, "section": section,
        "phase": phase or "", "current_focus": "", "next_action": next_action or "",
        "note": note or "", "repo": repo or "",
        "created": _today(), "last_update": _today(),
        "promote_by": promote_by,
        "done": [], "left": [],
    }
    store["projects"][name] = p
    _save(store)
    return {"ok": True, "project": p}


def set_project(name: str, **fields) -> dict:
    store = _load()
    p = store["projects"].get(name)
    if not p:
        return {"error": f"unknown project '{name}'"}
    allowed = {"section", "phase", "current_focus", "next_action", "note",
               "promote_by", "last_update", "label", "repo"}
    changed = []
    for k, v in fields.items():
        if v is None or k not in allowed:
            continue
        if k == "section" and v not in SECTIONS:
            return {"error": f"section must be one of {SECTIONS}"}
        p[k] = v
        changed.append(k)
    if not changed:
        return {"error": "nothing to set (give at least one field)"}
    _save(store)
    return {"ok": True, "changed": changed, "project": p}


def log_session(name: str, text: str, when: str | None = None) -> dict:
    store = _load()
    p = store["projects"].get(name)
    if not p:
        return {"error": f"unknown project '{name}'"}
    when = when or _today()
    try:
        date.fromisoformat(when)
    except ValueError:
        return {"error": "date must be YYYY-MM-DD"}
    p["last_update"] = when
    with _sessions_path().open("a") as f:
        f.write(json.dumps({"date": when, "project": name, "text": text}, ensure_ascii=False) + "\n")
    _save(store)
    return {"ok": True, "logged": {"date": when, "project": name, "text": text}}


def _item(p: dict, action: str, side: str, text: str) -> dict:
    if side not in ("done", "left"):
        return {"error": "side must be done|left"}
    lst = p[side]
    if action == "add":
        lst.append({"text": text, "done": False} if side == "left" else {"text": text})
    elif action == "check":  # left -> done
        match = [i for i in lst if i["text"] == text]
        if not match:
            return {"error": f"not in {side}: '{text}'"}
        lst.remove(match[0])
        p["done"].append({"text": text})
    elif action == "uncheck":  # done -> left
        match = [i for i in lst if i["text"] == text]
        if not match:
            return {"error": f"not in done: '{text}'"}
        lst.remove(match[0])
        p["left"].append({"text": text, "done": False})
    elif action == "remove":
        match = [i for i in lst if i["text"] == text]
        if not match:
            return {"error": f"not in {side}: '{text}'"}
        lst.remove(match[0])
    else:
        return {"error": "action must be add|check|uncheck|remove"}
    return {"ok": True}


def project_item(name: str, action: str, side: str, text: str) -> dict:
    store = _load()
    p = store["projects"].get(name)
    if not p:
        return {"error": f"unknown project '{name}'"}
    r = _item(p, action, side, text.strip())
    if "error" not in r:
        _save(store)
    return r


def list_projects(today: str | None = None) -> dict:
    store = _load()
    today = today or _today()
    out = []
    for name, p in store["projects"].items():
        item = dict(p)
        item["staleness"] = evaluate_staleness(p, today=today)
        out.append(item)
    order = {s: i for i, s in enumerate(SECTIONS)}
    out.sort(key=lambda x: (order.get(x["section"], 9), x["name"]))
    return {"today": today, "projects": out}


def review(today: str | None = None) -> dict:
    """Sunday-review evidence packet."""
    data = list_projects(today=today)
    flags, healthy = [], []
    for p in data["projects"]:
        s = p["staleness"]
        if s["stale"]:
            flags.append({
                "project": p["name"], "section": p["section"], "label": p["label"],
                "evidence": {
                    "rule": s["rule"], "days_idle": s.get("days_idle"),
                    "last_update": s.get("last_update") or p.get("promote_by"),
                    "next_action": p.get("next_action") or "(none set)",
                    "phase": p.get("phase") or "(none)",
                },
                "decision": "re-commit / park / drop" if p["section"] == "Building" else "decide",
            })
        else:
            healthy.append(p["name"])
    return data | {"stale_flags": flags, "healthy": healthy,
                   "review_checklist": [
                       "walk each stale flag: re-commit / park / drop",
                       "move finished Apps Building -> Maintenance",
                       "promote or park Ideas past promote-by",
                       "pick 1-3 projects for next week",
                   ]}