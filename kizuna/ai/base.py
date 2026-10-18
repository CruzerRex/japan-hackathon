"""Provider interfaces for knowledge extraction, assistant answering and video
understanding. Concrete providers are selected explicitly by the user (or
configuration); a failed provider is never silently replaced by another.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class CaptureInput:
    title: str
    expert_name: str
    task_category: str = ""
    machine: str = ""
    tools: list[str] = field(default_factory=list)
    materials: list[str] = field(default_factory=list)
    skills: list[dict] = field(default_factory=list)  # [{code, name}]
    experience_level: str = ""
    transcript: str = ""
    expert_notes: str = ""
    tips: str = ""
    mistakes: str = ""
    troubleshooting: str = ""
    safety_notes: str = ""
    markers: list[dict] = field(default_factory=list)  # [{t_seconds, kind, label, note}]
    has_video: bool = False

    @property
    def notes_blob(self) -> str:
        return "\n".join(x for x in (self.expert_notes, self.tips, self.mistakes, self.troubleshooting,
                                       self.safety_notes) if x)


class ExtractionError(Exception):
    """Raised when a provider cannot produce a result. `code` is one of:
    unavailable, not_configured, rate_limited, auth, timeout, refused, truncated, malformed, invalid_input."""

    def __init__(self, code: str, message: str, retryable: bool = False):
        super().__init__(message)
        self.code, self.message, self.retryable = code, message, retryable


class ExtractionProvider(Protocol):
    name: str
    label: str
    kind: str  # "deterministic" | "llm"

    def status(self) -> dict: ...

    def extract(self, capture: CaptureInput) -> dict: ...


class VideoAnalyzer(Protocol):
    name: str

    def status(self) -> dict: ...

    def analyze(self, file_path: str) -> list[dict]: ...
