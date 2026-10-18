"""Video understanding adapter.

No video-understanding model is configured in this build. Uploaded videos are
stored securely, streamed to the browser with HTTP range support, and experts
annotate them with timestamped demonstration markers in the Capture Studio.
Those markers are the evidence the extraction pipeline uses for
"demonstrated" steps. The pipeline records `video_analyzed: false` so nobody
can mistake marker-based evidence for automated video analysis.

To add a real model, implement `analyze(file_path) -> [{t_seconds, kind,
label, note, confidence}]` and register it in `registry.py`; its output would
be stored as *suggested* markers awaiting expert confirmation.
"""
from __future__ import annotations

from .base import ExtractionError


class NotConfiguredVideoAnalyzer:
    name = "none"

    def status(self) -> dict:
        return {"available": False, "name": self.name,
                "reason": "No video-understanding model configured. Videos are stored for playback and "
                          "experts add timestamped demonstration markers manually."}

    def analyze(self, file_path: str) -> list[dict]:
        raise ExtractionError("not_configured", "Automated video analysis is not configured in this deployment")
