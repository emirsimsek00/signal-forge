"""Demo data generator — produces realistic fake signals for all source types."""

from __future__ import annotations

import random
from datetime import timedelta

from backend.utils.time import utc_now

from backend.ingestion.base import RawSignal, SignalSource

# ─── Realistic content templates ────────────────────────────────

_REDDIT_POSTS = [
    {
        "title": "Major outage affecting checkout flow",
        "content": "Anyone else seeing 500 errors when trying to checkout? Been happening for the last 2 hours. This is unacceptable for a company this size.",
        "sentiment": "negative",
    },
    {
        "title": "App performance degraded since last update",
        "content": "Ever since v3.2 dropped, the mobile app takes 10+ seconds to load the dashboard. Battery drain is insane too. Rolling back to previous version.",
        "sentiment": "negative",
    },
    {
        "title": "Great new feature release!",
        "content": "Loving the new analytics dashboard. Finally we can see real-time metrics without exporting to a spreadsheet. Team did great work here.",
        "sentiment": "positive",
    },
    {
        "title": "API rate limits are way too aggressive",
        "content": "We're hitting rate limits after just 100 requests/min. Our integration is basically unusable. Support hasn't responded in 3 days.",
        "sentiment": "negative",
    },
    {
        "title": "Comparison: SignalForge vs competitors",
        "content": "Tried several platforms. SignalForge's multimodal approach is unique but the onboarding UX needs work. Documentation is sparse.",
        "sentiment": "mixed",
    },
    {
        "title": "Customer data privacy concern",
        "content": "Found that certain API endpoints return PII in plain text. Has anyone from the security team looked at this? Filing a report.",
        "sentiment": "negative",
    },
    {
        "title": "Shoutout to the support team",
        "content": "Had an integration issue last week. Support resolved it within 2 hours with a detailed walkthrough. Rare to see this level of service.",
        "sentiment": "positive",
    },
    {
        "title": "Revenue dashboard showing wrong numbers",
        "content": "The MRR chart seems to double-count annual subscriptions. Our finance team flagged this during the quarterly review.",
        "sentiment": "negative",
    },
]

_NEWS_ARTICLES = [
    {
        "title": "Tech sector braces for regulatory changes",
        "content": "New data protection regulations expected to impact SaaS companies. Compliance deadlines are tight and penalties are steep, forcing companies to accelerate their privacy infrastructure investments.",
    },
    {
        "title": "AI infrastructure spending surges in Q4",
        "content": "Enterprise AI platform spending grew 45% year-over-year. Companies are prioritizing multimodal AI capabilities and operational intelligence platforms for real-time decision making.",
    },
    {
        "title": "Major cloud provider reports widespread latency issues",
        "content": "US-East-1 region experiencing degraded performance across multiple availability zones. Hundreds of downstream services affected. Root cause under investigation.",
    },
    {
        "title": "Cybersecurity breach at financial platform raises concerns",
        "content": "A prominent fintech platform disclosed unauthorized access to customer transaction data. Industry analysts warn of increased attack sophistication targeting API endpoints.",
    },
    {
        "title": "Customer satisfaction scores decline across SaaS industry",
        "content": "New survey reveals NPS scores dropped an average of 12 points across B2B SaaS. Top complaints include feature bloat, performance degradation, and poor documentation.",
    },
]

_ZENDESK_TICKETS = [
    {
        "title": "Cannot access account — login loop",
        "content": "Customer reports being stuck in an authentication redirect loop. Cleared cookies, tried incognito, different browsers. Issue persists across all devices. Priority: High.",
        "urgency": "high",
    },
    {
        "title": "Billing discrepancy on latest invoice",
        "content": "Invoice shows charge for Enterprise tier but customer is on Pro plan. Amount overcharged by $450. Customer requesting immediate correction and credit.",
        "urgency": "medium",
    },
    {
        "title": "Data export timing out for large datasets",
        "content": "Attempting to export 6 months of signal data (~2M records) results in 504 Gateway Timeout. Customer needs data for compliance audit due next week.",
        "urgency": "high",
    },
    {
        "title": "Feature request: custom alert thresholds",
        "content": "Customer wants ability to set per-source alert thresholds instead of global defaults. Currently generating too many false positives from social media signals.",
        "urgency": "low",
    },
    {
        "title": "API webhook delivery failures",
        "content": "Webhook endpoint returning 200 but payloads not appearing in customer system. Suspect payload format changed in v2.1 API. Need to investigate breaking changes.",
        "urgency": "high",
    },
    {
        "title": "Dashboard loading extremely slowly",
        "content": "Overview page takes 15-20 seconds to render. Customer has 50K+ signals. Suspect query optimization needed for time-range aggregations.",
        "urgency": "medium",
    },
]

