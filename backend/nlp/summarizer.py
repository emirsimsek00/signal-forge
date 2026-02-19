"""Text summarization for executive brief generation."""

from __future__ import annotations


class Summarizer:
    """Summarizes text using HuggingFace or mock."""

    def __init__(self, use_mock: bool = True) -> None:
        self.use_mock = use_mock
        self._pipeline = None

    def _load_model(self):
        if self._pipeline is None and not self.use_mock:
            from transformers import pipeline
            self._pipeline = pipeline(
                "summarization",
                model="sshleifer/distilbart-cnn-12-6",
            )

    def summarize(self, text: str, max_length: int = 80) -> str:
        if self.use_mock:
            return self._mock_summarize(text)

        self._load_model()
        result = self._pipeline(text[:1024], max_length=max_length, min_length=20, do_sample=False)
        return result[0]["summary_text"]

    def _mock_summarize(self, text: str) -> str:
        """Extract first 1-2 sentences as a mock summary."""
        sentences = []
        current = []
        for char in text:
            current.append(char)
            if char in ".!?" and len("".join(current).strip()) > 10:
                sentences.append("".join(current).strip())
                current = []
                if len(sentences) >= 2:
                    break
        if current and not sentences:
            sentences.append("".join(current).strip())
        return " ".join(sentences)[:200]
