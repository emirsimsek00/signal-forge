"""AI Chat API — Natural language query interface over signals."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, func, desc, or_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database import get_session
from backend.models.signal import Signal
from backend.nlp.pipeline import NLPPipeline

router = APIRouter(prefix="/api/chat", tags=["chat"])

_pipeline = NLPPipeline(use_mock=settings.use_mock_ml)


# ── Request / Response schemas ──────────────────────────────────


class ChatRequest(BaseModel):
    query: str


class CitedSignal(BaseModel):
    id: int
    source: str
    title: Optional[str]
    risk_tier: Optional[str]
    sentiment_label: Optional[str]
    snippet: str


class ChatResponse(BaseModel):
    answer: str
    intent: str
    cited_signals: list[CitedSignal]
    signal_count: int


# ── Intent classification ───────────────────────────────────────

_INTENT_PATTERNS = {
    "search": [
        r"\b(find|show|list|get|what|which)\b.*\b(signal|post|article|alert|mention)\b",
        r"\b(from|on|about)\b.*\b(reddit|news|zendesk|stripe|pagerduty)\b",
    ],
    "summarize": [
        r"\b(summar|overview|brief|recap|digest|report)\b",
        r"\b(top|main|key)\b.*\b(risk|issue|alert|concern)\b",
    ],
    "analyze": [
        r"\b(analyz|assess|evaluat|investigat|explain|trend)\b",
        r"\b(why|how come|root cause|what happened)\b",
    ],
    "count": [
        r"\b(how many|count|total|number of)\b",
    ],
    "compare": [
        r"\b(compar|differ|versus|vs|between)\b",
    ],
}


def classify_intent(query: str) -> str:
    """Classify the user's intent from the query text."""
    q = query.lower()
    for intent, patterns in _INTENT_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, q):
                return intent
    return "search"  # default


# ── Query parsing ───────────────────────────────────────────────


def parse_filters(query: str) -> dict:
    """Extract source, risk tier, time window, and keywords from the query."""
    q = query.lower()
    filters: dict = {}

    # Source detection
    sources = ["reddit", "news", "zendesk", "stripe", "pagerduty", "system", "financial"]
    for src in sources:
        if src in q:
            filters["source"] = src
            break

    # Risk tier detection
    tiers = ["critical", "high", "moderate", "low"]
    for tier in tiers:
        if tier in q:
            filters["risk_tier"] = tier
            break

    # Sentiment detection
    if any(w in q for w in ["negative", "bad", "concerning", "alarming"]):
        filters["sentiment"] = "negative"
    elif any(w in q for w in ["positive", "good", "great"]):
        filters["sentiment"] = "positive"

    # Time window detection
    time_patterns = [
        (r"last\s+(\d+)\s+hour", "hours"),
        (r"past\s+(\d+)\s+hour", "hours"),
        (r"last\s+(\d+)\s+day", "days"),
        (r"past\s+(\d+)\s+day", "days"),
        (r"today", None),
        (r"last\s+24\s+hour", None),
    ]
    for pattern, unit in time_patterns:
        m = re.search(pattern, q)
        if m:
            if unit == "hours":
                filters["since"] = datetime.utcnow() - timedelta(hours=int(m.group(1)))
            elif unit == "days":
                filters["since"] = datetime.utcnow() - timedelta(days=int(m.group(1)))
            elif pattern in ("today", r"last\s+24\s+hour"):
                filters["since"] = datetime.utcnow() - timedelta(hours=24)
            break

    # Keywords (strip out recognized filter words)
    stop_words = set(sources + tiers + [
        "signal", "signals", "post", "posts", "article", "articles",
        "find", "show", "list", "get", "what", "which", "the", "a", "an",
        "from", "on", "about", "in", "with", "are", "is", "last", "past",
        "hour", "hours", "day", "days", "today", "me", "all", "any",
        "mention", "mentions", "mentioning", "that", "how", "many",
        "summarize", "summary", "analyze", "top", "risk", "risks",
    ])
    words = re.findall(r'\b[a-z]+\b', q)
    keywords = [w for w in words if w not in stop_words and len(w) > 2]
    if keywords:
        filters["keywords"] = keywords

    return filters


