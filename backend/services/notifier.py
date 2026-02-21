"""Notification dispatch service — Email (Resend) + Slack webhooks."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional

import httpx

from backend.config import settings

logger = logging.getLogger("signalforge.notifier")

# ── Resend email ──────────────────────────────────────────────

async def send_email(to: str, subject: str, html: str) -> dict:
    """Send an email via Resend API.  Returns {"id": ..., "status": "sent"} or raises."""
    if not settings.resend_api_key:
        logger.warning("Resend API key not configured — skipping email")
        return {"status": "skipped", "reason": "RESEND_API_KEY not set"}

    import resend
    resend.api_key = settings.resend_api_key

    try:
        result = resend.Emails.send({
            "from": settings.notification_from_email,
            "to": [to],
            "subject": subject,
            "html": html,
        })
        logger.info(f"Email sent to {to}: {subject}")
        return {"status": "sent", "id": result.get("id", "")}
    except Exception as exc:
        logger.error(f"Failed to send email to {to}: {exc}")
        raise


# ── Slack webhook ─────────────────────────────────────────────

async def send_slack(webhook_url: str, payload: dict) -> dict:
    """Post a message to a Slack webhook. Returns status."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(webhook_url, json=payload, timeout=10)
            resp.raise_for_status()
        logger.info(f"Slack notification sent to webhook")
        return {"status": "sent"}
    except Exception as exc:
        logger.error(f"Slack notification failed: {exc}")
        raise


# ── Message formatting ────────────────────────────────────────

def format_signal_email(signal_data: dict) -> tuple[str, str]:
    """Return (subject, html) for a critical signal alert email."""
    title = signal_data.get("title") or signal_data.get("source", "Signal")
    risk_score = signal_data.get("risk_score", 0)
    risk_tier = signal_data.get("risk_tier", "unknown")
    source = signal_data.get("source", "unknown")
    summary = signal_data.get("summary", signal_data.get("content", "")[:200])

    subject = f"🚨 SignalForge Alert: {risk_tier.upper()} risk signal from {source}"
    html = f"""
    <div style="font-family: -apple-system, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: linear-gradient(135deg, #ef4444, #dc2626); padding: 20px; border-radius: 12px 12px 0 0;">
            <h2 style="color: white; margin: 0;">⚡ Critical Signal Detected</h2>
        </div>
        <div style="background: #1a1a2e; color: #e0e0e0; padding: 24px; border-radius: 0 0 12px 12px;">
            <h3 style="color: #f8f8f8; margin-top: 0;">{title}</h3>
            <table style="width: 100%; border-collapse: collapse;">
                <tr><td style="padding: 8px 0; color: #999;">Source</td><td style="padding: 8px 0;">{source}</td></tr>
                <tr><td style="padding: 8px 0; color: #999;">Risk Score</td><td style="padding: 8px 0;">{risk_score:.2f}</td></tr>
                <tr><td style="padding: 8px 0; color: #999;">Risk Tier</td><td style="padding: 8px 0; color: #ef4444; font-weight: bold;">{risk_tier.upper()}</td></tr>
            </table>
            <p style="margin-top: 16px; color: #ccc;">{summary}</p>
            <a href="#" style="display: inline-block; margin-top: 16px; padding: 10px 20px;
               background: #6366f1; color: white; border-radius: 8px; text-decoration: none;">
                View in SignalForge →
            </a>
        </div>
    </div>
    """
    return subject, html


def format_incident_email(incident_data: dict, event: str = "created") -> tuple[str, str]:
    """Return (subject, html) for an incident notification email."""
    title = incident_data.get("title", "Incident")
    severity = incident_data.get("severity", "medium")
    status = incident_data.get("status", "active")
    description = incident_data.get("description", "")[:300]

    severity_colors = {"critical": "#ef4444", "high": "#f97316", "medium": "#eab308", "low": "#22c55e"}
    color = severity_colors.get(severity, "#6366f1")

    subject = f"🔔 SignalForge: Incident {event} — {title}"
    html = f"""
    <div style="font-family: -apple-system, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: linear-gradient(135deg, {color}, {color}dd); padding: 20px; border-radius: 12px 12px 0 0;">
            <h2 style="color: white; margin: 0;">📋 Incident {event.title()}</h2>
        </div>
        <div style="background: #1a1a2e; color: #e0e0e0; padding: 24px; border-radius: 0 0 12px 12px;">
            <h3 style="color: #f8f8f8; margin-top: 0;">{title}</h3>
            <table style="width: 100%; border-collapse: collapse;">
                <tr><td style="padding: 8px 0; color: #999;">Severity</td><td style="padding: 8px 0; color: {color}; font-weight: bold;">{severity.upper()}</td></tr>
                <tr><td style="padding: 8px 0; color: #999;">Status</td><td style="padding: 8px 0;">{status}</td></tr>
            </table>
            <p style="margin-top: 16px; color: #ccc;">{description}</p>
        </div>
    </div>
    """
    return subject, html


