"""Alpha Vantage source — fetches market/financial quote signals."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from backend.config import settings
from backend.ingestion.base import RawSignal, SignalSource


class AlphaVantageSource(SignalSource):
    """Fetch quote snapshots from Alpha Vantage."""

    BASE_URL = "https://www.alphavantage.co/query"

    @property
    def source_name(self) -> str:
        return "alpha_vantage"

    async def fetch_signals(self, limit: int = 50) -> list[RawSignal]:
        if not settings.alpha_vantage_key:
            return []

        symbols = [
            symbol.strip().upper()
            for symbol in settings.alpha_vantage_symbols.split(",")
            if symbol.strip()
        ]
        if not symbols:
            return []

        max_symbols = max(1, min(limit, len(symbols)))
        signals: list[RawSignal] = []

        async with httpx.AsyncClient(timeout=20) as client:
            for symbol in symbols[:max_symbols]:
                quote = await self._fetch_quote(client, symbol)
                if not quote:
                    continue
                signal = self._to_signal(symbol, quote)
                if signal:
                    signals.append(signal)

        return signals

    async def _fetch_quote(self, client: httpx.AsyncClient, symbol: str) -> dict | None:
        resp = await client.get(
            self.BASE_URL,
            params={
                "function": "GLOBAL_QUOTE",
                "symbol": symbol,
                "apikey": settings.alpha_vantage_key,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        if "Note" in data:
            # Free-tier rate-limit reached.
            return None
        return data.get("Global Quote")

    def _to_signal(self, symbol: str, quote: dict | None) -> RawSignal | None:
        if not quote:
            return None

        try:
            price = float(quote.get("05. price", 0) or 0)
            previous_close = float(quote.get("08. previous close", 0) or 0)
            change = float(quote.get("09. change", 0) or 0)
            change_percent_raw = (quote.get("10. change percent", "0%") or "0%").replace("%", "")
            change_percent = float(change_percent_raw)
            volume = int(float(quote.get("06. volume", 0) or 0))
        except (TypeError, ValueError):
            return None

        if price <= 0:
            return None

        is_anomaly = abs(change_percent) >= 3.0
        direction = "up" if change_percent >= 0 else "down"
        title = f"{symbol} {direction} {abs(change_percent):.2f}%"
        content = (
            f"{symbol} quote update: price={price:.2f}, change={change:+.2f} "
            f"({change_percent:+.2f}%), previous_close={previous_close:.2f}, volume={volume}."
        )

        return RawSignal(
            source="financial",
            title=title,
            content=content,
            timestamp=datetime.now(tz=timezone.utc),
            source_id=symbol,
            metadata={
                "provider": "alpha_vantage",
                "symbol": symbol,
                "metric_name": f"{symbol.lower()}_price",
                "value": price,
                "previous_close": previous_close,
                "delta": change,
                "delta_pct": change_percent,
                "volume": volume,
                "is_anomaly": is_anomaly,
            },
        )

    async def health_check(self) -> bool:
        if not settings.alpha_vantage_key:
            return False
        try:
            symbols = [
                symbol.strip().upper()
                for symbol in settings.alpha_vantage_symbols.split(",")
                if symbol.strip()
            ]
            symbol = symbols[0] if symbols else "SPY"
            async with httpx.AsyncClient(timeout=10) as client:
                quote = await self._fetch_quote(client, symbol)
                return quote is not None
        except Exception:
            return False
