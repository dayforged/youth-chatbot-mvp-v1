# backend/src/app/services/followup_questions.py
from __future__ import annotations

from typing import Optional
from .session_store import SessionState


def detect_policy_intent(user_text: str) -> Optional[str]:
    t = (user_text or "").strip().lower()
    if not t:
        return None

    # 도약장려금 계열 키워드 (반쪽 키워드 포함)
    if any(k in t for k in ["도약", "도약장려금", "일자리도약", "청년일자리도약", "일자리 장려금", "청년 장려금", "장려금"]):
        return "job_jump"

    if any(k in t for k in ["국민취업", "국취", "취업지원제도", "취업지원"]):
        return "kua"

    if any(k in t for k in ["희망두배", "희망 두배", "청년통장", "자산형성", "통장"]):
        return "hope_account"

    return None
