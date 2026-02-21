"""Demo data seeding API — pre-loads realistic dataset for instant demo experience."""

from __future__ import annotations

import json
import logging
import random
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_session
from backend.models.signal import Signal
from backend.models.incident import Incident
from backend.models.risk import RiskAssessment
from backend.nlp.pipeline import NLPPipeline
from backend.risk.scorer import RiskScorer
from backend.config import settings
from backend.api.auth import get_tenant_id

logger = logging.getLogger("signalforge.demo")
router = APIRouter(prefix="/api/demo", tags=["demo"])

_pipeline = NLPPipeline(use_mock=settings.use_mock_ml)
_scorer = RiskScorer()

# ── Pre-built signal dataset ────────────────────────────────────

_DEMO_SIGNALS = [
    # Critical Stripe signals
    {"source": "stripe", "title": "Surge in failed payments across EU region",
     "content": "Payment failure rate spiked to 12% in the last hour across EU customers. Primary error: card_declined and processing_error. Affecting approximately 340 transactions. Revenue impact estimated at $28,000.",
     "metadata": {"event_type": "charge.failed", "amount": 28000, "currency": "usd", "failure_rate": 0.12}},
    {"source": "stripe", "title": "Unusual chargeback cluster detected",
     "content": "17 chargebacks filed in the past 3 hours from enterprise customers on the Pro plan. Pattern suggests potential fraud ring targeting annual subscriptions.",
     "metadata": {"event_type": "charge.dispute.created", "amount": 45000, "dispute_count": 17}},

    # PagerDuty incidents
    {"source": "pagerduty", "title": "API latency exceeding SLA thresholds",
     "content": "P95 latency at 4200ms (SLA: 500ms). Database connection pool exhausted. Affecting /api/v2/users and /api/v2/orders endpoints. Auto-scaling triggered but not resolving.",
     "metadata": {"urgency": "high", "status": "triggered", "service": "api-gateway"}},
    {"source": "pagerduty", "title": "Memory leak in recommendation service",
     "content": "Recommendation engine pod consuming 14GB RAM, expected 4GB. Gradual increase over 48 hours. OOM kills occurring every 6 hours. Customer-facing product recommendations degraded.",
     "metadata": {"urgency": "high", "status": "triggered", "service": "ml-recommendations"}},

    # Reddit community sentiment
    {"source": "reddit", "title": "Users reporting intermittent login failures",
     "content": "Multiple posts on r/sysadmin about login issues: 'Been getting 502 errors trying to log in for the past hour. Anyone else?' Thread has 47 upvotes and 23 comments, mostly confirming the issue.",
     "metadata": {"subreddit": "sysadmin", "upvotes": 47, "num_comments": 23}},
    {"source": "reddit", "title": "Competitor launches free tier matching our paid plan",
     "content": "Discussion on r/startups about CompetitorX releasing a free tier that includes features currently only in our $49/month plan. Significant community interest with users comparing feature sets.",
     "metadata": {"subreddit": "startups", "upvotes": 312, "num_comments": 89}},
    {"source": "reddit", "title": "Positive review of latest product update",
     "content": "User posted detailed review praising the new dashboard redesign: 'Finally feels like a modern tool. The risk visualization is exactly what our ops team needed.' Getting traction in r/devops.",
     "metadata": {"subreddit": "devops", "upvotes": 128, "num_comments": 34}},

    # News signals
    {"source": "news", "title": "Major cloud provider announces 3-hour outage",
     "content": "AWS us-east-1 experiencing degraded performance affecting S3, EC2, and RDS services. Multiple SaaS companies reporting downstream impact. Expected resolution in 2-3 hours.",
     "metadata": {"category": "technology", "publisher": "TechCrunch"}},
    {"source": "news", "title": "New data privacy regulation passed in EU",
     "content": "European Parliament passes Digital Services Act amendment requiring real-time data breach notification within 4 hours. Significant compliance implications for SaaS companies handling EU citizen data.",
     "metadata": {"category": "business", "publisher": "Reuters"}},
    {"source": "news", "title": "Industry report: SaaS churn rates rising across sector",
     "content": "Latest SaaS benchmark report shows average B2B churn increased from 5.2% to 7.8% YoY. Key drivers: economic uncertainty, budget cuts, and increased competition in crowded markets.",
     "metadata": {"category": "business", "publisher": "SaaS Weekly"}},

    # Zendesk support tickets
    {"source": "zendesk", "title": "Enterprise customer threatening cancellation",
     "content": "Acme Corp (ARR: $120K) opened urgent ticket: 'We have experienced 3 outages in the past month. Leadership is evaluating alternatives. Need executive escalation immediately.'",
     "metadata": {"ticket_status": "open", "priority": "urgent", "customer_tier": "enterprise"}},
    {"source": "zendesk", "title": "Billing discrepancy reports from multiple SMB accounts",
     "content": "12 tickets opened in the last 24 hours about incorrect invoice amounts. All relate to the mid-cycle plan change feature. Engineering confirmed a rounding bug in the proration logic.",
     "metadata": {"ticket_status": "open", "priority": "high", "ticket_count": 12}},
    {"source": "zendesk", "title": "Feature request cluster: SSO integration",
     "content": "27 tickets requesting SAML SSO in the past quarter, 8 from enterprise prospects. Sales team flagging this as the #1 blocker for deals over $50K ARR.",
     "metadata": {"ticket_status": "pending", "priority": "normal", "request_count": 27}},

    # System metrics
    {"source": "system", "title": "Database replication lag exceeding threshold",
     "content": "PostgreSQL read replica lag at 45 seconds (threshold: 5s). Write-heavy migration job running on primary. Read-dependent services returning stale data. Dashboard metrics may be delayed.",
     "metadata": {"metric": "replication_lag", "value": 45, "threshold": 5, "unit": "seconds"}},
    {"source": "system", "title": "CDN cache hit ratio dropped significantly",
     "content": "CloudFront cache hit ratio dropped from 94% to 62% after the last deployment. New static asset hashes invalidated cache. Increased origin load causing slower page loads globally.",
     "metadata": {"metric": "cache_hit_ratio", "value": 0.62, "threshold": 0.85}},

    # Financial signals
    {"source": "financial", "title": "MRR growth stalling — 3-month plateau",
     "content": "Monthly Recurring Revenue has been flat at $2.1M for three consecutive months. New customer acquisition down 18% while expansion revenue from existing accounts up only 3%.",
     "metadata": {"metric": "mrr", "value": 2100000, "growth_rate": 0.001}},
    {"source": "financial", "title": "Customer acquisition cost rising unsustainably",
     "content": "CAC increased to $2,800 (up from $1,900 last quarter). LTV:CAC ratio now at 2.1x, below the 3x healthy threshold. Paid channels showing diminishing returns.",
     "metadata": {"metric": "cac", "value": 2800, "ltv_cac_ratio": 2.1}},
]

