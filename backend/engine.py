import os
import glob
from typing import List, Dict, Tuple, Optional

from dotenv import load_dotenv

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document

load_dotenv()

BASE_DIR = os.path.dirname(__file__)
RAW_DIR = os.path.join(BASE_DIR, "data", "raw-data")
DB_DIR = os.path.join(BASE_DIR, "chroma_db")


def _read_txt_files(raw_dir: str) -> List[Document]:
    docs: List[Document] = []
    for path in glob.glob(os.path.join(raw_dir, "*.txt")):
        with open(path, "r", encoding="utf-8") as f:
            text = f.read().strip()
        if not text:
            continue
        doc_id = os.path.basename(path)
        docs.append(Document(page_content=text, metadata={"doc_id": doc_id}))
    return docs


def _split_docs(docs: List[Document]) -> List[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=700,
        chunk_overlap=120,
        separators=["\n\n", "\n", ".", " ", ""],
    )
    return splitter.split_documents(docs)


class YouthPolicyEngine:
    """
    - raw-data/*.txt 를 Chroma로 인덱싱
    - 질문 시 similarity_search로 컨텍스트 뽑아서 LLM에 전달
    """

    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.api_ready = bool(api_key)

        self.llm = None
        self.emb = None
        self.vectordb = None

        if self.api_ready:
            self.llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)
            self.emb = OpenAIEmbeddings(model="text-embedding-3-small")
            self.vectordb = Chroma(persist_directory=DB_DIR, embedding_function=self.emb)

    def has_index(self) -> bool:
        if not self.vectordb:
            return False
        try:
            return self.vectordb._collection.count() > 0
        except Exception:
            return False

    def ingest_if_needed(self) -> Tuple[bool, str]:
        if not self.api_ready:
            return False, "OPENAI_API_KEY가 없어 인덱싱을 할 수 없습니다(.env 확인)."
        docs = _read_txt_files(RAW_DIR)
        if not docs:
            return False, f"raw-data에 txt가 없습니다: {RAW_DIR}"
        chunks = _split_docs(docs)

        if self.has_index():
            return True, "이미 인덱스가 존재합니다(스킵)."

        self.vectordb.add_documents(chunks)
        self.vectordb.persist()
        return True, f"Ingest 완료: 원문 {len(docs)}개 / 청크 {len(chunks)}개"

    def retrieve(self, query: str, top_k: int = 4) -> List[Document]:
        if not self.vectordb or not self.has_index():
            return []
        return self.vectordb.similarity_search(query, k=top_k)

    def _require_llm(self):
        if not self.api_ready or self.llm is None:
            raise RuntimeError("OPENAI_API_KEY가 설정되지 않아 LLM을 호출할 수 없습니다. backend/.env를 확인하세요.")

    def build_context(self, query: str, top_k: int = 4) -> Tuple[str, List[Tuple[str, str]]]:
        docs = self.retrieve(query, top_k=top_k)
        context = ""
        sources: List[Tuple[str, str]] = []
        for d in docs:
            doc_id = d.metadata.get("doc_id", "unknown")
            chunk = d.page_content
            sources.append((doc_id, chunk[:500]))
            context += f"\n[문서:{doc_id}]\n{chunk}\n"
        return context, sources

    def answer(
        self,
        feature: str,
        user_question: str,
        profile: Dict[str, str],
        top_k: int = 4,
    ) -> str:
        """
        feature: summary | qa | recommend
        """
        self._require_llm()

        # 컨텍스트는 질문 + 프로필 핵심을 합쳐서 검색
        query_for_search = f"{user_question}\n프로필:{profile}"
        context, _sources = self.build_context(query_for_search, top_k=top_k)

        # 공통 안전 가드(과도한 단정/최대이득 단정 방지)
        safety_rules = (
            "주의: 문서 컨텍스트에 없는 내용은 단정하지 말고 '문서에서 확인되지 않습니다'라고 말하세요. "
            "정책은 중복수혜 제한/모집기간/세부요건이 있어 최종 확인은 공식 공고를 안내하세요. "
            "주민번호/계좌/정확한 주소/잔고/자산총액 등은 요구하지 마세요."
        )

        if feature == "summary":
            system = "너는 서울시 청년정책 문서를 쉬운 말로 요약해주는 도우미다."
            user = (
                f"{safety_rules}\n\n"
                f"사용자 질문/요청: {user_question}\n"
                f"사용자 프로필(판정용): {profile}\n\n"
                f"문서 컨텍스트:\n{context}\n\n"
                "출력 형식:\n"
                "- 6~10개 bullet\n"
                "- 자격/기간/금액/신청방법/주의사항이 있으면 포함\n"
            )

        elif feature == "qa":
            system = "너는 서울시 청년정책 문서 기반 Q&A 챗봇이다."
            user = (
                f"{safety_rules}\n\n"
                f"질문: {user_question}\n"
                f"사용자 프로필(판정용): {profile}\n\n"
                f"문서 컨텍스트:\n{context}\n\n"
                "출력 형식:\n"
                "- 결론 1~2문장\n"
                "- 근거 bullet 3~6개\n"
                "- 추가로 확인할 정보(질문) 2~4개\n"
            )

        else:  # recommend
            system = "너는 서울시 청년정책 안내 및 신청 전략을 도와주는 도우미다."
            user = (
                f"{safety_rules}\n\n"
                f"사용자 질문: {user_question}\n"
                f"사용자 프로필(판정용): {profile}\n\n"
                f"문서 컨텍스트:\n{context}\n\n"
                "출력 형식(서비스처럼 보이게):\n"
                "1) 현재 조건에서 가능성이 높은 정책군(3~6개 bullet)\n"
                "2) 우선순위 전략(타임라인/마감/중복가능성 고려) 3~5개 bullet\n"
                "3) 다음 행동 체크리스트(서류/확인포인트) 5~10개 bullet\n"
                "4) 추가로 확인해야 정확해지는 질문 2~4개\n"
            )

        resp = self.llm.invoke(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ]
        )
        return resp.content.strip()