# ── Query execution ─────────────────────────────────────────────


async def search_signals(
    session: AsyncSession,
    filters: dict,
    limit: int = 15,
) -> list[Signal]:
    """Search signals using parsed filters."""
    query = select(Signal).order_by(desc(Signal.timestamp))

    if "source" in filters:
        query = query.where(Signal.source == filters["source"])
    if "risk_tier" in filters:
        query = query.where(Signal.risk_tier == filters["risk_tier"])
    if "sentiment" in filters:
        query = query.where(Signal.sentiment_label == filters["sentiment"])
    if "since" in filters:
        query = query.where(Signal.timestamp >= filters["since"])

    if "keywords" in filters:
        keyword_conditions = []
        for kw in filters["keywords"]:
            keyword_conditions.append(Signal.content.ilike(f"%{kw}%"))
            keyword_conditions.append(Signal.title.ilike(f"%{kw}%"))
        if keyword_conditions:
            query = query.where(or_(*keyword_conditions))

    query = query.limit(limit)
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_signal_stats(session: AsyncSession, filters: dict) -> dict:
    """Get aggregate stats for the filtered signal set."""
    query = select(
        func.count(Signal.id).label("total"),
        func.avg(Signal.risk_score).label("avg_risk"),
    )

    if "source" in filters:
        query = query.where(Signal.source == filters["source"])
    if "risk_tier" in filters:
        query = query.where(Signal.risk_tier == filters["risk_tier"])
    if "sentiment" in filters:
        query = query.where(Signal.sentiment_label == filters["sentiment"])
    if "since" in filters:
        query = query.where(Signal.timestamp >= filters["since"])

    result = await session.execute(query)
    row = result.one()
    return {"total": row.total or 0, "avg_risk": round(float(row.avg_risk or 0), 3)}


# ── Response generation ─────────────────────────────────────────


def generate_search_answer(query: str, signals: list[Signal], stats: dict) -> str:
    """Generate a natural language answer for search queries."""
    if not signals:
        return f"I didn't find any signals matching your query. Try broadening your search or ingesting more data."

    answer_parts = [f"Found **{stats['total']} signals** matching your query"]
    if stats["avg_risk"] > 0:
        answer_parts[0] += f" (avg risk: {stats['avg_risk']:.1%})"
    answer_parts[0] += "."

    # Group by source
    by_source: dict[str, int] = {}
    for s in signals:
        by_source[s.source] = by_source.get(s.source, 0) + 1

    if len(by_source) > 1:
        source_str = ", ".join(f"{v} from {k}" for k, v in sorted(by_source.items(), key=lambda x: -x[1]))
        answer_parts.append(f"\n**Sources:** {source_str}")

    # High risk highlights
    critical = [s for s in signals if s.risk_tier in ("critical", "high")]
    if critical:
        answer_parts.append(f"\n⚠️ **{len(critical)} high/critical risk** signals detected:")
        for s in critical[:3]:
            title = s.title or s.content[:60]
            answer_parts.append(f"- `{s.source}` • {title} (risk: {s.risk_score:.1%})")

    # Recent highlights
    answer_parts.append(f"\n**Most recent:**")
    for s in signals[:5]:
        title = s.title or s.content[:60]
        sentiment = f" [{s.sentiment_label}]" if s.sentiment_label else ""
        answer_parts.append(f"- #{s.id} `{s.source}` • {title}{sentiment}")

    return "\n".join(answer_parts)


