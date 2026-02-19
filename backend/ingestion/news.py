"""NewsAPI signal source — fetches top headlines and keyword searches."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from backend.config import settings
from backend.ingestion.base import RawSignal, SignalSource


class NewsSource(SignalSource):
    """Fetches articles from NewsAPI.org.

    Requires NEWSAPI_KEY in .env. Returns empty list without a key.
    """

    BASE = "https://newsapi.org/v2"

    @property
    def source_name(self) -> str:
        return "news"

    async def fetch_signals(self, limit: int = 50) -> list[RawSignal]:
        if not settings.newsapi_key:
            return []

        signals: list[RawSignal] = []
        half = max(1, limit // 2)

        async with httpx.AsyncClient(timeout=15) as client:
            # Top headlines
            try:
                headlines = await self._top_headlines(client, half)
                signals.extend(headlines)
            except Exception as exc:
                print(f"[NewsSource] Error fetching headlines: {exc}")

            # Keyword search
            try:
                keyword_results = await self._search(client, half)
                signals.extend(keyword_results)
            except Exception as exc:
                print(f"[NewsSource] Error searching: {exc}")

        return signals[:limit]

    async def _top_headlines(self, client: httpx.AsyncClient, limit: int) -> list[RawSignal]:
        categories = [c.strip() for c in settings.newsapi_categories.split(",") if c.strip()]
        per_cat = max(1, limit // max(len(categories), 1))
        results: list[RawSignal] = []

        for category in categories:
            resp = await client.get(
                f"{self.BASE}/top-headlines",
                params={
                    "category": category,
                    "country": "us",
                    "pageSize": per_cat,
                    "apiKey": settings.newsapi_key,
                },
            )
            resp.raise_for_status()
            articles = resp.json().get("articles", [])
            results.extend(self._parse_articles(articles, category))

        return results

    async def _search(self, client: httpx.AsyncClient, limit: int) -> list[RawSignal]:
        keywords = [k.strip() for k in settings.newsapi_keywords.split(",") if k.strip()]
        per_kw = max(1, limit // max(len(keywords), 1))
        results: list[RawSignal] = []

        for kw in keywords:
            resp = await client.get(
                f"{self.BASE}/everything",
                params={
                    "q": kw,
                    "sortBy": "publishedAt",
                    "pageSize": per_kw,
                    "apiKey": settings.newsapi_key,
                },
            )
            resp.raise_for_status()
            articles = resp.json().get("articles", [])
            results.extend(self._parse_articles(articles, f"search:{kw}"))

        return results

    @staticmethod
    def _parse_articles(articles: list[dict], category: str) -> list[RawSignal]:
        signals: list[RawSignal] = []
        for article in articles:
            title = article.get("title", "") or ""
            desc = article.get("description", "") or ""
            content = article.get("content", "") or ""
            body = f"{title}. {desc}" if desc else title
            if content and len(content) > len(body):
                body = content

            pub_at = article.get("publishedAt")
            try:
                ts = datetime.fromisoformat(pub_at.replace("Z", "+00:00")) if pub_at else datetime.now(tz=timezone.utc)
            except (ValueError, AttributeError):
                ts = datetime.now(tz=timezone.utc)

            signals.append(RawSignal(
                source="news",
                title=title,
                content=body,
                timestamp=ts,
                source_id=article.get("url", ""),
                metadata={
                    "category": category,
                    "author": article.get("author", ""),
                    "source_name": (article.get("source") or {}).get("name", ""),
                    "url": article.get("url", ""),
                    "image_url": article.get("urlToImage", ""),
                },
            ))
        return signals

    async def health_check(self) -> bool:
        if not settings.newsapi_key:
            return False
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(
                    f"{self.BASE}/top-headlines",
                    params={"country": "us", "pageSize": 1, "apiKey": settings.newsapi_key},
                )
                return resp.status_code == 200
        except Exception:
            return False
