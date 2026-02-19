"""Base interfaces for signal ingestion."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class RawSignal:
    """A raw signal from any source before processing."""

    source: str
    content: str
    timestamp: datetime
    title: str | None = None
    source_id: str | None = None
    metadata: dict = field(default_factory=dict)


class SignalSource(ABC):
    """Abstract base class for all signal sources."""

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Identifier for this source type."""
        ...

    @abstractmethod
    async def fetch_signals(self, limit: int = 50) -> list[RawSignal]:
        """Fetch raw signals from the source."""
        ...

    async def health_check(self) -> bool:
        """Check if the source is reachable."""
        return True