def format_signal_slack(signal_data: dict) -> dict:
    """Return Slack Block Kit payload for a signal alert."""
    title = signal_data.get("title") or signal_data.get("source", "Signal")
    risk_tier = signal_data.get("risk_tier", "unknown")
    source = signal_data.get("source", "unknown")
    risk_score = signal_data.get("risk_score", 0)

    return {
        "blocks": [
            {"type": "header", "text": {"type": "plain_text", "text": f"🚨 {risk_tier.upper()} Risk Signal", "emoji": True}},
            {"type": "section", "fields": [
                {"type": "mrkdwn", "text": f"*Source:*\n{source}"},
                {"type": "mrkdwn", "text": f"*Risk Score:*\n{risk_score:.2f}"},
            ]},
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*{title}*\n{signal_data.get('summary', '')[:200]}"}},
            {"type": "divider"},
        ]
    }


def format_incident_slack(incident_data: dict, event: str = "created") -> dict:
    """Return Slack Block Kit payload for an incident notification."""
    title = incident_data.get("title", "Incident")
    severity = incident_data.get("severity", "medium")

    emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(severity, "⚪")

    return {
        "blocks": [
            {"type": "header", "text": {"type": "plain_text", "text": f"{emoji} Incident {event.title()}", "emoji": True}},
            {"type": "section", "fields": [
                {"type": "mrkdwn", "text": f"*Title:*\n{title}"},
                {"type": "mrkdwn", "text": f"*Severity:*\n{severity.upper()}"},
            ]},
            {"type": "section", "text": {"type": "mrkdwn", "text": incident_data.get("description", "")[:300]}},
            {"type": "divider"},
        ]
    }


# ── Dispatcher ────────────────────────────────────────────────

async def notify_tenant(
    tenant_id: str,
    trigger: str,
    context: dict,
    session=None,
) -> list[dict]:
    """Look up notification preferences for a tenant and dispatch to all active channels.

    Args:
        tenant_id: Tenant to notify
        trigger: One of "critical_signal", "incident_created", "incident_escalated", "incident_resolved", "daily_digest"
        context: Data dict (signal or incident data)
        session: Optional DB session (if provided, logs delivery)

    Returns:
        List of delivery results
    """
    from backend.models.notification import NotificationPreference, NotificationLog
    from sqlalchemy import select

    if session is None:
        # No session means we can't look up preferences — use global defaults
        results = []
        if settings.slack_webhook_url:
            try:
                if "signal" in trigger:
                    payload = format_signal_slack(context)
                else:
                    payload = format_incident_slack(context, trigger.split("_")[-1])
                await send_slack(settings.slack_webhook_url, payload)
                results.append({"channel": "slack", "status": "sent"})
            except Exception as exc:
                results.append({"channel": "slack", "status": "failed", "error": str(exc)})
        return results

    # Look up preferences from database
    prefs_result = await session.execute(
        select(NotificationPreference).where(
            NotificationPreference.tenant_id == tenant_id,
            NotificationPreference.is_active == True,
        )
    )
    preferences = prefs_result.scalars().all()

    results = []
    for pref in preferences:
        try:
            pref_triggers = json.loads(pref.triggers) if isinstance(pref.triggers, str) else pref.triggers
        except json.JSONDecodeError:
            pref_triggers = []

        if trigger not in pref_triggers:
            continue

        status = "sent"
        error = None
        subject = ""

        try:
            if pref.channel == "email":
                if "signal" in trigger:
                    subject, html = format_signal_email(context)
                else:
                    event = trigger.split("_")[-1]
                    subject, html = format_incident_email(context, event)
                await send_email(pref.target, subject, html)

            elif pref.channel == "slack":
                if "signal" in trigger:
                    payload = format_signal_slack(context)
                else:
                    event = trigger.split("_")[-1]
                    payload = format_incident_slack(context, event)
                await send_slack(pref.target, payload)
                subject = f"Slack: {trigger}"

        except Exception as exc:
            status = "failed"
            error = str(exc)
            logger.error(f"Notification dispatch failed: {pref.channel} -> {pref.target}: {exc}")

        # Log the delivery
        log = NotificationLog(
            tenant_id=tenant_id,
            channel=pref.channel,
            trigger=trigger,
            subject=subject,
            status=status,
            error=error,
        )
        session.add(log)
        results.append({"channel": pref.channel, "target": pref.target, "status": status, "error": error})

    await session.commit()
    return results
