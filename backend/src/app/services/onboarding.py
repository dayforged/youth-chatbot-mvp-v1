# backend/src/app/services/onboarding.py
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple
from .session_store import SessionState


# 옵션 정책:
# - include_unknown: "모름" 포함 여부
# - include_none: "해당없음" 포함 여부
# - allow_free_text: 옵션 외 자유입력 저장 허용 여부
# - strict: True이면 옵션/정규화 실패 시 에러를 반환하지만, '먹통'은 만들지 않음(자연어 안내 후 재질문)
PRIMARY_QUESTIONS = [
    {
        "id": "age",
        "text": "먼저, 만 나이가 어떻게 되세요? (숫자만 입력 / 모르면 '모름')",
        "options": None,
        "policy": {"include_unknown": True, "include_none": False, "allow_free_text": True, "strict": True},
    },
    {
        "id": "residency",
        "text": "주민등록상 거주지 기준으로, 서울 거주 여부가 어떻게 되세요?",
        "options": ["서울 거주", "서울 전입 예정", "서울 아님"],
        # 거주지는 '해당없음'이 의미가 애매해서 제외, 모름만 허용
        "policy": {"include_unknown": True, "include_none": False, "allow_free_text": True, "strict": False},
    },
    {
        "id": "status",
        "text": "현재 상태는 어떤가요?",
        "options": ["재직 중", "구직 중(미취업)", "학생(재학/휴학)", "기타(사업 준비/휴직 등)"],
        # 상태는 보통 해당없음 없음, 모름만 허용
        "policy": {"include_unknown": True, "include_none": False, "allow_free_text": True, "strict": False},
    },
    {
        "id": "work_last_6m",
        "text": "최근 6개월 내 근로 이력이 있나요?",
        "options": ["있음", "없음"],
        # 질문 자체가 yes/no라 해당없음은 불필요, 모름만 허용
        "policy": {"include_unknown": True, "include_none": False, "allow_free_text": True, "strict": False},
    },
    {
        "id": "welfare",
        "text": "기초생활수급/차상위 여부가 어떻게 되세요?",
        "options": ["기초수급", "차상위", "해당없음"],
        # 여기서는 해당없음이 필수, 모름도 허용
        "policy": {"include_unknown": True, "include_none": True, "allow_free_text": True, "strict": False},
    },
    {
        "id": "household",
        "text": "가구/세대 기준으로 혼자 거주하나요?",
        "options": ["1인가구(혼자 거주)", "가족과 동거(형제자매 제외)", "기타/모름"],
        # 이미 기타/모름이 있으므로 '해당없음' 굳이 추가하지 않음
        "policy": {"include_unknown": True, "include_none": False, "allow_free_text": True, "strict": False},
    },
]


def needs_onboarding(state: SessionState) -> bool:
    return not state.profile.is_complete()


def _build_options(q: Dict[str, Any]) -> Optional[list[str]]:
    opts = q.get("options")
    if not opts:
        return None
    policy = q.get("policy") or {}
    out = list(opts)

    # 모름 옵션
    if policy.get("include_unknown", False) and "모름" not in out:
        out.append("모름")

    # 해당없음 옵션
    if policy.get("include_none", False) and "해당없음" not in out:
        out.append("해당없음")

    # 중복 제거
    seen = set()
    uniq = []
    for x in out:
        if x not in seen:
            uniq.append(x)
            seen.add(x)
    return uniq


def get_next_primary_question(state: SessionState) -> Dict[str, Any]:
    idx = state.onboarding_step
    if idx >= len(PRIMARY_QUESTIONS):
        state.pending_question_id = None
        return {"id": "done", "text": "기본 정보는 충분히 받았어요. 이제 궁금한 정책을 질문해 주세요.", "options": None}

    q = dict(PRIMARY_QUESTIONS[idx])
    q["options"] = _build_options(q)
    state.pending_question_id = q["id"]
    return q


def _parse_age(text: str) -> Optional[int]:
    t = (text or "").strip()
    if t in ("모름", "몰라", "잘모름"):
        return -1
    digits = "".join(ch for ch in t if ch.isdigit())
    if not digits:
        return None
    try:
        v = int(digits)
        if 0 < v < 120:
            return v
    except Exception:
        return None
    return None


def _normalize_general(answer: str) -> str:
    a = (answer or "").strip()
    if not a:
        return a
    # 흔한 변형 정규화
    if a in ["해당 없음", "해당없음"]:
        return "해당없음"
    if a in ["모름", "몰라", "잘모름", "모르겠어", "모르겠어요"]:
        return "모름"
    if a in ["무직", "미취업"]:
        return "구직 중(미취업)"
    if a in ["없다", "없어요", "없음"]:
        return "없음"
    if a in ["있다", "있어요", "있음"]:
        return "있음"
    return a


def apply_primary_answer(state: SessionState, answer: str) -> Tuple[bool, Optional[str]]:
    qid = state.pending_question_id
    if not qid:
        return False, "질문 상태가 꼬였어요. 다시 시도해 주세요."

    raw = (answer or "").strip()
    a = _normalize_general(raw)

    # 질문 정책 조회
    q = next((x for x in PRIMARY_QUESTIONS if x["id"] == qid), None)
    policy = (q.get("policy") if q else {}) or {}
    opts = _build_options(q) if q else None
    strict = bool(policy.get("strict", False))
    allow_free_text = bool(policy.get("allow_free_text", True))

    if qid == "age":
        age = _parse_age(a)
        if age is None:
            return False, "만 나이는 숫자로 입력해 주세요. 예: 27 / 모르면 '모름'"
        state.profile.age = age

    elif qid == "residency":
        # options 매칭 우선, 실패하면 자유입력 저장(allow_free_text=True)
        if opts and a in opts:
            state.profile.residency = a
        else:
            if strict and not allow_free_text:
                return False, "선택지 중 하나로 답해 주세요."
            state.profile.residency = a or "모름"

    elif qid == "status":
        if opts and a in opts:
            state.profile.status = a
        else:
            if strict and not allow_free_text:
                return False, "선택지 중 하나로 답해 주세요."
            state.profile.status = a or "모름"

    elif qid == "work_last_6m":
        if opts and a in opts:
            state.profile.work_last_6m = a
        else:
            if strict and not allow_free_text:
                return False, "선택지 중 하나로 답해 주세요."
            state.profile.work_last_6m = a or "모름"

    elif qid == "welfare":
        if opts and a in opts:
            state.profile.welfare = a
        else:
            # welfare는 자유입력도 허용(예: "차상위계층" 등)
            state.profile.welfare = a or "모름"

    elif qid == "household":
        if opts and a in opts:
            state.profile.household = a
        else:
            state.profile.household = a or "모름"

    else:
        return False, "알 수 없는 질문입니다."

    # ✅ 어떤 상황에서도 먹통 만들지 않음: 저장 후 다음 단계로 진행
    state.onboarding_step += 1
    state.pending_question_id = None
    return True, None
