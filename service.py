"""Store + staleness rules for project-tracker.

Source of truth: projects.json in plugin data. The vault's [[Projects]] note
is the human-facing mirror the agent maintains; this store is the live one.
"""
from __future__ import annotations

import json
import os
import re
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

# ---------------------------------------------------------------------------
# Refresh / evidence pass — pinned + recent desktop sessions vs the tracker log
# (feeds the Sunday interview; read-only, the session DB is never written)
# ---------------------------------------------------------------------------

import sqlite3
import time as _time


def _state_db_path():
    """The desktop app's session store (sessions table carries a pinned column)."""
    import os as _os
    env = _os.environ.get("PROJECT_TRACKER_STATE_DB")
    if env and Path(env).exists():
        return Path(env)
    try:
        from hermes_constants import get_hermes_home

        p = Path(get_hermes_home()) / "state.db"
        if p.exists():
            return p
    except Exception:  # noqa: BLE001 - fall through to filesystem guesses
        pass
    here = _data_dir().resolve()
    for parent in [here, *here.parents[:4]]:
        c = parent / "state.db"
        if c.exists():
            return c
    guesses = [
        Path.home() / "AppData" / "Local" / "hermes" / "state.db",
        Path.home() / ".hermes" / "state.db",
    ]
    for g in guesses:
        if g.exists():
            return g
    return None


def _norm(s: str) -> str:
    return "".join(ch for ch in (s or "").lower() if ch.isalnum())


def _sessions_window(days: int) -> dict:
    """project -> [{date, text}] logged inside the window (from sessions.jsonl)."""
    out: dict[str, list] = {}
    cutoff = (date.today() - __import__("datetime").timedelta(days=days)).isoformat()
    p = _sessions_path()
    if p.exists():
        for line in p.read_text().splitlines():
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("date", "") >= cutoff:
                out.setdefault(e.get("project", ""), []).append(e)
    return out


def _query_sessions(sql: str, args: tuple, previews: bool = False) -> list:
    db = _state_db_path()
    if not db:
        return []
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=2)
        con.row_factory = sqlite3.Row
        rows = [dict(r) for r in con.execute(sql, args)]
        if previews:
            for r in rows:
                r["preview"] = _first_user_prompt(con, r["id"])
        con.close()
        return rows
    except sqlite3.Error:
        return []


def _first_user_prompt(con, sid: str) -> str:
    try:
        row = con.execute(
            "SELECT content FROM messages WHERE session_id=? AND role='user' ORDER BY id LIMIT 1",
            (sid,),
        ).fetchone()
    except sqlite3.Error:
        return ""
    txt = (row[0] or "") if row else ""
    return re.sub(r"\s+", " ", txt).strip()[:200]


def pinned_sessions(limit: int = 25) -> list:
    sql = (
        "SELECT id, source, COALESCE(display_name, title) AS name, title, started_at,"
        " last_activity_at, message_count, profile_name FROM sessions"
        " WHERE pinned = 1 AND hidden = 0"
        " ORDER BY COALESCE(last_activity_at, started_at) DESC LIMIT ?"
    )
    return _query_sessions(sql, (limit,))


def recent_sessions(days: int = 7, limit: int = 30) -> list:
    since = _time.time() - days * 86400
    sql = (
        "SELECT id, source, COALESCE(display_name, title) AS name, title, started_at,"
        " last_activity_at, message_count, profile_name, archived FROM sessions"
        " WHERE hidden = 0 AND COALESCE(last_activity_at, started_at) >= ?"
        " ORDER BY COALESCE(last_activity_at, started_at) DESC LIMIT ?"
    )
    return _query_sessions(sql, (since, limit), previews=True)


def unlogged_candidates(recent: list, logs_window: dict, projects: list) -> list:
    """Sessions that look like project work but have no tracker log on/after them.

    Candidates are evidence, never conclusions — raise them for confirmation.
    """
    names = [p["name"] for p in projects]
    nrm = {n: _norm(n) for n in names}
    out, seen = [], set()
    for s in recent:
        sid = s["started_at"]
        day = (
            __import__("datetime")
            .datetime.fromtimestamp(sid)
            .strftime("%Y-%m-%d")
            if sid
            else None
        )
        hay = _norm((s.get("name") or "") + " " + (s.get("preview") or ""))
        if not hay:
            continue
        for n, nn in nrm.items():
            if len(nn) < 3 or nn not in hay:
                continue
            if day and any(e["date"] >= day for e in logs_window.get(n, [])):
                continue
            key = (n, s["id"])
            if key in seen:
                continue
            seen.add(key)
            out.append({
                "project": n, "session_id": s["id"], "title": s.get("name") or "",
                "when": day, "when_ts": sid, "preview": s.get("preview") or "",
            })
    out.sort(key=lambda x: x.get("when_ts") or 0, reverse=True)
    return out[:10]