_DEMO_INCIDENTS = [
    {
        "title": "Payment Processing Degradation",
        "description": "Elevated payment failure rates across EU region correlated with API latency spikes. Multiple Stripe webhook failures detected alongside PagerDuty alerts for the payment gateway service.",
        "severity": "critical",
        "status": "investigating",
        "root_cause_hypothesis": "Database connection pool exhaustion is cascading to payment processing timeouts. The pool limit (50 connections) is being saturated by a long-running migration job.",
        "recommended_actions": "1. Pause the migration job\n2. Increase connection pool to 100\n3. Restart payment gateway pods\n4. Monitor failure rate for 30 minutes",
    },
    {
        "title": "Customer Churn Risk — Enterprise Segment",
        "description": "Convergence of negative signals from enterprise customers: cancellation threats, billing complaints, and competitor activity. 3 enterprise accounts (combined ARR: $380K) showing high churn indicators.",
        "severity": "high",
        "status": "active",
        "root_cause_hypothesis": "Combination of recent reliability issues and aggressive competitor pricing is eroding enterprise confidence. The billing bug affecting proration adds friction.",
        "recommended_actions": "1. Executive outreach to Acme Corp within 24 hours\n2. Expedite billing bug fix (proration logic)\n3. Prepare competitive response brief\n4. Schedule QBRs with at-risk accounts",
    },
    {
        "title": "Infrastructure Reliability Degradation",
        "description": "Multiple system health signals indicate compounding infrastructure issues: replication lag, cache invalidation, and memory leaks. User-facing impact confirmed via Reddit reports.",
        "severity": "high",
        "status": "active",
        "root_cause_hypothesis": "Recent deployment introduced cache-busting changes while a migration job is consuming database resources. Memory leak in ML service is a separate but concurrent issue.",
        "recommended_actions": "1. Roll back CDN cache configuration\n2. Investigate and fix ML service memory leak\n3. Reschedule migration to off-peak hours\n4. Post status page update",
    },
]


