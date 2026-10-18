"""Procedure review state machine.

    DRAFT ──extract──▶ AI_PROCESSED ──submit──▶ EXPERT_REVIEW ──approve──▶ APPROVED ──publish──▶ PUBLISHED
      │                     │                      │   │                    │                     │
      └──────submit─────────┼──────────────────────┘   ├─reject──▶ REJECTED  └─request_revision─┐  └─(newer version published)─▶ SUPERSEDED
                            │                          └─request_revision──▶ NEEDS_REVISION ◀───┘
                            └───────────────────────────────────────────────────── resubmit ──▶ EXPERT_REVIEW

Only PUBLISHED versions are visible to trainees and used for training,
assessments, the assistant (for trainees) and "approved" knowledge counts.
"""
from __future__ import annotations

from dataclasses import dataclass

DRAFT = "DRAFT"
AI_PROCESSED = "AI_PROCESSED"
EXPERT_REVIEW = "EXPERT_REVIEW"
NEEDS_REVISION = "NEEDS_REVISION"
APPROVED = "APPROVED"
PUBLISHED = "PUBLISHED"
REJECTED = "REJECTED"
SUPERSEDED = "SUPERSEDED"

ALL_STATES = (DRAFT, AI_PROCESSED, EXPERT_REVIEW, NEEDS_REVISION, APPROVED, PUBLISHED, REJECTED, SUPERSEDED)

#: States whose content may still be edited in place.
EDITABLE = {DRAFT, AI_PROCESSED, EXPERT_REVIEW, NEEDS_REVISION}
#: States that represent expert-verified knowledge.
VERIFIED = {APPROVED, PUBLISHED}


@dataclass(frozen=True)
class Transition:
    action: str
    source: frozenset
    target: str
    permission: str
    needs_comment: bool = False
    needs_validation: bool = False


TRANSITIONS: dict[str, Transition] = {
    "submit": Transition("submit", frozenset({DRAFT, AI_PROCESSED, NEEDS_REVISION}), EXPERT_REVIEW,
                         "procedure.submit"),
    "approve": Transition("approve", frozenset({EXPERT_REVIEW}), APPROVED, "procedure.approve",
                          needs_validation=True),
    "reject": Transition("reject", frozenset({EXPERT_REVIEW}), REJECTED, "procedure.approve", needs_comment=True),
    "request_revision": Transition("request_revision", frozenset({EXPERT_REVIEW, APPROVED}), NEEDS_REVISION,
                                   "procedure.approve", needs_comment=True),
    "publish": Transition("publish", frozenset({APPROVED}), PUBLISHED, "procedure.publish"),
}


class TransitionError(Exception):
    pass


def check_transition(current: str, action: str) -> Transition:
    t = TRANSITIONS.get(action)
    if t is None:
        raise TransitionError(f"Unknown action '{action}'")
    if current not in t.source:
        allowed = ", ".join(sorted(t.source))
        raise TransitionError(f"Cannot '{action}' a procedure in state {current} (allowed from: {allowed})")
    return t


def available_actions(current: str) -> list[str]:
    return [name for name, t in TRANSITIONS.items() if current in t.source]
