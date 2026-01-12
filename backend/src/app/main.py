# backend/src/app/main.py
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from schema import ChatRequest, ChatResponse

from .services.session_store import InMemorySessionStore, ChatMessage
from .services.onboarding import (
    needs_onboarding,
    get_next_primary_question,
    apply_primary_answer,
)
from .services.followup_questions import detect_policy_intent
from .services.rag_service import RAGService

app = FastAPI(title="Youth Policy Chatbot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # MVP
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

store = InMemorySessionStore()
rag = RAGService()


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    state = store.get_or_create(req.session_id)

    user_text = (req.message or "").strip()
    if user_text:
        state.messages.append(ChatMessage(role="user", content=user_text))

    # 1) 온보딩(프로필 수집): 옵션은 여기서만 제공
    if needs_onboarding(state):
        if state.pending_question_id is not None and user_text:
            accepted, err = apply_primary_answer(state, user_text)
            if not accepted:
                q = get_next_primary_question(state)
                store.save(state)
                return ChatResponse(
                    session_id=state.session_id,
                    mode="onboarding",
                    answer=f"{err}\n\n{q['text']}",
                    options=q["options"],
                    debug_profile=state.profile.__dict__,
                )

        q = get_next_primary_question(state)
        store.save(state)
        return ChatResponse(
            session_id=state.session_id,
            mode="onboarding",
            answer=q["text"],
            options=q["options"],
            debug_profile=state.profile.__dict__,
        )

    # 2) 온보딩 이후: 무조건 상담사 자연어 답변 (옵션 없음)
    intent = detect_policy_intent(user_text)

    answer_text = rag.answer(
        question=user_text,
        intent=intent,
        profile=state.profile.__dict__,
        followups=state.followups.__dict__,
        history=[{"role": m.role, "content": m.content} for m in state.messages][-12:],
    )

    state.messages.append(ChatMessage(role="assistant", content=answer_text))
    store.save(state)

    return ChatResponse(
        session_id=state.session_id,
        mode="answer",
        answer=answer_text,
        options=None,
        debug_profile={**state.profile.__dict__, **state.followups.__dict__},
    )