@router.post("/seed")
async def seed_demo_data(
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Seed the database with a rich, pre-built demo dataset.

    This creates realistic signals across all sources, processes them through
    NLP + risk scoring, and creates pre-built incidents with root cause hypotheses.
    """
    # Check if already seeded
    count = (
        await session.execute(
            select(func.count(Signal.id)).where(Signal.tenant_id == tenant_id)
        )
    ).scalar() or 0
    if count > 30:
        return {
            "status": "already_seeded",
            "message": f"Database already has {count} signals. Use POST /api/demo/reset to clear first.",
            "signal_count": count,
        }

    now = datetime.utcnow()
    created_signals: list[Signal] = []

    # Create signals with varied timestamps over the past 72 hours
    for i, demo in enumerate(_DEMO_SIGNALS):
        hours_ago = random.uniform(1, 72)
        ts = now - timedelta(hours=hours_ago)

        sig = Signal(
            tenant_id=tenant_id,
            source=demo["source"],
            source_id=f"demo-{demo['source']}-{i}",
            title=demo["title"],
            content=demo["content"],
            timestamp=ts,
            metadata_json=json.dumps(demo.get("metadata", {})),
        )
        session.add(sig)
        await session.flush()  # get the ID

        # Process through NLP
        try:
            processed = _pipeline.process(sig.content)
            sig.sentiment_score = processed.sentiment.raw_score
            sig.sentiment_label = processed.sentiment.label
            sig.summary = processed.summary
            sig.entities_json = json.dumps(
                [{"text": e.text, "label": e.label} for e in processed.entities]
            )
            sig.embedding_json = json.dumps(processed.embedding)
            _pipeline.add_to_index(sig.id, processed.embedding)

            # Risk scoring
            metadata = demo.get("metadata", {})
            risk = _scorer.score(
                sentiment_score=processed.sentiment.raw_score,
                source=demo["source"],
                metadata=metadata,
            )
            sig.risk_score = risk.composite_score
            sig.risk_tier = risk.tier

            session.add(RiskAssessment(
                signal_id=sig.id,
                tenant_id=tenant_id,
                composite_score=risk.composite_score,
                sentiment_component=risk.sentiment_component,
                anomaly_component=risk.anomaly_component,
                ticket_volume_component=risk.ticket_volume_component,
                revenue_component=risk.revenue_component,
                engagement_component=risk.engagement_component,
                tier=risk.tier,
                explanation=risk.explanation,
            ))
        except Exception as e:
            logger.warning(f"Error processing demo signal {i}: {e}")

        created_signals.append(sig)

    # Create pre-built incidents linked to relevant signals
    for demo_inc in _DEMO_INCIDENTS:
        # Pick 2-4 related signals
        related = random.sample(created_signals, min(4, len(created_signals)))
        hours_ago = random.uniform(2, 48)

        incident = Incident(
            tenant_id=tenant_id,
            title=demo_inc["title"],
            description=demo_inc["description"],
            severity=demo_inc["severity"],
            status=demo_inc["status"],
            start_time=now - timedelta(hours=hours_ago),
            related_signal_ids_json=json.dumps([s.id for s in related]),
            root_cause_hypothesis=demo_inc["root_cause_hypothesis"],
            recommended_actions=demo_inc["recommended_actions"],
        )
        session.add(incident)

    await session.commit()

    logger.info(f"Seeded {len(created_signals)} signals and {len(_DEMO_INCIDENTS)} incidents")

    return {
        "status": "success",
        "signals_created": len(created_signals),
        "incidents_created": len(_DEMO_INCIDENTS),
        "message": "Demo data seeded successfully. Your dashboard is ready to explore.",
    }


@router.post("/reset")
async def reset_demo_data(
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Clear all demo data (signals with source_id starting with 'demo-')."""
    demo_signal_ids_result = await session.execute(
        select(Signal.id).where(
            Signal.tenant_id == tenant_id,
            Signal.source_id.like("demo-%"),
        )
    )
    demo_signal_ids = [row[0] for row in demo_signal_ids_result.all()]

    deleted_risk = 0
    if demo_signal_ids:
        risk_result = await session.execute(
            delete(RiskAssessment).where(
                RiskAssessment.tenant_id == tenant_id,
                RiskAssessment.signal_id.in_(demo_signal_ids),
            )
        )
        deleted_risk = risk_result.rowcount or 0

    incident_titles = [item["title"] for item in _DEMO_INCIDENTS]
    incident_result = await session.execute(
        delete(Incident).where(
            Incident.tenant_id == tenant_id,
            Incident.title.in_(incident_titles),
        )
    )

    signal_result = await session.execute(
        delete(Signal).where(
            Signal.tenant_id == tenant_id,
            Signal.source_id.like("demo-%"),
        )
    )
    await session.commit()

    return {
        "status": "success",
        "deleted": signal_result.rowcount or 0,
        "deleted_signals": signal_result.rowcount or 0,
        "deleted_incidents": incident_result.rowcount or 0,
        "deleted_risk_assessments": deleted_risk,
        "message": (
            f"Removed {signal_result.rowcount or 0} demo signals, "
            f"{incident_result.rowcount or 0} demo incidents, and "
            f"{deleted_risk} risk assessments for tenant '{tenant_id}'."
        ),
    }
