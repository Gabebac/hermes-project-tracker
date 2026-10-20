"""Project Tracker REST for the desktop tab. Same store as the agent tools."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

try:
    from .. import service  # type: ignore
except ImportError:  # pragma: no cover - standalone dashboard load
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import service  # type: ignore

router = APIRouter()


class ProjectIn(BaseModel):
    name: str
    label: str | None = None
    section: str | None = None
    phase: str | None = None
    next_action: str | None = None
    note: str | None = None
    promote_by: str | None = None
    repo: str | None = None


class SetIn(BaseModel):
    name: str
    section: str | None = None
    phase: str | None = None
    current_focus: str | None = None
    next_action: str | None = None
    note: str | None = None
    promote_by: str | None = None
    repo: str | None = None


class SessionIn(BaseModel):
    name: str
    text: str
    date: str | None = None


class ItemIn(BaseModel):
    name: str
    action: str
    side: str
    text: str


@router.get("/state")
def state() -> dict:
    return service.list_projects()


@router.post("/project")
def project_add(p: ProjectIn) -> dict:
    return service.add_project(p.name, label=p.label or "App", section=p.section,
                               phase=p.phase, next_action=p.next_action,
                               note=p.note, promote_by=p.promote_by, repo=p.repo)


@router.post("/set")
def project_set(s: SetIn) -> dict:
    return service.set_project(s.name, **{
        k: getattr(s, k) for k in
        ("section", "phase", "current_focus", "next_action", "note", "promote_by", "repo")
    })


@router.post("/session")
def session(s: SessionIn) -> dict:
    if not s.text.strip():
        return {"error": "empty session text"}
    return service.log_session(s.name, s.text, when=s.date)


@router.post("/item")
def item(i: ItemIn) -> dict:
    return service.project_item(i.name, i.action, i.side, i.text)


@router.get("/review")
def review() -> dict:
    return service.review()