def _brief_markdown(b: dict) -> str:
    lines = [
        "# Projects interview brief", "",
        f"Fresh evidence built by the tracker Refresh: **{b['generated_at']}** "
        f"(window: {b['window_days']} days) · checked {len(b['pinned'])} pinned + "
        f"{len(b['recent'])} recent desktop sessions.", "",
        "## Questions to ask (in order)", "",
    ]
    mapping = {
        "1_done_this_week": "① Done this week — confirmations",
        "2_stale_decisions": "② Stale — re-commit / park / drop",
        "3_ideas": "③ New ideas / promotions",
        "4_business_focus": "④ Business focus + next action",
        "5_next_week": "⑤ Next week's 1-3 picks + candidate raises",
    }
    for key, title in mapping.items():
        lines.append(f"### {title}")
        qs = b["questions"].get(key) or []
        if qs:
            lines.extend(f"- {q}" for q in qs)
        else:
            lines.append("- (nothing to ask from the current evidence)")
        lines.append("")
    lines += ["## Unlogged-work candidates (confirm before logging)", ""]
    if b["unlogged"]:
        for c in b["unlogged"]:
            lines.append(f"- **{c['project']}** — {c['when']} · {c['title']}")
            if c["preview"]:
                lines.append(f"  > {c['preview']}")
    else:
        lines.append("- none found in the window")
    lines += ["", "## Session titles in the window", ""]
    for s in b["recent"][:20]:
        when = (
            __import__("datetime").datetime.fromtimestamp(s["last_activity_at"] or s["started_at"]).strftime("%m-%d %H:%M")
            if (s["last_activity_at"] or s["started_at"]) else "?"
        )
        lines.append(f"- {when} · {s.get('name') or '(untitled)'} · {s['message_count']} msgs"
                     + (f" · matches: {', '.join(s['matches'])}" if s["matches"] else ""))
    return "\n".join(lines)


def build_brief(days: int = 7) -> dict:
    """Evidence pass + updated interview questions for the weekly update.

    Read-only. Also persists review_brief.json / review_brief.md in plugin data
    so a manual interview (agent side) can pick the same evidence up.
    """
    import datetime as _dt
    today = _today()
    days = max(1, min(int(days or 7), 31))
    review_packet = review(today=today)  # stale flags + checklist
    data = list_projects(today=today)
    projects = data["projects"]
    logs = _sessions_window(days)
    pinned = pinned_sessions()
    recent = recent_sessions(days)
    candidates = unlogged_candidates(recent, logs, projects)

    # per-session project mentions
    nrm = {p["name"]: _norm(p["name"]) for p in projects}
    for s in recent:
        hay = _norm((s.get("name") or "") + " " + (s.get("preview") or ""))
        s["matches"] = [n for n, nn in nrm.items() if len(nn) >= 3 and nn in hay]

    questions: dict[str, list] = {k: [] for k in (
        "1_done_this_week", "2_stale_decisions", "3_ideas", "4_business_focus", "5_next_week")}
    for name, entries in sorted(logs.items()):
        if name in {p["name"] for p in projects}:
            joined = "; ".join(f"{e['date']}: {e['text'][:80]}" for e in entries[-3:])
            questions["1_done_this_week"].append(f"{name} — logged: {joined}. Confirm and mark anything done.")
    for f in review_packet.get("stale_flags", []):
        ev = f["evidence"]
        questions["2_stale_decisions"].append(
            f"{f['project']} ({f['section']}) idle {ev.get('days_idle') or '?'}d, "
            f"last {ev.get('last_update') or '?'} · next action: {ev.get('next_action')} — re-commit / park / drop?")
    for p in projects:
        if p["section"] == "Ideas":
            questions["3_ideas"].append(
                f"{p['name']} — promote by {p.get('promote_by') or '(no date set)'}: promote with a phase, or park?")
    for p in projects:
        if p["section"] == "Ongoing (Business)":
            questions["4_business_focus"].append(
                f"{p['name']} (phase: {p.get('phase') or 'none'}) — current focus + next action?")
    for c in candidates:
        questions["5_next_week"].append(
            f"Unlogged work on {c['project']} ({c['when']} · {c['title']}) — log it? what really happened?")
    questions["5_next_week"].append("Pick 1-3 projects for next week.")

    brief = {
        "generated_at": _dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "today": today,
        "window_days": days,
        "pinned": pinned,
        "recent": recent,
        "sessions_checked": {"pinned": len(pinned), "recent": len(recent)},
        "unlogged": candidates,
        "stale_flags": review_packet.get("stale_flags", []),
        "healthy": review_packet.get("healthy", []),
        "logged_window": {k: v for k, v in logs.items()},
        "questions": questions,
        "projects": projects,
        "sources": {"state_db": str(_state_db_path() or "(not found)")},
    }
    brief["brief"] = (
        "Run Pooh's projects interview now.\n\n"
        "Load the skill `projects-routine` and follow its \"Sunday interview\" procedure "
        "(evidence pass -> 5 question stages -> apply in one pass). You are in an interactive "
        "desktop session: use clarify() for the interview questions (batch independent ones, "
        "max 4-5 per call).\n\n"
        f"An evidence refresh was already run at {brief['generated_at']}: "
        f"{len(pinned)} pinned + {len(recent)} recent desktop sessions checked, "
        f"{len(candidates)} unlogged-work candidates raised. Treat it as the first evidence pass — "
        "verify anything you use (call projects_review for the staleness packet) and extend with "
        "session_search only if something looks off.\n\n"
        "Questions to ask (in order, one call per stage):\n"
        + "".join(f"  {k}:\n" + "".join(f"    - {q}\n" for q in (questions[k] or ["(nothing to ask)"]))
                  for k in ("1_done_this_week", "2_stale_decisions", "3_ideas", "4_business_focus", "5_next_week"))
        + "\nThen apply all confirmed answers in one pass: project_log / project_set / project_item, "
        "explicit section moves, update the tracker, write the vault week note (Hermes/Projects/Weekly "
        "per the vault-delivery docker path), sync [[Projects]], and report every change back.\n"
        "Nothing moves without his answer — never drop, park, promote, or complete silently."
    )
    try:
        _data_dir().mkdir(parents=True, exist_ok=True)
        (_data_dir() / "review_brief.json").write_text(
            json.dumps(brief, indent=2, ensure_ascii=False, default=str))
        (_data_dir() / "review_brief.md").write_text(_brief_markdown(brief), encoding="utf-8")
        brief["persisted"] = True
    except OSError:
        brief["persisted"] = False
    return brief
