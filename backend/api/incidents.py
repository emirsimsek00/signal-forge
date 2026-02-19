"""Incident API endpoints."""

from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

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
