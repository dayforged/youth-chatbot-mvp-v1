import re
import json
import hashlib
from pathlib import Path
import fitz  # PyMuPDF

# PDF "파일" 경로로 지정
PDF_PATH = r"C:\Users\USER\Desktop\MY FILES\PROJECT\youth-chatbot\backend\data\raw-data\2026년 청년일자리도약장려금 사업운영 지침('26.1월).pdf"

OUT_DIR = Path("processed-data")  
OUT_DIR.mkdir(parents=True, exist_ok=True)

def normalize_text(text: str) -> str:
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)

    lines = [ln.strip() for ln in text.splitlines()]
    cleaned = []
    blank_streak = 0
    for ln in lines:
        if not ln:
            blank_streak += 1
            if blank_streak == 1:
                cleaned.append("")
            continue
        blank_streak = 0
        cleaned.append(ln)

    text = "\n".join(cleaned)
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()

def is_noise_page(text: str) -> bool:
    return len(text) < 50

def main():
    pdf_path = Path(PDF_PATH)
    assert pdf_path.exists(), f"PDF not found: {pdf_path}"
    assert pdf_path.suffix.lower() == ".pdf", f"Not a PDF file: {pdf_path}"

    doc_id = hashlib.md5(pdf_path.name.encode("utf-8")).hexdigest()[:12]
    out_file = OUT_DIR / f"{doc_id}.jsonl"

    doc = fitz.open(pdf_path)  # ✅ str() 안 해도 됨
    with out_file.open("w", encoding="utf-8") as f:
        for i, page in enumerate(doc, start=1):
            raw = page.get_text("text") or ""
            text = normalize_text(raw)
            if is_noise_page(text):
                continue

            record = {
                "doc_id": doc_id,
                "source": pdf_path.name,
                "page": i,
                "text": text,
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"[OK] saved: {out_file}")

if __name__ == "__main__":
    main()
