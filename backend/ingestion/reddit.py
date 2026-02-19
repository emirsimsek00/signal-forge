"""Reddit signal source — fetches posts from configurable subreddits."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from backend.config import settings
from backend.ingestion.base import RawSignal, SignalSource


class RedditSource(SignalSource):
    """Fetches posts from Reddit via the public JSON API.

    Uses OAuth2 client‑credentials when REDDIT_CLIENT_ID is set.
    Falls back to the unauthenticated `.json` endpoint otherwise
    (lower rate limits but no key required for light usage).
    """

    TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
    BASE = "https://oauth.reddit.com"
    PUBLIC_BASE = "https://www.reddit.com"

    def __init__(self) -> None:
        self._token: str | None = None
        self._subreddits = [s.strip() for s in settings.reddit_subreddits.split(",") if s.strip()]

    @property
    def source_name(self) -> str:
        return "reddit"

    # ── Auth ─────────────────────────────────────────────────────
    async def _ensure_token(self, client: httpx.AsyncClient) -> None:
        if self._token or not settings.reddit_client_id:
            return
        resp = await client.post(
            self.TOKEN_URL,
            data={"grant_type": "client_credentials"},
            auth=(settings.reddit_client_id, settings.reddit_client_secret),
            headers={"User-Agent": "SignalForge/1.0"},
        )
        resp.raise_for_status()
        self._token = resp.json()["access_token"]

    # ── Fetch ────────────────────────────────────────────────────
    async def fetch_signals(self, limit: int = 50) -> list[RawSignal]:
        per_sub = max(1, limit // max(len(self._subreddits), 1))
        signals: list[RawSignal] = []

        async with httpx.AsyncClient(timeout=15) as client:
            await self._ensure_token(client)

            for sub in self._subreddits:
                try:
                    posts = await self._fetch_subreddit(client, sub, per_sub)
                    signals.extend(posts)
                except Exception as exc:
                    print(f"[RedditSource] Error fetching r/{sub}: {exc}")

        return signals[:limit]

    async def _fetch_subreddit(
        self, client: httpx.AsyncClient, subreddit: str, limit: int
    ) -> list[RawSignal]:
        if self._token:
            url = f"{self.BASE}/r/{subreddit}/hot.json"
            headers = {
                "Authorization": f"Bearer {self._token}",
                "User-Agent": "SignalForge/1.0",
            }
        else:
            url = f"{self.PUBLIC_BASE}/r/{subreddit}/hot.json"
            headers = {"User-Agent": "SignalForge/1.0"}

        resp = await client.get(url, params={"limit": limit}, headers=headers)
        resp.raise_for_status()
        listing = resp.json().get("data", {}).get("children", [])

        results: list[RawSignal] = []
        for item in listing:
            post = item.get("data", {})
            if post.get("stickied"):
                continue

            content = post.get("selftext") or post.get("title", "")
            created_utc = post.get("created_utc", 0)
            ts = datetime.fromtimestamp(created_utc, tz=timezone.utc) if created_utc else datetime.now(tz=timezone.utc)

            results.append(RawSignal(
                source="reddit",
                title=post.get("title", ""),
                content=content,
                timestamp=ts,
                source_id=post.get("name", ""),
                metadata={
                    "subreddit": subreddit,
                    "score": post.get("score", 0),
                    "num_comments": post.get("num_comments", 0),
                    "upvote_ratio": post.get("upvote_ratio", 0),
                    "url": post.get("url", ""),
                    "author": post.get("author", ""),
                },
            ))

        return results

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(
                    f"{self.PUBLIC_BASE}/r/all/hot.json",
                    params={"limit": 1},
                    headers={"User-Agent": "SignalForge/1.0"},
                )
                return resp.status_code == 200
        except Exception:
            return False
