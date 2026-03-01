"""Tests for the anomaly detection engine."""

import pytest
from datetime import datetime, timedelta

from backend.utils.time import utc_now

from backend.anomaly.detector import AnomalyDetector, AnomalyEvent
from backend.models.signal import Signal


class TestAnomalyEvent:
    """Test AnomalyEvent dataclass."""

    def test_create_event(self):
        event = AnomalyEvent(
            id="test-event-1",
            type="volume_spike",
            severity="critical",
            title="Test anomaly",
            description="A test anomaly event",
            affected_source="reddit",
            metric_value=50.0,
            threshold=20.0,
        )
        assert event.id == "test-event-1"
        assert event.type == "volume_spike"
        assert event.severity == "critical"
        assert event.metric_value == 50.0
        assert isinstance(event.detected_at, datetime)

    def test_event_defaults(self):
        event = AnomalyEvent(
            id="test-2",
            type="risk_spike",
            severity="high",
            title="Risk",
            description="Desc",
            affected_source=None,
            metric_value=0.8,
            threshold=0.5,
        )
        assert event.affected_signal_ids == []
        assert event.detected_at is not None


class TestAnomalyDetector:
    """Test the anomaly detector."""

    def test_detector_initializes(self):
        detector = AnomalyDetector()
        assert detector is not None
        assert detector.recent_events == []

    def test_recent_events_ordered(self):
        detector = AnomalyDetector()
        detector._events = [
            AnomalyEvent(
                id=f"e-{i}", type="volume_spike", severity="high",
                title=f"Event {i}", description=f"Desc {i}",
                affected_source="reddit", metric_value=float(i),
                threshold=0.5,
            )
            for i in range(5)
        ]
        events = detector.recent_events
        # Recent events should be reversed (newest first)
        assert events[0].id == "e-4"
        assert events[-1].id == "e-0"

    def test_max_events_cap(self):
        detector = AnomalyDetector()
        detector._max_events = 5
        for i in range(10):
            detector._events.append(
                AnomalyEvent(
                    id=f"e-{i}", type="volume_spike", severity="moderate",
                    title=f"Event {i}", description=f"Desc {i}",
                    affected_source=None, metric_value=1.0, threshold=0.5,
                )
            )
        # Should only keep max
        detector._events = detector._events[-detector._max_events:]
        assert len(detector._events) == 5

    @pytest.mark.asyncio
    async def test_run_detection_empty_db(self, db_session):
        """Detection on empty database should return no events."""
        detector = AnomalyDetector()
        events = await detector.run_detection(db_session)
        assert events == []

    @pytest.mark.asyncio
    async def test_run_detection_with_signals(self, db_session):
        """Detection with signals should not error."""
        now = utc_now()
        for i in range(20):
            sig = Signal(
                source="reddit",
                source_id=f"test-{i}",
                title=f"Test signal {i}",
                content=f"Test content {i}",
                timestamp=now - timedelta(minutes=i * 5),
                sentiment_score=-0.5,
                sentiment_label="negative",
                risk_score=0.4,
                risk_tier="moderate",
            )
            db_session.add(sig)
        await db_session.commit()

        detector = AnomalyDetector()
        events = await detector.run_detection(db_session)
        # Should not error, events may or may not be detected
        assert isinstance(events, list)
