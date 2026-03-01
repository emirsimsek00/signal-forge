"""Tests for incident lifecycle API transition logic."""

from __future__ import annotations

from datetime import datetime

from backend.utils.time import utc_now

import pytest
from fastapi import HTTPException

from backend.api.incidents import _apply_transition
from backend.models.incident import Incident


def _incident(status: str = "active", end_time: datetime | None = None) -> Incident:
    return Incident(
        title="Test incident",
        description="Test description",
        severity="high",
        status=status,
        start_time=utc_now(),
        end_time=end_time,
        related_signal_ids_json="[]",
    )


def test_acknowledge_active_sets_investigating() -> None:
    incident = _incident(status="active")
    _apply_transition(incident, "acknowledge")
    assert incident.status == "investigating"
    assert incident.end_time is None


def test_resolve_sets_terminal_status_and_end_time() -> None:
    incident = _incident(status="investigating")
    _apply_transition(incident, "resolve")
    assert incident.status == "resolved"
    assert incident.end_time is not None


def test_reopen_clears_end_time() -> None:
    incident = _incident(status="resolved", end_time=utc_now())
    _apply_transition(incident, "reopen")
    assert incident.status == "active"
    assert incident.end_time is None


def test_dismiss_resolved_is_invalid() -> None:
    incident = _incident(status="resolved")
    with pytest.raises(HTTPException) as exc:
        _apply_transition(incident, "dismiss")
    assert exc.value.status_code == 409


def test_unknown_action_raises_400() -> None:
    incident = _incident(status="active")
    with pytest.raises(HTTPException) as exc:
        _apply_transition(incident, "not-real")
    assert exc.value.status_code == 400
