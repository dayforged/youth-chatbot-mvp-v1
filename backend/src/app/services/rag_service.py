# backend/src/app/services/rag_service.py
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import faiss
import requests
from sentence_transformers import SentenceTransformer

INDEX_PATH = Path("data/processed-data/faiss.index")
META_PATH = Path("data/processed-data/meta.json")

EMBED_MODEL = "BAAI/bge-m3"

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2:3b"

TOP_K_DEFAULT = 5
MAX_CTX_CHARS_PER_CHUNK = 900
OLLAMA_NUM_PREDICT = 520
MIN_TOP_SCORE_FOR_LLM = 0.55


def build_user_context(profile: Optional[Dict[str, Any]], followups: Optional[Dict[str, Any]]) -> str:
    profile = profile or {}
    followups = followups or {}

    def v(x: Any, unknown: str = "모름") -> str:
        if x is None:
            return unknown
        if isinstance(x, int) and x == -1:
            return unknown
        s = str(x).strip()
        return s if s else unknown

    lines = [
        f"- 만 나이: {v(profile.get('age'))}",
        f"- 거주지: {v(profile.get('residency'))}",
        f"- 현재 상태: {v(profile.get('status'))}",
        f"- 최근 6개월 근로 이력: {v(profile.get('work_last_6m'))}",
        f"- 기초생활수급/차상위 여부: {v(profile.get('welfare'))}",
        f"- 가구/세대 형태: {v(profile.get('household'))}",
    ]

    extra = []
    for k, val in followups.items():
        if val is None:
            continue
        s = str(val).strip()
        if s:
            extra.append(f"- {k}: {s}")
    if extra:
        lines.append("")
        lines.append("[추가 정보]")
        lines.extend(extra)

    return "\n".join(lines)


# ✅ 정책명 확정용 “후보 목록”
# (네 데이터가 아직 도약장려금만 있을 가능성이 커서, 후보는 MVP 기준 최소로 둠)
POLICY_CANDIDATES = [
    ("job_jump", "청년일자리도약장려금"),
    ("kua", "국민취업지원제도"),
    ("hope_account", "희망두배 청년통장"),
]


def _needs_policy_confirmation(question: str, intent: Optional[str]) -> bool:
    """
    ✅ 할루시네이션 방지 규칙:
    - 사용자가 정책명을 명확히 말하지 않고, '청년 장려금' 같은 일반어를 쓰면 확정 질문이 필요함
    - intent가 잡혔더라도 질문에 정책명이 명시되지 않으면 확인을 먼저 할 수도 있음
    """
    q = (question or "").strip()
    low = q.lower()

    # 명시적 정책명이 포함되어 있으면 confirmation 불필요
    explicit = any(name in q for _, name in POLICY_CANDIDATES)
    if explicit:
        return False

    # 일반어/반쪽 키워드 케이스는 확인 필요
    generic = any(k in low for k in ["청년 장려금", "일자리 장려금", "장려금", "지원금", "청년 지원금"])
    if generic:
        return True

    # intent가 없으면 확인 필요
    if intent is None:
        return True

    # intent가 있어도 질문이 너무 짧고 일반어면 확인
    if len(q) <= 14:
        return True

    return False


def _policy_confirmation_message(question: str) -> str:
    lines = []
    lines.append("질문하신 '청년 장려금'이 정확히 어떤 정책을 뜻하는지 먼저 확인이 필요합니다.")
    lines.append("비슷한 이름의 제도가 여러 개라서, 정책명을 확정하지 않으면 요건을 잘못 안내할 위험이 있어요.")
    lines.append("")
    lines.append("혹시 아래 중 어떤 정책을 찾으시는 걸까요?")
    for _, name in POLICY_CANDIDATES:
        lines.append(f"- {name}")
    lines.append("")
    lines.append("원하시는 정책명을 그대로 입력해 주시면, 그 다음에 자격/조건을 정확히 정리해드릴게요.")
    return "\n".join(lines)


