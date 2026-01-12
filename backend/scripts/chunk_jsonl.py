import json
import re
from pathlib import Path
from typing import List
import tiktoken

IN_PATH = Path("data/processed-data/0154b536d619.jsonl")
OUT_PATH = Path("data/processed-data/chunks.jsonl")

CHUNK_TOKENS = 900
OVERLAP_TOKENS = 150
TOKEN_MODEL_FOR_COUNT = "gpt-4o-mini"  # 토큰 길이 대략 측정용

enc = tiktoken.encoding_for_model(TOKEN_MODEL_FOR_COUNT)

def tok_len(s: str) -> int:
    return len(enc.encode(s))

def split_paragraphs(text: str) -> List[str]:
    text = re.sub(r"\n{3,}", "\n\n", text.strip())
    return [p.strip() for p in text.split("\n\n") if p.strip()]

def chunk_paragraphs(paras: List[str]) -> List[str]:
    chunks = []
    cur = []
    cur_t = 0

    for p in paras:
        pt = tok_len(p)

        if pt > CHUNK_TOKENS:
            words = p.split()
            buf = []
            for w in words:
                buf.append(w)
                if tok_len(" ".join(buf)) >= CHUNK_TOKENS:
                    chunks.append(" ".join(buf).strip())
                    buf = []
            if buf:
                chunks.append(" ".join(buf).strip())
            continue

        if cur_t + pt <= CHUNK_TOKENS:
            cur.append(p)
            cur_t += pt
        else:
            chunks.append("\n\n".join(cur).strip())

            carry = []
            carry_t = 0
            for prev in reversed(cur):
                t = tok_len(prev)
                if carry_t + t > OVERLAP_TOKENS:
                    break
                carry.append(prev)
                carry_t += t
            carry = list(reversed(carry))

            cur = carry + [p]
            cur_t = sum(tok_len(x) for x in cur)

    if cur:
        chunks.append("\n\n".join(cur).strip())

    return [c for c in chunks if c]

def main():
    assert IN_PATH.exists(), f"missing: {IN_PATH}"

    n_pages = 0
    n_chunks = 0

    with IN_PATH.open("r", encoding="utf-8") as f_in, OUT_PATH.open("w", encoding="utf-8") as f_out:
        for line in f_in:
            rec = json.loads(line)
            n_pages += 1

            paras = split_paragraphs(rec["text"])
            chs = chunk_paragraphs(paras)

            for i, ch in enumerate(chs):
                out = {
                    "chunk_id": f'{rec["doc_id"]}_p{rec["page"]}_c{i}',
                    "doc_id": rec["doc_id"],
                    "source": rec["source"],
                    "page": rec["page"],
                    "text": ch,
                }
                f_out.write(json.dumps(out, ensure_ascii=False) + "\n")
                n_chunks += 1

    print(f"[OK] pages={n_pages}, chunks={n_chunks}")
    print(f"[OK] wrote: {OUT_PATH}")

if __name__ == "__main__":
    main()
