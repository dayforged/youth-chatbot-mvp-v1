# backend/schema.py
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# =========================
# Request Schema
# =========================
class ChatRequest(BaseModel):
    """
    프론트 → 백엔드로 들어오는 단일 채팅 입력
    - 자유 텍스트
    - 버튼 선택지 클릭 결과
    둘 다 message로 통합
    """
    message: str = Field(..., description="사용자 질문 또는 선택지 응답")
    session_id: Optional[str] = Field(
        default=None,
        description="사용자 세션 식별자 (없으면 서버에서 신규 생성)"
    )


# =========================
# Response Schema
# =========================
class ChatResponse(BaseModel):
    """
    백엔드 → 프론트로 내려주는 챗봇 응답
    """
    session_id: str = Field(..., description="현재 사용자 세션 ID")

    # - onboarding : 1차 질문 수집 중
    # - followup   : 정책별 2차 질문 수집 중
    # - answer     : RAG 기반 최종 답변
    mode: str = Field(
        ...,
        description="챗봇 응답 모드 (onboarding | followup | answer)"
    )

    answer: str = Field(..., description="챗봇 응답 메시지")

    options: Optional[List[str]] = Field(
        default=None,
        description="사용자에게 제시할 선택지 목록 (버튼 UI용)"
    )

    debug_profile: Optional[Dict[str, Any]] = Field(
        default=None,
        description="수집된 사용자 프로필 정보 (개발용)"
    )