class RAGService:
    def __init__(self):
        assert INDEX_PATH.exists(), f"missing: {INDEX_PATH}"
        assert META_PATH.exists(), f"missing: {META_PATH}"
        self.index = faiss.read_index(str(INDEX_PATH))
        self.meta = json.loads(META_PATH.read_text(encoding="utf-8"))
        self.embedder = SentenceTransformer(EMBED_MODEL)

    def _normalize_meta_item(self, item: Any, idx: int) -> Dict[str, Any]:
        if isinstance(item, dict):
            item.setdefault("chunk_id", f"chunk_{idx}")
            item.setdefault("source", None)
            item.setdefault("page", None)
            item.setdefault("text", "")
            return item
        return {"chunk_id": f"chunk_{idx}", "source": None, "page": None, "text": str(item)}

    def retrieve(self, query: str, top_k: int = TOP_K_DEFAULT) -> List[Dict[str, Any]]:
        qv = self.embedder.encode([query], normalize_embeddings=True).astype("float32")
        scores, idxs = self.index.search(qv, top_k)

        results: List[Dict[str, Any]] = []
        for score, idx in zip(scores[0], idxs[0]):
            if idx < 0:
                continue
            raw_item = self.meta[idx]
            item = self._normalize_meta_item(raw_item, idx)
            results.append({
                "score": float(score),
                "chunk_id": item["chunk_id"],
                "source": item["source"],
                "page": item["page"],
                "text": item["text"],
            })
        return results

    def _build_prompt(
        self,
        question: str,
        ctxs: List[Dict[str, Any]],
        user_context: str,
        history: Optional[List[Dict[str, str]]],
        intent: Optional[str],
    ) -> str:
        ctx_lines = []
        for i, c in enumerate(ctxs, start=1):
            text = (c.get("text") or "")
            if len(text) > MAX_CTX_CHARS_PER_CHUNK:
                text = text[:MAX_CTX_CHARS_PER_CHUNK] + "\n...(생략)"
            ctx_lines.append(f"[{i}] ({c.get('source')} p.{c.get('page')})\n{text}")
        ctx_block = "\n\n".join(ctx_lines).strip() or "(관련 문서 발췌가 충분하지 않음)"

        hist_block = ""
        if history:
            tail = history[-8:]
            hist_block = "\n".join([f"{m.get('role')}: {m.get('content')}" for m in tail])

        # intent 힌트를 약하게 제공 (확정은 LLM이 아니라 서버 정책확정 단계에서)
        intent_hint = ""
        if intent:
            intent_hint = f"- 시스템 추정 intent: {intent} (참고용, 확정 아님)"

        return f"""
너는 '청년 정책 상담사'다. 사용자는 비전공자이며 문서 용어에 익숙하지 않다.

[최우선 규칙]
- JSON 출력 금지.
- 문서 출처만 나열 금지.
- 문서에 없는 내용은 추측 금지. (추측 대신 '문서에 명시 없음' + 다음 액션 제시)
- 정책명이 불명확하면 절대 요건/자격을 단정하지 말고, 먼저 정책명을 확인하는 질문을 한다.

[사용자 프로필]
{user_context}

[최근 대화]
{hist_block}

[시스템 힌트]
{intent_hint}

[사용자 질문]
{question}

[근거 문서 발췌(Context)]
{ctx_block}

[답변 구조]
1) 지금 상태에서 할 수 있는 1차 답변(짧게)
2) 근거가 충분하면 조건/요건을 쉬운 말로 정리
3) 근거가 부족하면 "현재 보유 문서에 명시가 부족"이라고 말하고 (문서 추가/질문 구체화) 유도
4) 추가 질문은 1~2개만, 선택지 강제 금지
""".strip()

    def _call_ollama(self, prompt: str) -> str:
        r = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "top_p": 0.9,
                    "num_predict": OLLAMA_NUM_PREDICT,
                },
            },
            timeout=180,
        )
        r.raise_for_status()
        return (r.json().get("response") or "").strip()

    def answer(
        self,
        question: str,
        intent: Optional[str],
        top_k: int = TOP_K_DEFAULT,
        profile: Optional[Dict[str, Any]] = None,
        followups: Optional[Dict[str, Any]] = None,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        # ✅ 5번 요구: 반쪽 키워드 → 정책 확정 질문 선행
        if _needs_policy_confirmation(question, intent):
            return _policy_confirmation_message(question)

        user_context = build_user_context(profile, followups)
        retrieval_query = f"{question}\n\n[사용자 정보]\n{user_context}"

        ctxs = self.retrieve(retrieval_query, top_k)

        # 근거 약하면: LLM이 자연어로 "근거 부족" + 다음 액션 유도하도록
        if not ctxs or (ctxs and ctxs[0]["score"] < MIN_TOP_SCORE_FOR_LLM):
            prompt = self._build_prompt(
                question=question,
                ctxs=ctxs[:1] if ctxs else [],
                user_context=user_context,
                history=history,
                intent=intent,
            )
            try:
                return self._call_ollama(prompt)
            except Exception:
                return (
                    "현재 보유 문서에서 질문과 직접 연결되는 근거를 찾기 어렵습니다.\n"
                    "정확한 안내를 위해 정책명을 조금 더 구체적으로 적어주시거나, 해당 정책 PDF를 데이터에 추가해 주세요."
                )

        prompt = self._build_prompt(
            question=question,
            ctxs=ctxs,
            user_context=user_context,
            history=history,
            intent=intent,
        )

        try:
            return self._call_ollama(prompt)
        except Exception:
            # 어떤 에러든 사용자에게 자연어로 안내
            return (
                "지금은 답변을 만드는 과정에서 오류가 발생했어요.\n"
                "질문을 조금 더 짧게/구체적으로 다시 보내주시거나, 잠시 후 다시 시도해 주세요."
            )
