# backend/src/app/services/session_store.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, List
import time
import uuid


@dataclass
class ChatMessage:
    role: str  # "user" | "assistant"
    content: str


@dataclass
class UserProfile:
    age: Optional[int] = None                 # 모름이면 -1 사용
    residency: Optional[str] = None
    status: Optional[str] = None
    work_last_6m: Optional[str] = None
    welfare: Optional[str] = None
    household: Optional[str] = None

    def is_complete(self) -> bool:
        return all([
            self.age is not None,
            self.residency is not None,
            self.status is not None,
            self.work_last_6m is not None,
            self.welfare is not None,
            self.household is not None,
        ])


@dataclass
class FollowupAnswers:
    employment_type: Optional[str] = None
    ei_insured: Optional[str] = None
    company_size: Optional[str] = None
    seoul_residency_months: Optional[str] = None


@dataclass
class SessionState:
    session_id: str
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    messages: List[ChatMessage] = field(default_factory=list)

    profile: UserProfile = field(default_factory=UserProfile)
    followups: FollowupAnswers = field(default_factory=FollowupAnswers)

    onboarding_step: int = 0
    pending_question_id: Optional[str] = None
    pending_followup_id: Optional[str] = None


class InMemorySessionStore:
    def __init__(self):
        self._sessions: Dict[str, SessionState] = {}

    def get_or_create(self, session_id: Optional[str]) -> SessionState:
        if session_id and session_id in self._sessions:
            return self._sessions[session_id]

        sid = uuid.uuid4().hex
        s = SessionState(session_id=sid)
        self._sessions[sid] = s
        return s

    def save(self, state: SessionState) -> None:
        state.updated_at = time.time()
        self._sessions[state.session_id] = state