def generate_summary_answer(signals: list[Signal], stats: dict) -> str:
    """Generate a summary/brief of the signal landscape."""
    if not signals:
        return "No signals available to summarize. Try ingesting some data first."

    # Tier breakdown
    tier_counts: dict[str, int] = {}
    sentiment_counts: dict[str, int] = {}
    for s in signals:
        tier_counts[s.risk_tier or "unknown"] = tier_counts.get(s.risk_tier or "unknown", 0) + 1
        sentiment_counts[s.sentiment_label or "unknown"] = sentiment_counts.get(s.sentiment_label or "unknown", 0) + 1

    parts = [f"## Signal Intelligence Summary\n"]
    parts.append(f"Analyzing **{stats['total']} signals** with average risk of **{stats['avg_risk']:.1%}**.\n")

    # Risk overview
    parts.append("### Risk Breakdown")
    for tier in ["critical", "high", "moderate", "low"]:
        if tier in tier_counts:
            emoji = {"critical": "🔴", "high": "🟠", "moderate": "🟡", "low": "🟢"}.get(tier, "⚪")
            parts.append(f"- {emoji} **{tier.capitalize()}**: {tier_counts[tier]} signals")

    # Sentiment overview
    parts.append("\n### Sentiment")
    for label in ["negative", "neutral", "positive"]:
        if label in sentiment_counts:
            emoji = {"negative": "😟", "neutral": "😐", "positive": "😊"}.get(label, "❓")
            parts.append(f"- {emoji} **{label.capitalize()}**: {sentiment_counts[label]}")

    # Key signals
    critical = [s for s in signals if s.risk_tier in ("critical", "high")]
    if critical:
        parts.append(f"\n### ⚠️ Top Alerts ({len(critical)})")
        for s in critical[:5]:
            title = s.title or s.content[:60]
            parts.append(f"- #{s.id} `{s.source}` • {title}")

    # Summaries from NLP
    summarized = [s for s in signals[:5] if s.summary]
    if summarized:
        parts.append("\n### Key Highlights")
        for s in summarized:
            parts.append(f"- {s.summary}")

    return "\n".join(parts)


def generate_count_answer(query: str, stats: dict, filters: dict) -> str:
    """Generate an answer for count queries."""
    context_parts = []
    if "source" in filters:
        context_parts.append(f"from **{filters['source']}**")
    if "risk_tier" in filters:
        context_parts.append(f"with **{filters['risk_tier']}** risk")
    if "sentiment" in filters:
        context_parts.append(f"with **{filters['sentiment']}** sentiment")

    context = " ".join(context_parts) if context_parts else "across all sources"
    return f"There are **{stats['total']} signals** {context}, with an average risk score of **{stats['avg_risk']:.1%}**."


# ── Main endpoint ───────────────────────────────────────────────


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    session: AsyncSession = Depends(get_session),
):
    """Process a natural language query about signals."""
    query = request.query.strip()
    if not query:
        return ChatResponse(
            answer="Please ask a question about your signals.",
            intent="empty",
            cited_signals=[],
            signal_count=0,
        )

    # 1. Classify intent
    intent = classify_intent(query)

    # 2. Parse filters
    filters = parse_filters(query)

    # 3. Search signals
    signals = await search_signals(session, filters, limit=15)
    stats = await get_signal_stats(session, filters)

    # 4. Generate answer based on intent
    if intent == "summarize":
        answer = generate_summary_answer(signals, stats)
    elif intent == "count":
        answer = generate_count_answer(query, stats, filters)
    else:
        answer = generate_search_answer(query, signals, stats)

    # 5. Build cited signals
    cited = [
        CitedSignal(
            id=s.id,
            source=s.source,
            title=s.title,
            risk_tier=s.risk_tier,
            sentiment_label=s.sentiment_label,
            snippet=(s.summary or s.content[:100]),
        )
        for s in signals[:10]
    ]

    return ChatResponse(
        answer=answer,
        intent=intent,
        cited_signals=cited,
        signal_count=stats["total"],
    )