_SYSTEM_METRICS = [
    {"metric": "cpu_usage", "normal_range": (30, 60), "anomaly_range": (85, 99)},
    {"metric": "memory_usage", "normal_range": (40, 65), "anomaly_range": (90, 98)},
    {"metric": "api_latency_ms", "normal_range": (50, 200), "anomaly_range": (800, 3000)},
    {"metric": "error_rate_pct", "normal_range": (0.1, 1.5), "anomaly_range": (5, 15)},
    {"metric": "request_rate_rps", "normal_range": (500, 2000), "anomaly_range": (50, 150)},
]

_FINANCIAL_METRICS = [
    {"metric": "mrr", "base": 125000, "normal_delta": (-1000, 2000), "anomaly_delta": (-8000, -3000)},
    {"metric": "churn_rate", "base": 2.5, "normal_delta": (-0.3, 0.3), "anomaly_delta": (1.0, 3.0)},
    {"metric": "arr_growth", "base": 15.0, "normal_delta": (-1, 1), "anomaly_delta": (-8, -3)},
    {"metric": "cac", "base": 350, "normal_delta": (-20, 20), "anomaly_delta": (50, 150)},
]


class DemoDataGenerator(SignalSource):
    """Generates realistic demo signals across all source types."""

    @property
    def source_name(self) -> str:
        return "demo"

    async def fetch_signals(self, limit: int = 50) -> list[RawSignal]:
        signals: list[RawSignal] = []
        now = utc_now()

        # Decide if we inject anomalies for this batch
        inject_anomaly = random.random() < 0.35

        for i in range(limit):
            # Keep generated points within a strict 72h lookback window.
            offset_seconds = random.uniform(0, 72 * 3600)
            ts = now - timedelta(seconds=offset_seconds)
            source_type = random.choice(["reddit", "news", "zendesk", "system", "financial"])

            if source_type == "reddit":
                post = random.choice(_REDDIT_POSTS)
                signals.append(RawSignal(
                    source="reddit",
                    title=post["title"],
                    content=post["content"],
                    timestamp=ts,
                    source_id=f"reddit_{random.randint(10000, 99999)}",
                    metadata={"subreddit": random.choice(["technology", "SaaS", "devops", "sysadmin"]), "upvotes": random.randint(1, 500)},
                ))
            elif source_type == "news":
                article = random.choice(_NEWS_ARTICLES)
                signals.append(RawSignal(
                    source="news",
                    title=article["title"],
                    content=article["content"],
                    timestamp=ts,
                    source_id=f"news_{random.randint(10000, 99999)}",
                    metadata={"publisher": random.choice(["TechCrunch", "Reuters", "Bloomberg", "Ars Technica"])},
                ))
            elif source_type == "zendesk":
                ticket = random.choice(_ZENDESK_TICKETS)
                signals.append(RawSignal(
                    source="zendesk",
                    title=ticket["title"],
                    content=ticket["content"],
                    timestamp=ts,
                    source_id=f"ticket_{random.randint(10000, 99999)}",
                    metadata={"urgency": ticket["urgency"], "assignee": random.choice(["Alice", "Bob", "Carlos", "Dana"])},
                ))
            elif source_type == "system":
                metric = random.choice(_SYSTEM_METRICS)
                is_anom = inject_anomaly and random.random() < 0.4
                rng = metric["anomaly_range"] if is_anom else metric["normal_range"]
                value = round(random.uniform(rng[0], rng[1]), 2)
                signals.append(RawSignal(
                    source="system",
                    title=f"{metric['metric']} = {value}",
                    content=f"System metric {metric['metric']} recorded at {value}. {'⚠ ANOMALY DETECTED' if is_anom else 'Within normal range.'}",
                    timestamp=ts,
                    source_id=f"metric_{random.randint(10000, 99999)}",
                    metadata={"metric_name": metric["metric"], "value": value, "is_anomaly": is_anom},
                ))
            elif source_type == "financial":
                metric = random.choice(_FINANCIAL_METRICS)
                is_anom = inject_anomaly and random.random() < 0.3
                delta_range = metric["anomaly_delta"] if is_anom else metric["normal_delta"]
                delta = round(random.uniform(delta_range[0], delta_range[1]), 2)
                value = round(metric["base"] + delta, 2)
                signals.append(RawSignal(
                    source="financial",
                    title=f"{metric['metric']} = {value}",
                    content=f"Financial metric {metric['metric']} at {value} (delta: {delta:+.2f}). {'⚠ Significant deviation detected.' if is_anom else 'Within expected variance.'}",
                    timestamp=ts,
                    source_id=f"fin_{random.randint(10000, 99999)}",
                    metadata={"metric_name": metric["metric"], "value": value, "delta": delta, "is_anomaly": is_anom},
                ))

        return signals
