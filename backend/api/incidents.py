"""Incident API endpoints."""

from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.websocket import manager as ws_manager
from backend.database import get_session
from backend.models.incident import Incident, IncidentCreate, IncidentResponse

router = APIRouter(prefix="/api/incidents", tags=["incidents"])


@router.get("", response_model=list[IncidentResponse])
async def list_incidents(
    status: str | None = Query(None),
    severity: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    """List incidents with optional filtering."""
    query = select(Incident).order_by(desc(Incident.created_at))

    if status:
        query = query.where(Incident.status == status)
    if severity:
        query = query.where(Incident.severity == severity)

    query = query.limit(limit)
    result = await session.execute(query)
    incidents = result.scalars().all()
    return [IncidentResponse.model_validate(i) for i in incidents]


@router.get("/{incident_id}", response_model=IncidentResponse)
async def get_incident(
    incident_id: int,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return IncidentResponse.model_validate(incident)


@router.post("", response_model=IncidentResponse, status_code=201)
async def create_incident(
    data: IncidentCreate,
    session: AsyncSession = Depends(get_session),
):
    incident = Incident(
        title=data.title,
        description=data.description,
        severity=data.severity,
        status="active",
        start_time=data.start_time,
        end_time=data.end_time,
        related_signal_ids_json=json.dumps(data.related_signal_ids),
        root_cause_hypothesis=data.root_cause_hypothesis,
    )
    session.add(incident)
    await session.commit()
    await session.refresh(incident)
    return IncidentResponse.model_validate(incident)


def _apply_transition(incident: Incident, action: str) -> None:
    """Apply a lifecycle action to an incident or raise 409 if invalid."""
    now = datetime.utcnow()

    if action == "acknowledge":
        if incident.status not in {"active", "investigating"}:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot acknowledge incident in '{incident.status}' state",
            )
        incident.status = "investigating"
        incident.end_time = None
        return

    if action == "resolve":
        if incident.status not in {"active", "investigating", "resolved"}:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot resolve incident in '{incident.status}' state",
            )
        incident.status = "resolved"
        incident.end_time = incident.end_time or now
        return

    if action == "dismiss":
        if incident.status not in {"active", "investigating", "dismissed"}:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot dismiss incident in '{incident.status}' state",
            )
        incident.status = "dismissed"
        incident.end_time = incident.end_time or now
        return

    if action == "reopen":
        if incident.status not in {"resolved", "dismissed", "active"}:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot reopen incident in '{incident.status}' state",
            )
        incident.status = "active"
        incident.end_time = None
        return

    raise HTTPException(status_code=400, detail=f"Unsupported action: {action}")


async def _transition_incident(
    incident_id: int,
    action: str,
    session: AsyncSession,
) -> IncidentResponse:
    result = await session.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    previous_status = incident.status
    previous_end_time = incident.end_time
    _apply_transition(incident, action)

    await session.commit()
    await session.refresh(incident)

    if incident.status != previous_status or incident.end_time != previous_end_time:
        await ws_manager.broadcast_alert(
            {
                "type": "incident_update",
                "incident_id": incident.id,
                "action": action,
                "status": incident.status,
                "severity": incident.severity,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

    return IncidentResponse.model_validate(incident)


@router.post("/{incident_id}/acknowledge", response_model=IncidentResponse)
async def acknowledge_incident(
    incident_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Move an incident from active to investigating."""
    return await _transition_incident(incident_id, "acknowledge", session)


@router.post("/{incident_id}/resolve", response_model=IncidentResponse)
async def resolve_incident(
    incident_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Mark an incident as resolved."""
    return await _transition_incident(incident_id, "resolve", session)


@router.post("/{incident_id}/dismiss", response_model=IncidentResponse)
async def dismiss_incident(
    incident_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Dismiss an incident as non-actionable."""
    return await _transition_incident(incident_id, "dismiss", session)


@router.post("/{incident_id}/reopen", response_model=IncidentResponse)
async def reopen_incident(
    incident_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Re-open a previously resolved or dismissed incident."""
    return await _transition_incident(incident_id, "reopen", session)


# ── Notes (collaboration) ───────────────────────────────────────

from backend.models.note import Note, NoteCreate, NoteResponse


@router.get("/{incident_id}/notes", response_model=list[NoteResponse])
async def list_notes(
    incident_id: int,
    session: AsyncSession = Depends(get_session),
):
    """List all notes for an incident."""
    result = await session.execute(
        select(Note).where(Note.incident_id == incident_id).order_by(Note.created_at)
    )
    notes = result.scalars().all()
    return [NoteResponse.model_validate(n) for n in notes]


@router.post("/{incident_id}/notes", response_model=NoteResponse, status_code=201)
async def add_note(
    incident_id: int,
    data: NoteCreate,
    session: AsyncSession = Depends(get_session),
):
    """Add a note to an incident."""
    # Verify incident exists
    inc_result = await session.execute(select(Incident).where(Incident.id == incident_id))
    if not inc_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Incident not found")

    note = Note(
        incident_id=incident_id,
        content=data.content,
        author=data.author,
    )
    session.add(note)
    await session.commit()
    await session.refresh(note)
    return NoteResponse.model_validate(note)


# ── Timeline ────────────────────────────────────────────────────


@router.get("/{incident_id}/timeline")
async def get_incident_timeline(
    incident_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get the full timeline for an incident workspace.

    Returns related signals, notes, and status events in chronological order.
    """
    from backend.models.signal import Signal

    # Get incident
    inc_result = await session.execute(select(Incident).where(Incident.id == incident_id))
    incident = inc_result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    timeline: list[dict] = []

    # Add incident creation
    timeline.append({
        "type": "incident_created",
        "timestamp": incident.start_time.isoformat() if incident.start_time else incident.created_at.isoformat(),
        "content": f"Incident created: {incident.title}",
        "severity": incident.severity,
    })

    # Add related signals
    if incident.related_signal_ids_json:
        try:
            signal_ids = json.loads(incident.related_signal_ids_json)
            if signal_ids:
                sig_result = await session.execute(
                    select(Signal).where(Signal.id.in_(signal_ids))
                )
                for sig in sig_result.scalars().all():
                    timeline.append({
                        "type": "signal",
                        "timestamp": sig.timestamp.isoformat() if sig.timestamp else sig.created_at.isoformat(),
                        "content": sig.title or sig.content[:100],
                        "source": sig.source,
                        "signal_id": sig.id,
                        "risk_tier": sig.risk_tier,
                        "sentiment_label": sig.sentiment_label,
                    })
        except (json.JSONDecodeError, Exception):
            pass

    # Add notes
    notes_result = await session.execute(
        select(Note).where(Note.incident_id == incident_id)
    )
    for note in notes_result.scalars().all():
        timeline.append({
            "type": "note",
            "timestamp": note.created_at.isoformat(),
            "content": note.content,
            "author": note.author,
        })

    # Add resolution if resolved
    if incident.end_time:
        timeline.append({
            "type": "incident_resolved",
            "timestamp": incident.end_time.isoformat(),
            "content": f"Incident {incident.status}",
            "status": incident.status,
        })

    # Sort chronologically
    timeline.sort(key=lambda x: x["timestamp"])

    return {
        "incident": IncidentResponse.model_validate(incident),
        "timeline": timeline,
        "event_count": len(timeline),
    }

