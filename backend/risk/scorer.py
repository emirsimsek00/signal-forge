"""Risk scoring engine — computes composite risk scores with explainability."""

from __future__ import annotations

from dataclasses import dataclass

from backend.config import settings


@dataclass
class RiskResult:
    """Result of risk scoring a signal."""

    composite_score: float  # 0.0 to 1.0
    tier: str  # low, moderate, high, critical
    sentiment_component: float
    anomaly_component: float
    ticket_volume_component: float
    revenue_component: float
    engagement_component: float
    explanation: str


class RiskScorer:
    """Computes composite risk scores using configurable weighted formula.

    Risk Score = W_sentiment × sentiment_risk
               + W_anomaly  × anomaly_magnitude
               + W_ticket   × ticket_volume_spike
               + W_revenue  × revenue_deviation
               + W_engage   × engagement_surge
    """

    def __init__(self) -> None:
        self.weights = {
            "sentiment": settings.risk_weight_sentiment,
            "anomaly": settings.risk_weight_anomaly,
            "ticket_volume": settings.risk_weight_ticket_volume,
            "revenue": settings.risk_weight_revenue,
            "engagement": settings.risk_weight_engagement,
        }

    def score(
        self,
        sentiment_score: float | None = None,
        anomaly_magnitude: float | None = None,
        ticket_volume_spike: float | None = None,
        revenue_deviation: float | None = None,
        engagement_surge: float | None = None,
        source: str | None = None,
        metadata: dict | None = None,
    ) -> RiskResult:
        """Compute composite risk from individual signal components.

        All inputs should be normalized to 0.0-1.0 range where 1.0 = highest risk.
        """
        # Normalize sentiment: negative sentiment → higher risk
        s_risk = self._normalize_sentiment(sentiment_score)
        a_risk = anomaly_magnitude if anomaly_magnitude is not None else 0.0
        t_risk = ticket_volume_spike if ticket_volume_spike is not None else 0.0
        r_risk = revenue_deviation if revenue_deviation is not None else 0.0
        e_risk = engagement_surge if engagement_surge is not None else 0.0

        # Infer risk components from metadata when direct values aren't provided
        if metadata:
            if a_risk == 0.0 and metadata.get("is_anomaly"):
                a_risk = min(1.0, metadata.get("value", 50) / 100) if "value" in metadata else 0.7
            if t_risk == 0.0 and metadata.get("urgency") == "high":
                t_risk = 0.7
            elif t_risk == 0.0 and metadata.get("urgency") == "medium":
                t_risk = 0.4

            # Generic numeric signals often available in financial/system metadata.
            delta_pct = abs(self._to_float(metadata.get("delta_pct")))
            if delta_pct > 0 and r_risk == 0.0:
                r_risk = min(1.0, delta_pct / 10.0)

            metric_name = str(metadata.get("metric_name") or "").lower()
            if metric_name and a_risk == 0.0:
                if "latency" in metric_name or "error" in metric_name:
                    value = self._to_float(metadata.get("value"))
                    if value > 0:
                        # Light normalization for typical service metrics.
                        a_risk = min(1.0, value / 1000.0)

            # Source-specific risk mapping for incident ops/payment systems.
            src = (source or "").lower()
            if src == "pagerduty":
                status = str(metadata.get("status") or "").lower()
                urgency = str(metadata.get("urgency") or "").lower()
                if status in {"triggered", "acknowledged"}:
                    a_risk = max(a_risk, 0.75)
                    e_risk = max(e_risk, 0.5)
                if urgency == "high":
                    t_risk = max(t_risk, 0.85)
                    a_risk = max(a_risk, 0.65)
                elif urgency == "low":
                    t_risk = max(t_risk, 0.2)

            elif src == "stripe":
                event_type = str(metadata.get("event_type") or "").lower()
                amount = abs(self._to_float(metadata.get("amount")))
                if any(k in event_type for k in ("failed", "dispute", "fraud", "chargeback")):
                    a_risk = max(a_risk, 0.65)
                    r_risk = max(r_risk, 0.55)
                    t_risk = max(t_risk, 0.5)
                if any(k in event_type for k in ("dispute", "fraud", "chargeback")):
                    a_risk = max(a_risk, 0.9)
                    r_risk = max(r_risk, 0.8)
                    e_risk = max(e_risk, 0.55)
                if amount > 0:
                    # Scale large financial impact events into revenue component.
                    r_risk = max(r_risk, min(1.0, amount / 20000.0))

        # Weighted composite
        composite = (
            self.weights["sentiment"] * s_risk
            + self.weights["anomaly"] * a_risk
            + self.weights["ticket_volume"] * t_risk
            + self.weights["revenue"] * r_risk
            + self.weights["engagement"] * e_risk
        )

        # Clamp to [0, 1]
        composite = max(0.0, min(1.0, composite))

        tier = self._classify_tier(composite)
        explanation = self._explain(
            composite, tier, s_risk, a_risk, t_risk, r_risk, e_risk
        )

        return RiskResult(
            composite_score=round(composite, 4),
            tier=tier,
            sentiment_component=round(s_risk, 4),
            anomaly_component=round(a_risk, 4),
            ticket_volume_component=round(t_risk, 4),
            revenue_component=round(r_risk, 4),
            engagement_component=round(e_risk, 4),
            explanation=explanation,
        )

    def _normalize_sentiment(self, raw_score: float | None) -> float:
        """Convert sentiment raw_score (-1 to 1) to risk (0 to 1).

        Negative sentiment → high risk. Positive → low risk.
        """
        if raw_score is None:
            return 0.0
        # raw_score: -1.0 (very negative) to 1.0 (very positive)
        # risk: 0.0 (positive/safe) to 1.0 (very negative/risky)
        return max(0.0, min(1.0, (1.0 - raw_score) / 2.0))

    def _classify_tier(self, score: float) -> str:
        if score >= 0.75:
            return "critical"
        elif score >= 0.5:
            return "high"
        elif score >= 0.25:
            return "moderate"
        else:
            return "low"

    def _explain(
        self,
        composite: float,
        tier: str,
        sentiment: float,
        anomaly: float,
        ticket: float,
        revenue: float,
        engagement: float,
    ) -> str:
        parts = []
        components = [
            ("Sentiment risk", sentiment, self.weights["sentiment"]),
            ("Anomaly magnitude", anomaly, self.weights["anomaly"]),
            ("Ticket volume pressure", ticket, self.weights["ticket_volume"]),
            ("Revenue deviation", revenue, self.weights["revenue"]),
            ("Engagement surge", engagement, self.weights["engagement"]),
        ]

        # Find top contributors
        weighted = [(name, val, w, val * w) for name, val, w in components if val > 0]
        weighted.sort(key=lambda x: x[3], reverse=True)

        if weighted:
            top = weighted[0]
            parts.append(
                f"Primary driver: {top[0]} ({top[1]:.0%} × {top[2]:.0%} weight = {top[3]:.2f} contribution)"
            )

        if len(weighted) > 1:
            secondary = [f"{w[0]} ({w[1]:.0%})" for w in weighted[1:3]]
            parts.append(f"Secondary factors: {', '.join(secondary)}")

        parts.append(f"Composite score: {composite:.2f} → {tier.upper()} tier")

        return ". ".join(parts) + "."

    @staticmethod
    def _to_float(value: object) -> float:
        try:
            return float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 0.0
